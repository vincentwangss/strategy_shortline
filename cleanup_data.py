import os, re, json, shutil
from collections import Counter, defaultdict

root = 'D:/杰哥复盘数据'
backup_dir = 'D:/杰哥复盘数据/backup_articles'

# ========== 第零步：备份 ==========
print('=== 创建备份 ===')
if not os.path.exists(backup_dir):
    for entry in os.scandir(root):
        if not entry.is_dir() or entry.name in ('price_data', 'backup_articles'):
            continue
        src = entry.path
        dst = os.path.join(backup_dir, entry.name)
        shutil.copytree(src, dst)
        print(f'  备份 {entry.name} -> {dst}')
print('备份完成\n')

# ========== 第一步：改进简写映射 ==========
print('=== 构建简写映射 ===')

with open('D:/杰哥复盘数据/stock_name_map.json', 'r', encoding='utf-8') as f:
    name_map = json.load(f)
all_names = list(name_map.keys())

# 扫描所有文章，找到简写模式
all_text = ''
for entry in os.scandir(root):
    if not entry.is_dir() or entry.name in ('price_data', 'backup_articles'):
        continue
    for f in os.listdir(entry.path):
        if not f.endswith('.html'):
            continue
        try:
            with open(os.path.join(entry.path, f), 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        all_text += text + '\n'

# 找中文(2-4字) + 1个大写字母 模式
pat1 = re.findall(r'([一-鿿]{2,4})([A-Z])', all_text)
cnt1 = Counter(pat1)

abbrev_map = {}

for (cn_prefix, letter), count in cnt1.most_common():
    if count < 2:
        continue
    candidates = [n for n in all_names if n.startswith(cn_prefix) and len(n) > len(cn_prefix)]
    if len(candidates) == 1:
        abbrev_map[f'{cn_prefix}{letter}'] = candidates[0]
    elif len(candidates) > 1:
        # 用字母长度过滤：大写字母数应该匹配剩余字数的1-2倍
        # 例如 有研XC (2字母) -> 有研新材(2剩余字) ✓
        letter_count = 1
        filtered = []
        for c in candidates:
            remaining = c[len(cn_prefix):]
            # 每个汉字对应1-2个拼音首字母
            expected_letter_count = len(remaining)
            # 特殊情况：一个字可能是复姓拼音或整体认读音节
            if expected_letter_count == 0:
                continue
            # 允许1个字母对应1-2个字（极简情况如"红宝L"中"L"对应"丽"）
            # 也支持1个字母对应1个字（标准情况）
            if letter_count <= expected_letter_count * 2 and letter_count >= expected_letter_count - 1:
                filtered.append(c)

        if len(filtered) == 1:
            abbrev_map[f'{cn_prefix}{letter}'] = filtered[0]

# 2个字母的简写
pat2 = re.findall(r'([一-鿿]{2,4})([A-Z]{2})', all_text)
cnt2 = Counter(pat2)
for (cn_prefix, letters), count in cnt2.most_common():
    if count < 2:
        continue
    candidates = [n for n in all_names if n.startswith(cn_prefix) and len(n) > len(cn_prefix)]
    if len(candidates) == 1:
        abbrev_map[f'{cn_prefix}{letters}'] = candidates[0]
    elif len(candidates) > 1:
        # 用字母长度过滤
        filtered = []
        for c in candidates:
            remaining = c[len(cn_prefix):]
            # 2个字母应对应1-2个汉字
            if len(remaining) * 2 >= 2 >= len(remaining) - 1:
                filtered.append(c)
        if len(filtered) == 1:
            abbrev_map[f'{cn_prefix}{letters}'] = filtered[0]

# 强制加入已知但可能漏掉的映射
force_add = {
    '有研XC': '有研新材', '中通客C': '中通客车',
    '比亚迪D': '比亚迪', '东方财D': '东方财富',
    '浙江S': '浙江世宝', '浙江建T': '浙江建投',
}
for k, v in force_add.items():
    if k not in abbrev_map:
        # 验证股票名存在
        if v in name_map:
            abbrev_map[k] = v
            print(f'  强制添加: {k} -> {v}')

# 按出现次数排序输出
print(f'\n共{len(abbrev_map)}条映射')
print('\n出现次数最多的20条:')
abbrev_counts = [(abbr, full, all_text.count(abbr)) for abbr, full in abbrev_map.items()]
abbrev_counts.sort(key=lambda x: -x[2])
for abbr, full, c in abbrev_counts[:20]:
    print(f'  {abbr} -> {full} ({c}次)')

with open('D:/杰哥复盘数据/abbrev_map.json', 'w', encoding='utf-8') as f:
    json.dump(abbrev_map, f, ensure_ascii=False, indent=2)

# ========== 第二步：替换正文中的简写 ==========
print('\n=== 替换正文中的简写 ===')

# 构建替换规则表，按长度降序排列 (避免部分匹配)
replacements = sorted(abbrev_map.items(), key=lambda x: -len(x[0]))

total_replaced = 0
file_count = 0
for entry in os.scandir(root):
    if not entry.is_dir() or entry.name in ('price_data', 'backup_articles'):
        continue
    acct = entry.name
    for f in os.listdir(entry.path):
        if not f.endswith('.html'):
            continue
        fpath = os.path.join(entry.path, f)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue

        new_content = content
        count = 0
        for abbr, full in replacements:
            # 只在body内容中替换，不破坏HTML结构
            # 简单替换所有出现
            if abbr in new_content:
                new_content = new_content.replace(abbr, full)
                cnt = content.count(abbr) - new_content.count(abbr)
                count += cnt if cnt > 0 else 0

        if count > 0:
            with open(fpath, 'w', encoding='utf-8') as fh:
                fh.write(new_content)
            total_replaced += count
            file_count += 1
            if file_count <= 5:
                print(f'  {acct}/{f[:50]}: 替换{count}处')

print(f'共修改 {file_count} 个文件，替换 {total_replaced} 处')

# ========== 第三步：重命名文件名 ==========
print('\n=== 重命名文件名 ===')

# 建索引：从原始来源获取日期
source_index = {}
source_paths = [
    'D:/tools/微信公众号批量下载工具3.7',
    'D:/tools/微信公众号批量下载工具3.8',
    'D:/project/duanxian/tools',
]
for base in source_paths:
    if not os.path.exists(base):
        continue
    for item in os.listdir(base):
        cache_dir = os.path.join(base, item)
        if not os.path.isdir(cache_dir):
            continue
        for sub in os.listdir(cache_dir):
            acct_dir = os.path.join(cache_dir, sub)
            if not os.path.isdir(acct_dir):
                continue
            for sf in os.listdir(acct_dir):
                if not (sf.endswith('.html') or sf.endswith('.md')):
                    continue
                dm = re.match(r'\[(\d{4}-\d{2}-\d{2})\](.*)', sf)
                if not dm:
                    dm = re.match(r'\[(\d{4})(\d{2})(\d{2})', sf)
                    if dm:
                        norm = f'{dm.group(1)}-{dm.group(2)}-{dm.group(3)}'
                        rest = sf[sf.index(']')+1:]
                        dm = (norm, rest)
                if dm:
                    if isinstance(dm, tuple) and len(dm) == 2:
                        norm, rest = dm
                    else:
                        norm = dm.group(1)
                        rest = dm.group(2)
                    sf_noext = os.path.splitext(rest)[0].strip()
                    source_index[sf_noext] = norm

rename_count = 0
skip_count = 0
no_date_count = 0

for entry in os.scandir(root):
    if not entry.is_dir() or entry.name in ('price_data', 'backup_articles'):
        continue
    acct = entry.name
    d = entry.path

    for f in os.listdir(d):
        fpath = os.path.join(d, f)
        if os.path.isdir(fpath):
            continue

        # 检查是否已有标准日期前缀
        if re.match(r'^\d{8}_', f):
            skip_count += 1
            continue

        date_str = None
        new_name = None

        # 生成新文件名
        ext = os.path.splitext(f)[1]  # keep original extension

        # 格式1: [YYYY-MM-DD]标题
        m = re.match(r'\[(\d{4})-(\d{2})-(\d{2})\](.*)', f)
        if m:
            y, mo, dd, title = m.groups()
            date_str = f'{y}{mo}{dd}'
            new_name = f'{date_str}_{title.strip().lstrip("_")}'

        # 格式2: [YYYYMMDDHHMMSS]标题
        if not m:
            m = re.match(r'\[(\d{4})(\d{2})(\d{2})\d*\](.*)', f)
            if m:
                y, mo, dd, title = m.groups()
                date_str = f'{y}{mo}{dd}'
                new_name = f'{date_str}_{title.strip().lstrip("_")}'

        # 无日期：尝试从原始来源找回
        if not m:
            base_noext = os.path.splitext(f)[0].strip()
            if base_noext in source_index:
                date_str = source_index[base_noext].replace('-', '')
                new_name = f'{date_str}_{base_noext}{ext}'
            else:
                no_date_count += 1
                # 保留原文件名，移动到 separate 目录
                continue

        if new_name:
            new_path = os.path.join(d, new_name)
            if not os.path.exists(new_path):
                os.rename(fpath, new_path)
                rename_count += 1
                if rename_count <= 5:
                    print(f'  {acct}: {f[:50]}')
                    print(f'    -> {new_name[:60]}')
            else:
                # 文件已存在（可能是重复）
                dedup_name = new_name.replace(ext, f'_{hash(fpath) % 10000:04d}{ext}')
                os.rename(fpath, os.path.join(d, dedup_name))
                rename_count += 1
                if rename_count <= 5:
                    print(f'  {acct} [重名]: {f[:50]} -> {dedup_name[:60]}')

print(f'重命名: {rename_count} 个')
print(f'跳过(已有日期): {skip_count} 个')
print(f'无日期(需人工处理): {no_date_count} 个')

# 保存未处理文件清单
if no_date_count > 0:
    undated_list = []
    for entry in os.scandir(root):
        if entry.is_dir() and entry.name not in ('price_data', 'backup_articles'):
            for f in os.listdir(entry.path):
                if not re.match(r'^\d{8}_', f) and not re.match(r'\[\d', f):
                    undated_list.append(f'{entry.name}/{f}')
    with open('D:/杰哥复盘数据/undated_files.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(undated_list)))
    print(f'\n无日期文件列表已保存到 undated_files.txt ({len(undated_list)}个)')

print('\n全部处理完成！')
