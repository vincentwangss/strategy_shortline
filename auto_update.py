"""
每日自动更新：微信公众号文章下载 + 信号提取 + 回测 + 持仓报告
===============================================================

原理：用 Playwright 访问公众号历史文章页，获取最新文章URL并下载。
首次运行需扫码登录微信，后续自动复用会话。

用法:
  python auto_update.py              # 正常运行（自动下载新文章+跑管道）
  python auto_update.py --sync-only   # 只同步已有工具下载，不启动浏览器
  python auto_update.py --re-login    # 重新扫码登录
  python auto_update.py --pipeline    # 只跑管道（不下载）
"""

import asyncio, os, re, sys, json, subprocess
from datetime import datetime
from bs4 import BeautifulSoup

ROOT = r'D:/杰哥复盘数据'
STATE_FILE = os.path.join(ROOT, '.playwright_state')
DOWNLOADED_URLS = os.path.join(ROOT, '.downloaded_urls.json')
TOOL_DIR = r'D:/project/duanxian/tools/下载'

ACCOUNTS = {
    '短线杰哥擒龙': {'biz': 'MzIxMjMxNDUzOQ=='},
    '杰哥擒龙收评': {'biz': 'MzA3NTQyNTM3NQ=='},
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
}

# ========== 已下载URL管理 ==========

