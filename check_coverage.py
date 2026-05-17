import os, re, json
from collections import defaultdict, Counter

# 1) 统计所有来源的文章数量（按月）
tool_dirs = [
    r'D:/tools/微信公众号批量下载工具3.7',
    r'D:/tools/微信公众号批量下载工具3.8',
    r'D:/project/duanxian/tools',
]

articles_by_month = defaultdict(int)
articles_by_source = defaultdict(int)

for tool_dir in tool_dirs:
    if not os.path.exists(tool_dir):
        continue
    for item in os.listdir(tool_dir):
        cache_dir = os.path.join(tool_dir, item)
        if not os.path.isdir(cache_dir):
            continue
        for sub in os.listdir(cache_dir):
            account_dir = os.path.join(cache_dir, sub)
            if not os.path.isdir(account_dir):
                continue
            for f in os.listdir(account_dir):
                if not (f.endswith('.html') or f.endswith('.htm')):
                    continue
                m = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', f)
                if m:
                    ym = m.group(1)[:7]
                    articles_by_month[ym] += 1
                    articles_by_source[sub] += 1
                    continue
                m = re.match(r'\[(\d{4})(\d{2})(\d{2})', f)
                if m:
                    ym = f'{m.group(1)}-{m.group(2)}'
                    articles_by_month[ym] += 1
                    articles_by_source[sub] += 1

print('=== 各月文章数量（全部来源）===')
for ym in sorted(articles_by_month):
    if ym >= '2024':
        print(f'  {ym}: {articles_by_month[ym]}篇')

print(f'\n=== 各来源文章总量 ===')
for src in sorted(articles_by_source, key=articles_by_source.get, reverse=True):
    print(f'  {src}: {articles_by_source[src]}篇')

# 2) 按公众号账号分
print('\n=== 各账号按月份统计 ===')
account_month = defaultdict(lambda: defaultdict(int))
for tool_dir in tool_dirs:
    if not os.path.exists(tool_dir):
        continue
    for item in os.listdir(tool_dir):
        cache_dir = os.path.join(tool_dir, item)
        if not os.path.isdir(cache_dir):
            continue
        for sub in os.listdir(cache_dir):
            account_dir = os.path.join(cache_dir, sub)
            if not os.path.isdir(account_dir):
                continue
            for f in os.listdir(account_dir):
                if not (f.endswith('.html') or f.endswith('.htm')):
                    continue
                m = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', f)
                if m:
                    ym = m.group(1)[:7]
                    account_month[sub][ym] += 1
                    continue
                m = re.match(r'\[(\d{4})(\d{2})(\d{2})', f)
                if m:
                    ym = f'{m.group(1)}-{m.group(2)}'
                    account_month[sub][ym] += 1

for acct in sorted(account_month.keys()):
    print(f'\n  {acct}:')
    for ym in sorted(account_month[acct]):
        if ym >= '2024':
            print(f'    {ym}: {account_month[acct][ym]}篇')

# 3) 对比信号提取覆盖度
with open(r'D:/杰哥复盘数据/stock_signals.json', 'r', encoding='utf-8') as f:
    signals = json.load(f)

signal_months = Counter()
for s in signals:
    ym = s['date'][:7]
    signal_months[ym] += 1

print('\n=== 信号提取覆盖度 ===')
print(f'{"月份":>8} {"文章":>6} {"信号":>6} {"信号/篇":>8}')
for ym in sorted(articles_by_month):
    if ym >= '2024':
        arts = articles_by_month.get(ym, 0)
        sigs = signal_months.get(ym, 0)
        ratio = sigs/arts if arts else 0
        print(f'  {ym:>8} {arts:>6} {sigs:>6} {ratio:>7.2f}')
