"""
语义化信号引擎 v2
==================
基于短线交易策略体系.md 的十条投资原则重构：

1. 全句语义分析（不是20字截取）
2. 买入/卖出/中性 意图分类
3. 个股角色识别（龙头/核心/跟风/杂毛）
4. 情绪周期阶段判断
5. 基于原则的综合评分

用法:
  from signal_engine import SignalEngine
  engine = SignalEngine()
  engine.scan_articles()  # 扫描并生成信号
"""

import os, re, json
from collections import OrderedDict, Counter

ROOT = r'D:/杰哥复盘数据'

# ═══════════════════════════════════════════════════
# 语义规则库（基于策略体系提炼）
# ═══════════════════════════════════════════════════

# 买入意图关键词（正向）
BUY_SIGNALS = [
    '关注', '低吸', '打板', '回封', '看好', '可以买', '买入',
    '上车', '加仓', '博弈', '试错', '拿先手', '半路', '扫板',
    '排板', '竞价', '反核', '分歧低吸', '弱转强',
]

# 卖出/回避信号
SELL_SIGNALS = [
    '卖出', '出局', '止损', '止盈', '回避', '谨慎', '不碰',
    '不要追', '不能追', '别追', '走人', '减仓', '兑现',
    '不适合买', '不参与', '不考虑', '放弃',
]

# 中性持有信号
HOLD_SIGNALS = [
    '持有', '做T', '格局', '持股', '不动', '观察',
    '看看', '等待', '等机会',
]

# 个股角色关键词
ROLE_KEYWORDS = {
    '总龙头': ['总龙头', '市场总龙头', '最高板'],
    '板块龙头': ['板块龙头', '龙头', '龙一', '龙二'],
    '核心辨识度': ['核心', '辨识度', '阵眼', '前排', '高标'],
    '补涨': ['补涨', '补涨龙', '低位补涨'],
    '跟风': ['跟风', '后排', '杂毛', '卡位'],
}

# 情绪周期关键词
PHASE_KEYWORDS = {
    '冰点': ['冰点', '恐慌', 'A杀', '补跌', '高位股补跌', '跌停潮',
             '量能萎缩', '亏钱效应', '惨烈', '没什么能玩'],
    '修复': ['修复', '回暖', '企稳', '反弹', '反抽', '止跌',
             '弱修复', '强修复', '增量修复', '修复日'],
    '高潮': ['高潮', '加速', '涨停潮', '全面爆发', '一致性',
             '一致', '顶一字', '一字板', '发酵'],
    '退潮': ['退潮', '分歧加大', '轮动快', '没有持续性',
             '高度压缩', '管住手', '等待周期'],
}

# 开仓限制关键词（看到这些词降低评分）
RISK_WORDS = [
    '风险', '亏钱效应', 'A杀', '退潮', '补跌', '出货',
    '没量能', '缩量', '弱势', '横盘', '震荡',
]

# 否定词（反转意图）
NEGATION_WORDS = ['不', '别', '不要', '不能', '没', '无', '慎']

# 中文后缀→拼音缩写映射（文章里常用拼音缩写代替汉字）
SUFFIX_ABBREV = {
    '股份': 'gf', '科技': 'kj', '电子': 'dz', '智能': 'zn',
    '通信': 'tx', '光电': 'gd', '医药': 'yy', '生物': 'sw',
    '能源': 'ny', '证券': 'zq', '银行': 'yh', '保险': 'bx',
    '汽车': 'qc', '地产': 'dc', '材料': 'cl', '装备': 'zb',
    '航空': 'hk', '信息': 'xx', '软件': 'rj', '网络': 'wl',
    '传媒': 'cm', '数字': 'sz', '控股': 'kg', '实业': 'sy',
    '集团': 'jt', '工程': 'gc', '建设': 'js', '发展': 'fz',
    '国际': 'gj', '化学': 'hx', '新材': 'xc', '重工': 'zg',
    '股份': 'gf', '科技': 'kj',
}

