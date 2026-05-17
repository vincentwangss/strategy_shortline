"""
从微信公众号批量下载工具 同步新文章到复盘数据目录
==================================================

用法: python sync_from_tool.py

流程:
  1. 扫描工具下载目录的新文章
  2. 复制到对应的复盘数据目录
  3. 自动运行信号提取 + 回测 + 持仓报告

工具目录: D:/project/duanxian/tools/下载/
"""

import os, re, shutil, sys, subprocess

ROOT = r'D:/杰哥复盘数据'
TOOL_DIR = r'D:/project/duanxian/tools/下载'

ACCOUNTS = {
    '短线杰哥擒龙': {
        'tool_dir': os.path.join(TOOL_DIR, '短线杰哥擒龙'),
        'repo_dir': os.path.join(ROOT, '短线杰哥擒龙'),
    },
    '杰哥擒龙收评': {
        'tool_dir': os.path.join(TOOL_DIR, '杰哥擒龙收评'),
        'repo_dir': os.path.join(ROOT, '杰哥擒龙收评'),
    },
}


def scan_repo_dates(repo_dir):
    """扫描复盘目录已有的文章日期集合"""
    if not os.path.exists(repo_dir):
        return set()
    dates = set()
    for fname in os.listdir(repo_dir):
        if fname.endswith('.html'):
            m = re.match(r'(\d{8})', fname)
            if m:
                dates.add(m.group(1))
    return dates


def sync_account(account_name, info, dry_run=False):
    """同步单个公众号的新文章"""
    tool_dir = info['tool_dir']
    repo_dir = info['repo_dir']
    if not os.path.exists(tool_dir):
        print(f'  [跳过] {account_name}: 工具目录不存在')
        return 0

    os.makedirs(repo_dir, exist_ok=True)
    existing_dates = scan_repo_dates(repo_dir)
    copied = 0

    # 扫描工具目录的HTML文件，按文件名排序（日期顺序）
    html_files = sorted([f for f in os.listdir(tool_dir) if f.endswith('.html')])

    for fname in html_files:
        # 提取日期: [202605150012]标题.html → 20260515
        m = re.match(r'\[(\d{8})\d{4}\](.+)\.html$', fname)
        if not m:
            continue
        article_date = m.group(1)
        title = m.group(2)

        if article_date in existing_dates:
            continue  # 已存在跳过

        src = os.path.join(tool_dir, fname)
        # 生成本地文件名: 20260515_0515标题.html
        mmdd = article_date[4:8]
        clean_title = re.sub(r'[\\/:*?"<>|]', '', title)[:60]
        new_fname = f'{article_date}_{mmdd}{clean_title}.html'
        dst = os.path.join(repo_dir, new_fname)

        if os.path.exists(dst):
            continue

        if dry_run:
            print(f'  [待同步] {article_date}_{clean_title[:30]}...')
        else:
            shutil.copy2(src, dst)
            print(f'  [同步] {new_fname}')
        copied += 1

    return copied


def main():
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print('\n扫描新文章（预览模式）...')
    else:
        print('\n扫描新文章...')

    total = 0
    for name, info in ACCOUNTS.items():
        print(f'\n{name}:')
        c = sync_account(name, info, dry_run)
        print(f'  → {c} 篇新文章')
        total += c

    print(f'\n合计: {total} 篇新文章')

    if total == 0:
        print('没有新文章需要同步')
        return

    if dry_run:
        print('\n去掉 --dry-run 执行实际同步')
        return

    # 运行完整管道
    print('\n' + '=' * 50)
    print('  运行信号提取...')
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

    print(f'\n完成! 共同步 {total} 篇新文章')


if __name__ == '__main__':
    main()
