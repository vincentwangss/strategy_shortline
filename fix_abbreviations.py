import os, re, json
from collections import Counter

# Load stock name map
with open('D:/杰哥复盘数据/stock_name_map.json', 'r', encoding='utf-8') as f:
    name_map = json.load(f)

# Stock names as list
all_names = list(name_map.keys())

# Scan all articles
all_text = ''
root = 'D:/杰哥复盘数据'
html_count = 0
for entry in os.scandir(root):
    if not entry.is_dir() or entry.name == 'price_data':
        continue
    d = entry.path
    for f in os.listdir(d):
        if not f.endswith('.html'):
            continue
        html_count += 1
        try:
            with open(os.path.join(d,f), 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        all_text += text + '\n'

print(f'扫描 {html_count} 个HTML文件')

# Find Chinese(2-4) + single uppercase letter patterns
pat1 = re.findall(r'([一-鿿]{2,4})([A-Z])', all_text)
cnt1 = Counter(pat1)

abbrev_map = {}

for (cn_prefix, letter), count in cnt1.most_common():
    if count < 2:
        continue

    # Find stock names that start with cn_prefix
    candidates = [n for n in all_names if n.startswith(cn_prefix) and len(n) > len(cn_prefix)]

    if len(candidates) == 1:
        # Only one possible match
        abbrev_map[f'{cn_prefix}{letter}'] = candidates[0]
    elif len(candidates) > 1:
        # Multiple candidates - see if we can narrow down
        # Try: remaining chars must not start with 大写 (A-Z letter)
        # e.g. for cn="深振", candidates=["深振业A"], and letter="Y" -> 深振业 (ye)
        filtered = []
        for c in candidates:
            remaining = c[len(cn_prefix):]
            filtered.append(c)

        if len(filtered) == 1:
            abbrev_map[f'{cn_prefix}{letter}'] = filtered[0]
        else:
            # Multiple matches - pick the most frequent one in articles
            freqs = {n: all_text.count(n) for n in filtered}
            best = max(freqs, key=freqs.get)
            # Only map if the abbreviation is more common than any full name match
            if all_text.count(f'{cn_prefix}{letter}') > 0:
                abbrev_map[f'{cn_prefix}{letter}'] = best

# Also check double-letter patterns
pat2 = re.findall(r'([一-鿿]{2,4})([A-Z]{2})', all_text)
cnt2 = Counter(pat2)
for (cn_prefix, letters), count in cnt2.most_common():
    if count < 2:
        continue
    # Single-char prefix + 2 letters: e.g. 有研XC
    candidates = [n for n in all_names if n.startswith(cn_prefix) and len(n) > len(cn_prefix)]
    if len(candidates) == 1:
        abbrev_map[f'{cn_prefix}{letters}'] = candidates[0]
    elif len(candidates) > 1:
        # Try to narrow down by checking which has chars matching the letters
        matching = []
        for c in candidates:
            remaining = c[len(cn_prefix):]
            # Simple check: remaining length vs letters count
            matching.append(c)
        if len(matching) == 1:
            abbrev_map[f'{cn_prefix}{letters}'] = matching[0]

print(f'\n=== 发现 {len(abbrev_map)} 个简写->全名映射 ===')
print(f'\n{"简写":<12} {"全名":<12} {"文本出现":<8} {"说明":<20}')
print('-' * 55)
for abbr, full in sorted(abbrev_map.items()):
    c = all_text.count(abbr)
    # Try to explain: what does the letter stand for
    if len(abbr) - len(full) == 0:
        # 1 letter maps to 1 char
        full_part = full[len(abbr)-1:]
        note = f'{abbr[-1]}=>{full_part}' if full_part else ''
    else:
        note = ''
    print(f'  {abbr:<12} {full:<12} {c:<8} {note}')

# Save
with open('D:/杰哥复盘数据/abbrev_map.json', 'w', encoding='utf-8') as f:
    json.dump(abbrev_map, f, ensure_ascii=False, indent=2)
print(f'\n已保存 abbrev_map.json')
