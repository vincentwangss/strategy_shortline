"""
微信公众号文章下载 + 信号提取 + 回测
====================================

自动下载：使用 Playwright 打开真实浏览器，自动获取文章内容
支持导入：从本地导入已保存的 HTML 文件

用法:
  # 下载单篇文章（会弹出浏览器窗口）
  python fetch_latest_articles.py --url "https://mp.weixin.qq.com/s/..."

  # 从文件批量下载
  python fetch_latest_articles.py --file urls.txt

  # 手动输入URL
  python fetch_latest_articles.py --manual

  # 导入本地HTML文件
  python fetch_latest_articles.py --import "文章.html"

  # 只下载，不提取信号/回测
  python fetch_latest_articles.py --url <URL> --skip-extract

安装依赖:
  pip install playwright
  python -m playwright install chromium
"""

import asyncio, os, re, time, json, sys, glob
from datetime import datetime
from bs4 import BeautifulSoup

ROOT = r'D:/杰哥复盘数据'
ACCOUNTS = {
    '短线杰哥擒龙': {
        'dir': os.path.join(ROOT, '短线杰哥擒龙'),
        'biz': 'MzIxMjMxNDUzOQ==',
    },
    '杰哥擒龙收评': {
        'dir': os.path.join(ROOT, '杰哥擒龙收评'),
        'biz': 'MzA3NTQyNTM3NQ==',
    },
}
DOWNLOADS_FILE = os.path.join(ROOT, '.downloaded_urls.json')

for info in ACCOUNTS.values():
    os.makedirs(info['dir'], exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


# ========== 工具函数 ==========

def get_downloaded_urls():
    if os.path.exists(DOWNLOADS_FILE):
        with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def mark_downloaded(url):
    urls = get_downloaded_urls()
    urls.add(url)
    with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(urls), f, ensure_ascii=False)


def extract_article_info(html, source=''):
    """从HTML中提取文章元信息"""
    soup = BeautifulSoup(html, 'html.parser')

    # 标题
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
    if not title or title in ('微信公众号平台', ''):
        title = ''

    # 日期
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

    # 从文件名提取
    if not date_compact and source:
        fname = os.path.basename(source)
        name_match = re.match(r'(\d{8})', fname)
        if name_match:
            date_compact = name_match.group(1)

    if not date_compact:
        date_compact = datetime.now().strftime('%Y%m%d')

    # biz
    biz = ''
    biz_match = re.search(r'__biz=([^&"\']+)', html)
    if biz_match:
        biz = biz_match.group(1).strip()

    # 检查是否是验证页
    is_verify = ('secitptpage/verify' in html[:5000] or
                 '请确认' in html[:5000])

    # 检查是否有真实文章内容
    has_content = bool(soup.find('div', class_='rich_media_content') or
                       soup.find(id='js_content'))

    return {
        'title': title,
        'date': date_compact,
        'biz': biz,
        'is_verify': is_verify,
        'has_content': has_content,
    }


def detect_dir(info, filepath=''):
    """判断文章归属哪个公众号目录"""
    if info['biz']:
        for name, a in ACCOUNTS.items():
            if info['biz'] == a['biz']:
                return a['dir']

    if filepath:
        basename = os.path.basename(filepath).lower()
        for name, a in ACCOUNTS.items():
            if name in basename:
                return a['dir']

    unknown = os.path.join(ROOT, 'other_articles')
    os.makedirs(unknown, exist_ok=True)
    return unknown


def make_filename(date_compact, title):
    """生成标准文件名"""
    clean = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    if not clean:
        clean = '无标题'
    if len(clean) > 60:
        clean = clean[:60]
    mmdd = date_compact[4:8] if len(date_compact) >= 8 else date_compact
    return f'{date_compact}_{mmdd}{clean}.html'


def save_html_file(html, info, target_dir):
    """保存HTML到目标目录"""
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


# ========== Playwright 下载 ==========