def get_downloaded_urls():
    if os.path.exists(DOWNLOADED_URLS):
        with open(DOWNLOADED_URLS, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def mark_downloaded(url):
    urls = get_downloaded_urls()
    urls.add(url)
    with open(DOWNLOADED_URLS, 'w', encoding='utf-8') as f:
        json.dump(list(urls), f, ensure_ascii=False)

# ========== 文章处理 ==========

def extract_article_info(html, source=''):
    soup = BeautifulSoup(html, 'html.parser')
    title = ''
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title = og_title['content'].strip()
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text().strip()
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            title = re.sub(r'\s+', ' ', title_tag.get_text().strip()).strip()

    date_compact = ''
    ct_match = re.search(r'var\s+ct\s*=\s*["\'](\d+)["\']', html)
    if ct_match:
        dt = datetime.fromtimestamp(int(ct_match.group(1)))
        date_compact = dt.strftime('%Y%m%d')
    if not date_compact:
        ts_match = re.search(r'timestamp=(\d{10})', html)
        if ts_match:
            dt = datetime.fromtimestamp(int(ts_match.group(1)))
            date_compact = dt.strftime('%Y%m%d')

    biz = ''
    biz_match = re.search(r'__biz=([^&"\']+)', html)
    if biz_match:
        biz = biz_match.group(1).strip()

    is_verify = ('secitptpage/verify' in html[:5000] or '请确认' in html[:5000])
    has_content = bool(soup.find('div', class_='rich_media_content') or
                       soup.find(id='js_content'))

    return {'title': title, 'date': date_compact, 'biz': biz,
            'is_verify': is_verify, 'has_content': has_content}


def detect_dir(info):
    if info['biz']:
        for name, a in ACCOUNTS.items():
            if info['biz'] == a['biz']:
                return os.path.join(ROOT, name)
    unknown = os.path.join(ROOT, 'other_articles')
    os.makedirs(unknown, exist_ok=True)
    return unknown


def make_filename(date_compact, title):
    clean = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    if not clean:
        clean = '无标题'
    if len(clean) > 60:
        clean = clean[:60]
    mmdd = date_compact[4:8] if len(date_compact) >= 8 else date_compact
    return f'{date_compact}_{mmdd}{clean}.html'


def save_html(html, info):
    target_dir = detect_dir(info)
    os.makedirs(target_dir, exist_ok=True)
    filename = make_filename(info['date'], info['title'])
    filepath = os.path.join(target_dir, filename)
    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        for i in range(2, 100):
            filepath = os.path.join(target_dir, f'{base}_{i}{ext}')
            if not os.path.exists(filepath):
                break
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    return filepath

# ========== 从历史文章页获取URL列表 ==========

async def get_article_urls_from_history(page, biz):
    """从公众号历史文章页提取所有文章URL"""
    url = f'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={biz}&scene=124#wechat_redirect'
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.wait_for_timeout(5000)

    # 检查是否需要登录
    content = await page.content()
    if '请点击确认' in content[:3000] or '二维码' in content[:3000]:
        print('  [需要扫码登录] 请在浏览器中扫描二维码...')
        await page.wait_for_timeout(30000)  # 等待30秒扫码
        await page.wait_for_timeout(3000)

    # 滚动加载更多文章
    print('  [加载文章列表] 滚动加载中...')
    for i in range(5):
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(2000)

    # 提取文章链接
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')
    links = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '__biz=' in href and 'mid=' in href:
            full_url = href if href.startswith('http') else 'https://mp.weixin.qq.com' + href
            links.add(full_url)

    return list(links)


async def download_article(page, url):
    """下载单篇文章"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        try:
            await page.wait_for_selector('.rich_media_content, #js_content', timeout=15000)
        except:
            pass
        await page.wait_for_timeout(2000)
        html = await page.content()
        return html
    except Exception as e:
        print(f'    [失败] {e}')
        return None


async def run_browser_download():
    """主流程：打开浏览器下载新文章"""
    from playwright.async_api import async_playwright

    existing = get_downloaded_urls()
    new_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800}, user_agent=HEADERS['User-Agent'])

        # 恢复保存的登录状态
        if os.path.exists(STATE_FILE) and '--re-login' not in sys.argv:
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                await context.add_cookies(state.get('cookies', []))
                print('[复用上次登录状态]')
            except:
                print('[状态文件损坏，需要重新登录]')
        else:
            print('[首次运行或重新登录]')

        page = await context.new_page()

        for name, info in ACCOUNTS.items():
            print(f'\n{name}:')
            try:
                urls = await get_article_urls_from_history(page, info['biz'])
            except Exception as e:
                print(f'  [获取文章列表失败] {e}')
                continue

            print(f'  找到 {len(urls)} 篇文章')

            # 过滤未下载的
            new_urls = [u for u in urls if u not in existing]
            print(f'  新文章: {len(new_urls)} 篇')

            for url in new_urls:
                print(f'  下载: {url[:60]}...', end=' ')
                html = await download_article(page, url)
                if not html:
                    print('[跳过]')
                    continue

                info = extract_article_info(html, url)
                if info.get('is_verify') or not info.get('has_content') or not info['title']:
                    print('[内容无效]')
                    continue

                filepath = save_html(html, info)
                mark_downloaded(url)
                print(f'OK → {os.path.basename(filepath)}')
                new_count += 1

        # 保存登录状态
        state = {
            'cookies': await context.cookies(),
            'timestamp': datetime.now().isoformat(),
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        print(f'\n[登录状态已保存]')

        await browser.close()

    return new_count

# ========== 从工具目录同步 ==========

def sync_from_tool():
    """从微信公众号批量下载工具目录同步新文章"""
    tool_accounts = {
        '短线杰哥擒龙': os.path.join(TOOL_DIR, '短线杰哥擒龙'),
        '杰哥擒龙收评': os.path.join(TOOL_DIR, '杰哥擒龙收评'),
    }

    total = 0
    for name, tool_dir in tool_accounts.items():
        if not os.path.exists(tool_dir):
            continue
        repo_dir = os.path.join(ROOT, name)
        os.makedirs(repo_dir, exist_ok=True)

        # 已存在的日期
        existing_dates = set()
        for fname in os.listdir(repo_dir):
            m = re.match(r'(\d{8})', fname)
            if m:
                existing_dates.add(m.group(1))

        copied = 0
        for fname in sorted(os.listdir(tool_dir)):
            if not fname.endswith('.html'):
                continue
            m = re.match(r'\[(\d{8})\d{4}\](.+)\.html$', fname)
            if not m:
                continue
            article_date = m.group(1)
            if article_date in existing_dates:
                continue

            title = m.group(2)
            src = os.path.join(tool_dir, fname)
            mmdd = article_date[4:8]
            clean_title = re.sub(r'[\\/:*?"<>|]', '', title)[:60]
            new_fname = f'{article_date}_{mmdd}{clean_title}.html'
            dst = os.path.join(repo_dir, new_fname)
            if os.path.exists(dst):
                continue

            import shutil
            shutil.copy2(src, dst)
            print(f'  [同步] {new_fname}')
            copied += 1

        if copied:
            print(f'  {name}: {copied} 篇')
        total += copied

    return total

# ========== 策略评分（与run_backtest.py一致） ==========

def strategy_score(ctx):
    score = 0
    if any(kw in ctx for kw in ['龙头', '核心', '辨识度', '前排', '阵眼', '总龙头',
                                  '板块龙头', '补涨龙', '趋势龙头', '高标']):
        score += 3
    if any(kw in ctx for kw in ['低吸', '关注', '看好', '分歧低吸', '反核',
                                  '打板', '回封', '弱转强']):
        score += 2
    if any(kw in ctx for kw in ['去弱存强', '切核心', '聚焦核心']):
        score += 1
    if any(kw in ctx for kw in ['修复', '回暖', '企稳', '反弹']):
        score += 1
    if any(kw in ctx for kw in ['分歧', '冰点']):
        score += 1
    if any(kw in ctx for kw in ['跟风', '杂毛', '后排', '补跌', '风险',
                                  '亏钱效应', 'A杀', '退潮', '出货']):
        score -= 2
    if any(kw in ctx for kw in ['卖出', '止损', '出局', '回避']):
        score -= 1
    return score


# ========== 生成stocklist ==========

def generate_stocklist():
    """从最新信号生成stocklist文件"""
    signals_path = os.path.join(ROOT, 'stock_signals.json')
    if not os.path.exists(signals_path):
        print('  [stocklist] stock_signals.json 不存在，跳过')
        return None

    with open(signals_path, 'r', encoding='utf-8') as f:
        signals = json.load(f)

    dates = sorted(set(s['date'] for s in signals))
    latest_date = dates[-1]
    today_signals = [s for s in signals if s['date'] == latest_date]

    fan_markers = ['杰哥，', '杰哥：', '杰哥、', '杰哥:', '请教', '请问', '杰哥你好', '杰哥好']
    non_fan = [s for s in today_signals if not any(m in s['context'] for m in fan_markers)]

    scored = [(strategy_score(s['context']), s) for s in non_fan]
    scored.sort(key=lambda x: -x[0])
    selected = scored[:5]

    # 评分关键词映射
    score_keywords = {
        3: ['龙头', '核心', '辨识度', '前排', '阵眼', '高标'],
        2: ['低吸', '关注', '看好', '分歧低吸', '反核', '打板', '弱转强'],
        1: ['去弱存强', '切核心', '聚焦核心', '修复', '回暖', '企稳', '分歧', '冰点'],
    }

    date_compact = latest_date.replace('-', '')
    stocklist_path = os.path.join(ROOT, f'{date_compact}.stocklist')
    with open(stocklist_path, 'w', encoding='utf-8') as f:
        f.write(f'# {latest_date} 策略选股组合\n')
        f.write('# 策略: 隔日超短+止损-5%（实算-6%）\n')
        f.write('# 评分规则: 龙头核心+3 买入信号+2 修复分歧+1 弱势风险-2\n')
        f.write('\n')
        for rank, (score, s) in enumerate(selected, 1):
            ctx = s['context']

            # 提取触发评分的关键词
            matched = []
            for pts, kws in score_keywords.items():
                for kw in kws:
                    if kw in ctx:
                        matched.append(kw)
                        break  # 每档取一个

            # 提取股票名称附近的上下文作为理由
            name = s['stock_name']
            idx = ctx.find(name)
            if idx >= 0:
                start = max(0, idx - 15)
                end = min(len(ctx), idx + len(name) + 40)
                reason = ctx[start:end].replace('\n', ' ')
            else:
                reason = ctx[:60].replace('\n', ' ')

            kw_str = f' [{",".join(matched)}]' if matched else ''
            f.write(f'{s["stock_code"]} {s["stock_name"]}  评分:{score}{kw_str}\n')
            f.write(f'    理由: {reason}\n')
            f.write('\n')

    print(f'  [stocklist] 已生成 {stocklist_path} ({len(selected)}只股票)')
    return stocklist_path


def git_push(filepath):
    """提交并推送指定文件到git"""
    repo = ROOT
    try:
        subprocess.run(['git', 'add', filepath], cwd=repo, capture_output=True)
        date_str = datetime.now().strftime('%Y%m%d')
        result = subprocess.run(
            ['git', 'commit', '-m', f'每日更新: {date_str} 策略选股组合'],
            cwd=repo, capture_output=True, text=True
        )
        if 'nothing to commit' in result.stdout or 'nothing to commit' in result.stderr:
            print('  [git] 无变更需要提交')
            return
        subprocess.run(['git', 'push'], cwd=repo, capture_output=True)
        print(f'  [git] 已推送 {os.path.basename(filepath)}')
    except Exception as e:
        print(f'  [git] 错误: {e}')


def git_push_with_msg(filepath, msg):
    """提交并推送指定文件到git，自定义提交信息"""
    repo = ROOT
    try:
        subprocess.run(['git', 'add', filepath], cwd=repo, capture_output=True)
        result = subprocess.run(
            ['git', 'commit', '-m', msg],
            cwd=repo, capture_output=True, text=True
        )
        if 'nothing to commit' in result.stdout or 'nothing to commit' in result.stderr:
            print('  [git] 无变更需要提交')
            return
        subprocess.run(['git', 'push'], cwd=repo, capture_output=True)
        print(f'  [git] 已推送 {os.path.basename(filepath)}')
    except Exception as e:
        print(f'  [git] 错误: {e}')


# ========== 生成重点摘要 ==========

def generate_keypoints():
    """从最新文章中提取提及主线的段落"""
    from bs4 import BeautifulSoup
    import glob
    from datetime import timedelta

    today = datetime.now()
    dates_to_check = [(today - timedelta(days=i)).strftime('%Y%m%d') for i in range(3)]

    keypoints = []
    for dirname in ['短线杰哥擒龙', '杰哥擒龙收评']:
        base = os.path.join(ROOT, dirname)
        if not os.path.exists(base):
            continue
        for f in sorted(glob.glob(os.path.join(base, '*.html'))):
            fname = os.path.basename(f)
            if not any(d in fname for d in dates_to_check):
                continue
            with open(f, 'r', encoding='utf-8') as fh:
                html = fh.read()
            soup = BeautifulSoup(html, 'html.parser')
            content = soup.find('div', class_='rich_media_content') or soup.find(id='js_content')
            if not content:
                continue
            text = content.get_text(separator='\n', strip=True)

            title = ''
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()
            if not title:
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text().strip()

            lines = text.split('\n')
            for i, line in enumerate(lines):
                if '主线' in line or '赚钱效应' in line:
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    excerpt = '\n'.join(lines[start:end]).strip()
                    if len(excerpt) > 10:
                        tag = '主线' if '主线' in line else '赚钱效应'
                        keypoints.append({
                            'account': dirname,
                            'title': title or fname,
                            'excerpt': excerpt,
                            'tag': tag,
                        })
                    break

    date_compact = today.strftime('%Y%m%d')
    path = os.path.join(ROOT, f'{date_compact}.重点.txt')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {today.strftime("%Y-%m-%d")} 盘面要点梳理\n')
        f.write(f'# 提取自最近3天公众号文章\n')
        f.write('\n')
        if not keypoints:
            f.write('最近3天文章未提及"主线"或"赚钱效应"\n')
        else:
            for kp in keypoints:
                f.write(f'## [{kp["tag"]}] [{kp["account"]}] {kp["title"]}\n')
                f.write(f'{kp["excerpt"]}\n')
                f.write('\n')

    print(f'  [重点] 已生成 {os.path.basename(path)} ({len(keypoints)}条主线/赚钱效应)')
    return path


# ========== 管道 ==========

def run_pipeline():
    print('\n' + '=' * 50)
    print('  提取信号...')
    print('=' * 50)
    extract_script = os.path.join(ROOT, 'extract_signals.py')
    if os.path.exists(extract_script):
        subprocess.run([sys.executable, extract_script], cwd=ROOT)

    print('\n' + '=' * 50)
    print('  运行回测...')
    print('=' * 50)
    backtest_script = os.path.join(ROOT, 'run_backtest.py')
    if os.path.exists(backtest_script):
        subprocess.run([sys.executable, backtest_script], cwd=ROOT)

    print('\n' + '=' * 50)
    print('  生成持仓报告...')
    print('=' * 50)
    pos_script = os.path.join(ROOT, 'build_daily_positions.py')
    if os.path.exists(pos_script):
        subprocess.run([sys.executable, pos_script], cwd=ROOT)

    print('\n' + '=' * 50)
    print('  生成stocklist + 推送git...')
    print('=' * 50)
    stocklist_path = generate_stocklist()
    if stocklist_path:
        git_push(stocklist_path)

    print('\n' + '=' * 50)
    print('  提取主线要点 + 推送git...')
    print('=' * 50)
    keypoints_path = generate_keypoints()
    if keypoints_path:
        date_str = datetime.now().strftime('%Y%m%d')
        git_push_with_msg(keypoints_path, f'每日更新: {date_str} 主线梳理')


# ========== 主入口 ==========

def main():
    only_sync = '--sync-only' in sys.argv
    only_pipeline = '--pipeline' in sys.argv

    # 日志记录
    log_path = os.path.join(ROOT, f'auto_update_{datetime.now().strftime("%Y%m%d")}.log')
    log_file = open(log_path, 'w', encoding='utf-8')

    def log(msg=''):
        print(msg)
        log_file.write(msg + '\n')
        log_file.flush()

    log('=' * 50)
    log(f'自动更新: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log('=' * 50)

    if only_pipeline:
        log('只运行管道...')
        run_pipeline()
        log('\n完成!')
        log_file.close()
        return

    if only_sync:
        log('从工具目录同步...')
        n = sync_from_tool()
        log(f'\n同步 {n} 篇新文章')
        run_pipeline()
        log('\n完成!')
        log_file.close()
        return

    # 1. 先同步工具目录
    log('=== 步骤1: 同步工具目录 ===')
    n = sync_from_tool()
    log(f'工具目录同步: {n} 篇')

    # 2. 再用浏览器下载最新
    log('\n=== 步骤2: 浏览器下载最新文章 ===')
    log('(浏览器窗口会自动弹出，扫码登录后自动下载)')
    try:
        new_count = asyncio.run(run_browser_download())
        log(f'\n浏览器下载: {new_count} 篇')
    except ImportError:
        log('Playwright 未安装，跳过浏览器下载')
        log('安装: pip install playwright && python -m playwright install chromium')
        new_count = 0
    except Exception as e:
        log(f'浏览器下载异常: {e}')
        new_count = 0

    # 3. 运行管道
    if n > 0 or new_count > 0 or only_pipeline:
        log('\n=== 步骤3: 运行管道 ===')
        run_pipeline()

    log(f'\n完成! 更新 {n + new_count} 篇')
    log_file.close()


if __name__ == '__main__':
    main()