# 积极/看好语境词（没有明确买入词，但语境表达正面看法）
BULLISH_CONTEXT = [
    '可以做', '适合做', '值得做', '可以看', '可以搞',
    '性价比', '有机会', '有空间', '有预期', '有想象',
    '表现不错', '可以关注', '可以参与', '做核心', '做龙头',
    '多看看', '多关注', '核心品种', '好机会', '不错',
    '比较强', '挺强', '很强', '最强', '走得强',
    '涨了', '走强', '反包', '涨停', '超预期',
    '机会', '空间', '预期',
]

# 粉丝提问特征模式（微信文章留言区）
FAN_QUESTION_PATTERNS = [
    r'^[^\s]{1,8}来自[^\s]{1,10}.*杰哥[，,：:\?？]',  # "用户名来自地区...杰哥，..."
    r'[？?]\s*$',                     # 以问号结尾
    r'^(请问|请教|杰哥)',              # 以请教开头
    r'怎么看$',                        # "怎么看"
    r'还能[看持]',                     # "还能看吗/还能持有吗"
    r'怎么样$',                        # "怎么样？"
    r'给反弹',                         # "给反弹吗"
    r'可以[买持]',                     # "可以买吗/可以持有吗"
]


class SignalEngine:
    def __init__(self, root=ROOT):
        self.root = root
        self.name_map = self._load_name_map()
        # 按长度降序排列，长名字优先匹配
        self.stock_names = sorted(self.name_map.keys(), key=len, reverse=True)
        self.sector_map = self._load_sector_map()
        # 构建缩写映射：如 "润建gf" -> ("润建股份", "002929")
        self.abbrev_map = self._build_abbreviation_map()
        # 合并后的查找列表（原名+缩写）
        self.all_search_terms = self._build_search_terms()

    def _build_abbreviation_map(self):
        """为股票名称构建拼音缩写映射，如 润建股份 -> ['润建gf', '润建股份']"""
        abbrev = {}
        for name, codes in self.name_map.items():
            code = codes[0] if codes else ''
            if not code:
                continue
            # 对每个后缀尝试生成缩写
            for suffix, abbr in SUFFIX_ABBREV.items():
                if name.endswith(suffix):
                    base = name[:-len(suffix)]
                    abbr_name = base + abbr  # 如 "润建gf"
                    if abbr_name not in abbrev:
                        abbrev[abbr_name] = (name, code)
        return abbrev

    def _build_search_terms(self):
        """合并原名+缩写，按长度降序"""
        terms = list(self.stock_names)  # 原名
        terms.extend(self.abbrev_map.keys())  # 缩写
        return sorted(set(terms), key=len, reverse=True)

    def _find_article_body(self, text):
        """
        分割文章正文和留言区。
        公众号文章格式：正文在前，留言区在"本人内容皆为个人分享"之类的声明之后。
        返回 (body_text, qa_text)
        """
        # 常见声明/分割标记
        boundary_markers = [
            '本人内容皆为个人分享',
            '以上内容均为个人分享',
            '欢迎多点赞点在看',
            '以上就是本期的复盘',
        ]
        split_pos = len(text)
        for marker in boundary_markers:
            pos = text.find(marker)
            if pos != -1 and pos < split_pos:
                split_pos = pos

        body = text[:split_pos].strip()
        qa = text[split_pos:].strip()
        return body, qa

    def _load_name_map(self):
        path = os.path.join(self.root, 'stock_name_map.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_sector_map(self):
        path = os.path.join(self.root, 'stock_sector.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ═══════════════════════════════════════════
    # 文本处理
    # ═══════════════════════════════════════════

    def extract_clean_text(self, html):
        """提取纯文本，保留段落结构"""
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>',
                      '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        text = re.sub(r'&[a-z]+;', ' ', text)
        # 保留换行和句号（用来分句）
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        return text.strip()

    def split_sentences(self, text):
        """按标点符号分割句子"""
        text = re.sub(r'\s+', '', text)
        sentences = re.split(r'[。！？；\n]', text)
        return [s.strip() for s in sentences if len(s.strip()) > 3]

    def find_stocks_in_sentence(self, sentence):
        """
        在句子中查找股票名字（含拼音缩写），返回 [(name, code, pos), ...]
        支持：全名"润建股份"、缩写"润建gf"、中文名简称"润建"
        """
        found = []
        seen_positions = set()  # 去重：同一位置不同名称只取最长的

        for term in self.all_search_terms:
            idx = 0
            while True:
                idx = sentence.find(term, idx)
                if idx == -1:
                    break

                # 判断这个term是原名还是缩写
                if term in self.name_map:
                    name = term
                    code = self.name_map[name][0] if self.name_map[name] else ''
                elif term in self.abbrev_map:
                    name, code = self.abbrev_map[term]
                else:
                    idx += len(term)
                    continue

                if not code:
                    idx += len(term)
                    continue

                # 去重：如果这个位置已经被更长的匹配覆盖，跳过
                overlap = False
                for seen_start, seen_end in seen_positions:
                    if not (idx + len(term) <= seen_start or idx >= seen_end):
                        overlap = True
                        break
                if overlap:
                    idx += len(term)
                    continue

                seen_positions.add((idx, idx + len(term)))
                found.append((name, code, idx))
                idx += len(term)

        # 按出现位置排序
        found.sort(key=lambda x: x[2])
        return found

    # ═══════════════════════════════════════════
    # 语义分析
    # ═══════════════════════════════════════════

    def has_negation(self, text, keyword_pos):
        """检查关键词前面是否有否定词"""
        before = text[max(0, keyword_pos - 4):keyword_pos]
        for neg in NEGATION_WORDS:
            if neg in before:
                return True
        return False

    def classify_intent(self, sentence, stock_pos, stock_len, role='普通', is_analysis_section=False):
        """
        判断对某只股票的意图：buy / sell / hold / mention
        基于全句语义分析，不是截取片段

        Parameters:
        - is_analysis_section: 是否在正文分析区（非留言区），正文区放宽判断标准
        """
        # 用股票名字前后的上下文来判断
        text_before = sentence[:stock_pos]
        text_after = sentence[stock_pos + stock_len:]

        # 检查卖出信号（优先级最高）
        for kw in SELL_SIGNALS:
            if kw in text_before or kw in text_after:
                return 'sell'

        # 检查买入信号（显式关键词）
        for kw in BUY_SIGNALS:
            if kw in text_before or kw in text_after:
                # 检查是否有否定
                kw_pos_in_text = (text_before + text_after).find(kw)
                if not self.has_negation(text_before + text_after, kw_pos_in_text):
                    return 'buy'
                else:
                    return 'mention'  # 否定过的买入信号算中性

        # 检查持有信号
        for kw in HOLD_SIGNALS:
            if kw in text_before or kw in text_after:
                return 'hold'

        # ═══ 正文分析区的宽松判断 ═══
        if is_analysis_section:
            # 1. 角色为龙头/核心/辨识度的个股，默认视为买入信号
            #    （作者提到核心品种本身就是看好，不用再写"买入"二字）
            if role in ('总龙头', '板块龙头', '核心辨识度'):
                return 'buy'

            # 2. 积极语境词检测
            sentence_text = text_before + text_after
            for kw in BULLISH_CONTEXT:
                if kw in sentence_text and not self.has_negation(sentence_text, sentence_text.find(kw)):
                    return 'buy'

        return 'mention'

    def classify_role(self, sentence, stock_pos, stock_len):
        """
        判断股票在文中的角色：
        总龙头 / 板块龙头 / 核心 / 补涨 / 跟风 / 普通
        """
        # 取股票名周围60个字符分析角色
        start = max(0, stock_pos - 30)
        end = min(len(sentence), stock_pos + stock_len + 30)
        context = sentence[start:end]

        # 从高到低判断
        roles_found = []
        for role, keywords in ROLE_KEYWORDS.items():
            for kw in keywords:
                if kw in context:
                    roles_found.append(role)

        if roles_found:
            return roles_found[0]  # 返回最高优先级角色

        return '普通'

    def detect_market_phase(self, article_text):
        """
        判断文章反映的情绪周期阶段
        返回值: '冰点' / '修复' / '高潮' / '退潮' / '震荡'
        """
        scores = {'冰点': 0, '修复': 0, '高潮': 0, '退潮': 0}
        for phase, keywords in PHASE_KEYWORDS.items():
            for kw in keywords:
                count = article_text.count(kw)
                scores[phase] += count * (2 if kw in ['冰点', '退潮', '修复'] else 1)

        # 震荡是默认状态，不加分
        max_phase = max(scores, key=scores.get)
        if scores[max_phase] == 0:
            return '震荡'
        return max_phase

    def get_context_sentence(self, text, stock_pos, stock_len):
        """
        获取股票所在的完整句子及前后文
        返回: (前一句, 本句, 后一句) 用于完整的上下文分析
        """
        # 找最近的句号/换行
        sent_start = text.rfind('。', 0, stock_pos)
        if sent_start == -1:
            sent_start = text.rfind('\n', 0, stock_pos)
        if sent_start == -1:
            sent_start = max(0, stock_pos - 50)
        else:
            sent_start += 1

        sent_end = text.find('。', stock_pos + stock_len)
        if sent_end == -1:
            sent_end = text.find('\n', stock_pos + stock_len)
        if sent_end == -1:
            sent_end = min(len(text), stock_pos + stock_len + 50)

        sentence = text[sent_start:sent_end].strip()
        return sentence

    def compute_conviction(self, intent, role, phase):
        """
        综合计算买入信心度（决定仓位大小）
        基于十条投资原则：
        - 分歧低吸 = 高信心
        - 龙头 = 高信心
        - 冰点期不出手
        - 高潮期不接力
        """
        if intent != 'buy':
            return 0

        score = 0

        # 角色权重（原则三：龙头战法）
        role_scores = {
            '总龙头': 5,
            '板块龙头': 4,
            '核心辨识度': 3,
            '补涨': 2,
            '跟风': -1,
            '普通': 1,
        }
        score += role_scores.get(role, 0)

        # 情绪周期权重（原则一：情绪周期）
        phase_multipliers = {
            '冰点': 0.3,   # 冰点不出手
            '修复': 1.5,   # 修复期可做
            '高潮': 0.5,   # 高潮不接力
            '退潮': 0.2,   # 退潮减仓
            '震荡': 0.8,   # 震荡市低吸
        }
        multiplier = phase_multipliers.get(phase, 0.8)

        final_score = score * multiplier
        return final_score

    # ═══════════════════════════════════════════
    # 主扫描流程
    # ═══════════════════════════════════════════

    def scan_articles(self):
        """扫描所有文章生成语义化信号"""
        all_signals = []
        total_files = 0

        for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
            d = os.path.join(self.root, acct)
            print(f'扫描 {acct}...')
            for fname in sorted(os.listdir(d)):
                if not fname.endswith('.html'):
                    continue

                m = re.match(r'(\d{8})_(.*)', fname)
                if not m:
                    continue
                ymd = m.group(1)
                date_str = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}'

                fpath = os.path.join(d, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                except:
                    continue

                text = self.extract_clean_text(content)
                if len(text) < 50:
                    continue

                total_files += 1

                # 分割正文和留言区
                body_text, qa_text = self._find_article_body(text)

                # 判断整篇文章的情绪周期（用全文判断更准确）
                phase = self.detect_market_phase(text)

                # 正文区句子
                body_sentences = self.split_sentences(body_text)
                # 留言区句子
                qa_sentences = self.split_sentences(qa_text)

                file_signals = []
                processed_codes = set()

                # 处理正文区（is_analysis_section=True → 放宽意图判断）
                for sentence in body_sentences:
                    found_stocks = self.find_stocks_in_sentence(sentence)
                    if not found_stocks:
                        continue

                    for stock_name, stock_code, pos in found_stocks:
                        if not stock_code:
                            continue

                        # 去重
                        dedup_key = f'{stock_code}_{date_str}'
                        if dedup_key in processed_codes:
                            continue

                        # 先判定角色（意图判断需要用到角色）
                        role = self.classify_role(sentence, pos, len(stock_name))

                        # 意图分类（正文区宽松）
                        intent = self.classify_intent(sentence, pos, len(stock_name),
                                                      role=role, is_analysis_section=True)

                        # 计算信心度
                        conviction = self.compute_conviction(intent, role, phase)

                        # 获取完整句子作为上下文（直接用已经分割好的句子）
                        context = sentence

                        # 买入信号
                        if intent == 'buy' and conviction > 0:
                            file_signals.append({
                                'date': date_str,
                                'stock_name': stock_name,
                                'stock_code': stock_code,
                                'account': acct,
                                'role': role,
                                'phase': phase,
                                'conviction': round(conviction, 1),
                                'context': context,
                                'intent': intent,
                            })
                            processed_codes.add(dedup_key)

                # 处理留言区（仅处理作者的回复，过滤读者提问）
                for sentence in qa_sentences:
                    # 跳过纯读者提问
                    if self._is_fan_question(sentence):
                        continue

                    found_stocks = self.find_stocks_in_sentence(sentence)
                    if not found_stocks:
                        continue

                    for stock_name, stock_code, pos in found_stocks:
                        if not stock_code:
                            continue

                        dedup_key = f'{stock_code}_{date_str}'
                        if dedup_key in processed_codes:
                            continue

                        role = self.classify_role(sentence, pos, len(stock_name))

                        # 留言区用严格模式
                        intent = self.classify_intent(sentence, pos, len(stock_name),
                                                      role=role, is_analysis_section=False)

                        conviction = self.compute_conviction(intent, role, phase)
                        context = self.get_context_sentence(text, pos, len(stock_name))

                        if intent == 'buy' and conviction > 0:
                            file_signals.append({
                                'date': date_str,
                                'stock_name': stock_name,
                                'stock_code': stock_code,
                                'account': acct,
                                'role': role,
                                'phase': phase,
                                'conviction': round(conviction, 1),
                                'context': context,
                                'intent': intent,
                            })
                            processed_codes.add(dedup_key)

                        elif intent == 'sell':
                            file_signals.append({
                                'date': date_str,
                                'stock_name': stock_name,
                                'stock_code': stock_code,
                                'account': acct,
                                'role': role,
                                'phase': phase,
                                'conviction': 0,
                                'context': context,
                                'intent': 'sell',
                            })
                            processed_codes.add(dedup_key)

                all_signals.extend(file_signals)

        print(f'\n扫描完成: {total_files} 文件, {len(all_signals)} 信号')

        # 统计
        intents = Counter(s['intent'] for s in all_signals)
        roles = Counter(s['role'] for s in all_signals)
        print(f'意图分布: {dict(intents)}')
        print(f'角色分布: {dict(roles)}')

        # 保存
        self._save_signals(all_signals)
        self._save_phase_info(all_signals)
        return all_signals

    def _is_fan_question(self, text):
        """判断是否是粉丝提问（留言区），用正则模式匹配"""
        text = text.strip()
        for pat in FAN_QUESTION_PATTERNS:
            if re.search(pat, text):
                return True
        # "用户名来自地区+内容" 模式（留言区常见格式）
        if re.match(r'^[一-鿿\w]{1,10}来自', text):
            return True
        return False

    def _save_signals(self, signals):
        path = os.path.join(self.root, 'stock_signals_v2.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(signals, f, ensure_ascii=False, indent=2)
        print(f'已保存 {path} ({len(signals)} 条)')

        # 同时保存精简版
        buy_signals = [s for s in signals if s['intent'] == 'buy' and s['conviction'] > 0]
        path2 = os.path.join(self.root, 'stock_signals.json')
        with open(path2, 'w', encoding='utf-8') as f:
            json.dump(buy_signals, f, ensure_ascii=False, indent=2)
        print(f'已保存 {path2} ({len(buy_signals)} 条买入信号)')

    def _save_phase_info(self, signals):
        """保存每日情绪周期信息"""
        daily_phase = OrderedDict()
        for s in signals:
            d = s['date']
            if d not in daily_phase:
                daily_phase[d] = s['phase']

        path = os.path.join(self.root, 'daily_phase.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(daily_phase, f, ensure_ascii=False, indent=2)
        print(f'已保存 {path} ({len(daily_phase)} 天)')


if __name__ == '__main__':
    engine = SignalEngine()
    engine.scan_articles()