async def download_with_playwright(url):
    """使用 Playwright 打开浏览器下载文章"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print('  Playwright 未安装，请运行:')
        print('  pip install playwright && python -m playwright install chromium')
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            # 等待文章内容加载
            try:
                await page.wait_for_selector('.rich_media_content, #js_content',
                                             timeout=15000)
            except:
                pass
            await page.wait_for_timeout(2000)

            html = await page.content()
            title = await page.title()

            info = extract_article_info(html, url)
            info['title'] = info['title'] or title

            await browser.close()
            return html, info

        except Exception as e:
            print(f'  页面加载异常: {e}')
            await browser.close()
            return None


def download_with_playwright_sync(url):
    """同步包装"""
    return asyncio.run(download_with_playwright(url))


# ========== 下载 / 导入模式 ==========

def process_one_url(url, skip_extract=False, skip_backtest=False):
    """下载单篇文章"""
    existing = get_downloaded_urls()
    if url in existing:
        print(f'  跳过(已下载)')
        return True

    print(f'  启动浏览器下载... (浏览器窗口会自动关闭)')
    result = download_with_playwright_sync(url)
    if not result:
        return False

    html, info = result

    if info.get('is_verify') or not info.get('has_content'):
        print(f'  遇到验证页，请在浏览器中手动完成验证')
        return False

    if not info['title']:
        print(f'  无法提取标题')
        return False

    target_dir = detect_dir(info, url)
    filepath = save_html_file(html, info, target_dir)
    mark_downloaded(url)

    account_name = [n for n, a in ACCOUNTS.items() if a['dir'] == target_dir]
    account_name = account_name[0] if account_name else '其他'
    print(f'  OK [{account_name}] {os.path.basename(filepath)}')
    return True


def process_import_file(filepath, skip_extract=False, skip_backtest=False):
    """导入本地HTML文件"""
    if not os.path.exists(filepath):
        print(f'  文件不存在')
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    if len(html) < 1000:
        print(f'  文件过小({len(html)} bytes)')
        return False

    info = extract_article_info(html, filepath)

    is_wechat = ('mp.weixin.qq.com' in html[:5000] or
                 '__biz' in html[:5000] or
                 info['biz'])
    if not is_wechat:
        print(f'  不是微信公众号文章')
        return False

    target_dir = detect_dir(info, filepath)
    if not info['title']:
        basename = os.path.splitext(os.path.basename(filepath))[0]
        info['title'] = re.sub(r'^\d{8}_\d{4}', '', basename)[:40] or '导入文章'

    new_filename = make_filename(info['date'], info['title'])
    new_path = os.path.join(target_dir, new_filename)
    if os.path.exists(new_path):
        print(f'  已存在: {new_filename}')
        return True

    import shutil
    shutil.copy2(filepath, new_path)

    account_name = [n for n, a in ACCOUNTS.items() if a['dir'] == target_dir]
    account_name = account_name[0] if account_name else '其他'
    print(f'  OK [{account_name}] {new_filename}')
    return True


def process_import_path(path, skip_extract, skip_backtest):
    """导入文件或文件夹"""
    if os.path.isfile(path):
        return process_import_file(path, skip_extract, skip_backtest)
    elif os.path.isdir(path):
        html_files = glob.glob(os.path.join(path, '*.html'))
        print(f'找到 {len(html_files)} 个HTML文件')
        success = 0
        for f in sorted(html_files):
            basename = os.path.basename(f)
            print(f'  [{success+1}/{len(html_files)}] {basename}', end=' ')
            if process_import_file(f):
                success += 1
            else:
                print()
        print(f'成功: {success}/{len(html_files)}')
        return success > 0


# ========== 信号提取 + 回测 ==========

def run_pipeline(skip_extract, skip_backtest):
    if skip_extract:
        print('\n跳过信号提取和回测')
        return

    print('\n' + '=' * 50)
    print('  提取信号...')
    print('=' * 50)
    if not os.path.exists(os.path.join(ROOT, 'extract_signals.py')):
        print('  未找到 extract_signals.py')
        return

    if os.system(f'cd /d "{ROOT}" && python extract_signals.py') != 0:
        print('  信号提取失败')
        return

    if skip_backtest:
        print('\n跳过回测')
        return

    print('\n' + '=' * 50)
    print('  运行回测...')
    print('=' * 50)
    os.system(f'cd /d "{ROOT}" && python run_backtest.py')

    print('\n' + '=' * 50)
    print('  生成持仓报告...')
    print('=' * 50)
    os.system(f'cd /d "{ROOT}" && python build_daily_positions.py')
    print(f'\n完成! 结果已更新')


# ========== 命令行 ==========

def usage():
    print(__doc__)


def main():
    skip_extract = '--skip-extract' in sys.argv
    skip_backtest = '--skip-backtest' in sys.argv
    for flag in ['--skip-extract', '--skip-backtest']:
        if flag in sys.argv:
            sys.argv.remove(flag)

    if len(sys.argv) <= 1:
        usage()
        return

    cmd = sys.argv[1]
    has_new = False

    if cmd == '--url' and len(sys.argv) > 2:
        for url in sys.argv[2:]:
            print(f'\nURL: {url[:80]}')
            if process_one_url(url, skip_extract, skip_backtest):
                has_new = True
            time.sleep(2)

    elif cmd == '--file' and len(sys.argv) > 2:
        filepath = sys.argv[2]
        if not os.path.exists(filepath):
            print(f'文件不存在: {filepath}')
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip().startswith('http')]
        print(f'从文件读取 {len(urls)} 个URL')
        for i, url in enumerate(urls):
            print(f'\n[{i+1}/{len(urls)}]', end=' ')
            if process_one_url(url, skip_extract, skip_backtest):
                has_new = True
            time.sleep(2)

    elif cmd == '--import' and len(sys.argv) > 2:
        for path in sys.argv[2:]:
            print(f'\n导入: {path}')
            if process_import_path(path, skip_extract, skip_backtest):
                has_new = True

    elif cmd == '--manual':
        print('输入文章URL（空行结束）:')
        urls = []
        while True:
            url = input('URL > ').strip()
            if not url:
                break
            if url.startswith('http'):
                urls.append(url)
        for url in urls:
            print(f'\nURL: {url[:80]}')
            if process_one_url(url, skip_extract, skip_backtest):
                has_new = True
            time.sleep(2)

    else:
        usage()
        return

    if has_new:
        run_pipeline(skip_extract, skip_backtest)


if __name__ == '__main__':
    main()
