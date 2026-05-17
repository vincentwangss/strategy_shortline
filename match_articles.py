import os, re, json
from collections import defaultdict

# Build a complete date->filenames map from ALL article directories
date_articles = defaultdict(list)  # date -> [(filename, source_dir)]

tool_dirs = [
    r'D:/tools/微信公众号批量下载工具3.7',
    r'D:/tools/微信公众号批量下载工具3.8',
    r'D:/project/duanxian/tools',
]

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
                # Try multiple date formats
                m = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', f)
                if m:
                    date = m.group(1)
                    date_articles[date].append((f, sub, os.path.basename(tool_dir)))
                    continue
                # Try YYYYMMDD format (no dashes)
                m = re.match(r'\[(\d{8})', f)
                if m:
                    d = m.group(1)
                    date = f'{d[:4]}-{d[4:6]}-{d[6:8]}'
                    date_articles[date].append((f, sub, os.path.basename(tool_dir)))

print(f'扫描完成: {len(date_articles)}个日期有文章')
total = sum(len(v) for v in date_articles.values())
print(f'共{total}篇文章')

# Load signals
with open(r'D:/杰哥复盘数据/stock_signals.json', 'r', encoding='utf-8') as f:
    signals = json.load(f)

# Match signals with articles by date
matched = 0
unmatched = defaultdict(set)
for s in signals:
    date = s['date']
    if date in date_articles:
        articles = date_articles[date]
        # Pick the best match: prefer non-公众号 if possible
        non_gh = [a for a in articles if a[1] != '公众号']
        if non_gh:
            s['article'] = non_gh[0][0]
        else:
            s['article'] = articles[0][0]
        matched += 1
    else:
        s['article'] = 'unknown'
        unmatched[date].add(s['account'])

# Save
with open(r'D:/杰哥复盘数据/stock_signals.json', 'w', encoding='utf-8') as f:
    json.dump(signals, f, ensure_ascii=False, indent=2)

print(f'匹配成功: {matched}/{len(signals)}')
if unmatched:
    print(f'仍有{len(unmatched)}个日期未匹配:')
    for d in sorted(unmatched)[:15]:
        print(f'  {d} ({unmatched[d]})')

# Show samples
print('\n信号示例:')
for s in signals[:5]:
    print(f'  {s["date"]} | {s["stock_name"]}({s["stock_code"]}) | {s["account"]} | 文章: {s.get("article","?")}')
