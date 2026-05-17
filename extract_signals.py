import os, re, json
from collections import OrderedDict

root = 'D:/杰哥复盘数据'

# Load stock name map: name -> [code1, code2, ...]
with open(os.path.join(root, 'stock_name_map.json'), 'r', encoding='utf-8') as f:
    name_map = json.load(f)

# Sort by length descending so longer names match first (e.g. "机器人" before "机器")
stock_names = sorted(name_map.keys(), key=len, reverse=True)

def extract_clean_text(html):
    """Strip HTML tags, scripts, styles, normalize whitespace"""
    body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', body)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', '', text)
    return text

def find_stocks(text):
    """Find all stock names in text, return list of (name, code, position)"""
    found = OrderedDict()
    for name in stock_names:
        idx = 0
        while True:
            idx = text.find(name, idx)
            if idx == -1:
                break
            if name not in found:
                found[name] = []
            found[name].append(idx)
            idx += len(name)
    return found

def get_context(text, pos, name, width=20):
    """Get surrounding context for a stock mention"""
    start = max(0, pos - width)
    end = min(len(text), pos + len(name) + width)
    return text[start:end]

def is_fan_question(ctx):
    """Check if context suggests this is a fan question, not a stock recommendation"""
    markers = ['杰哥，', '杰哥：', '杰哥、', '杰哥:', '请教', '请问', '杰哥你好', '杰哥好']
    return any(m in ctx for m in markers)

# Scan all files
signals = []
total_files = 0
total_stock_mentions = 0
fan_filtered = 0

for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    print(f'扫描 {acct}...')
    for fname in sorted(os.listdir(d)):
        if not fname.endswith('.html'):
            continue

        # Extract date from filename prefix YYYYMMDD
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

        text = extract_clean_text(content)
        if len(text) < 50:
            continue

        total_files += 1
        found = find_stocks(text)

        file_signals = []
        for name, positions in found.items():
            codes = name_map[name]
            if not codes:
                continue
            code = codes[0]  # Primary code

            # Use first occurrence context
            pos = positions[0]
            ctx = get_context(text, pos, name)

            # Check if fan question
            if is_fan_question(ctx):
                fan_filtered += 1
                continue

            file_signals.append({
                'date': date_str,
                'stock_name': name,
                'stock_code': code,
                'account': acct,
                'context': ctx,
            })
            total_stock_mentions += 1

        signals.extend(file_signals)

print(f'\n扫描完成: {total_files} 文件')
print(f'原始信号: {len(signals)}')
print(f'粉丝提问过滤: {fan_filtered}')

# Dedup: same stock_code + same date + same account -> keep first occurrence
seen = set()
deduped = []
for s in signals:
    key = (s['stock_code'], s['date'], s['account'])
    if key not in seen:
        seen.add(key)
        deduped.append(s)

print(f'去重后: {len(deduped)} 信号')

# Save
output = deduped
with open(os.path.join(root, 'stock_signals.json'), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'已保存 stock_signals.json ({len(output)} 条)')

# Quick stats
from collections import Counter
dates = sorted(set(s['date'] for s in output))
accts = Counter(s['account'] for s in output)
print(f'日期范围: {dates[0]} ~ {dates[-1]}')
print(f'账户分布: {dict(accts)}')
