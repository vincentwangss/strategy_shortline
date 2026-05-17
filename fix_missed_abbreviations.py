import os, re, json
from collections import Counter

root = 'D:/杰哥复盘数据'

# Load stock name map
with open(os.path.join(root, 'stock_name_map.json'), 'r', encoding='utf-8') as f:
    name_map = json.load(f)
all_names = list(name_map.keys())

# Also load existing abbrev map
with open(os.path.join(root, 'abbrev_map.json'), 'r', encoding='utf-8') as f:
    existing_map = json.load(f)

print(f'现有 {len(existing_map)} 条映射, {len(all_names)} 只股票')
print('扫描正文中的中文+字母模式...')

# ===== Scan all files for patterns =====
all_text = ''
file_count = 0
for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    for f in os.listdir(d):
        if not f.endswith('.html'):
            continue
        file_count += 1
        fpath = os.path.join(d, f)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        all_text += text + '\n'

print(f'扫描 {file_count} 个HTML文件')

# ===== Find patterns =====
# Pattern 1: Chinese(2-4) + single uppercase letter
pat1 = re.findall(r'([一-鿿]{2,4})([A-Z])', all_text)
cnt1 = Counter(pat1)

# Pattern 2: Chinese(2-4) + double uppercase letters
pat2 = re.findall(r'([一-鿿]{2,4})([A-Z]{2})', all_text)
cnt2 = Counter(pat2)

# Pattern 3: Chinese(2-4) + lowercase pinyin (2-3 letters, common stock suffixes)
pat3 = re.findall(r'([一-鿿]{2,4})([a-z]{2,3})', all_text)
cnt3 = Counter(pat3)

print(f'\n大写单字母模式: {len(cnt1)}')
print(f'大写双字母模式: {len(cnt2)}')
print(f'小写拼音模式: {len(cnt3)}')

# ===== Build new mappings =====
new_abbrev = {}

def find_best_match(prefix, hint_chars=None):
    """Find the best stock name matching a prefix"""
    candidates = [n for n in all_names if n.startswith(prefix) and len(n) > len(prefix)]
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # If hint chars available, try to narrow down
        if hint_chars:
            for c in candidates:
                remaining = c[len(prefix):]
                # Check if remaining chars match the hint
                # For uppercase letters: match pinyin initials
                remaining_pinyin = ''
                for ch in remaining:
                    # Get first pinyin letter
                    # Simple: just compare
                    pass
        # Return the most frequent one
        return candidates[0] if candidates else None
    return None

# Process single uppercase
for (prefix, letter), count in cnt1.most_common():
    key = f'{prefix}{letter}'
    if key in existing_map:
        continue  # Already mapped
    candidates = [n for n in all_names if n.startswith(prefix) and len(n) > len(prefix)]
    if len(candidates) == 1:
        new_abbrev[key] = candidates[0]
    elif len(candidates) > 1 and count >= 2:
        # Pick by frequency
        freqs = {n: all_text.count(n) for n in candidates}
        best = max(freqs, key=freqs.get)
        new_abbrev[key] = best

# Process double uppercase
for (prefix, letters), count in cnt2.most_common():
    key = f'{prefix}{letters}'
    if key in existing_map:
        continue
    candidates = [n for n in all_names if n.startswith(prefix) and len(n) > len(prefix)]
    if len(candidates) == 1:
        new_abbrev[key] = candidates[0]
    elif len(candidates) > 1 and count >= 2:
        freqs = {n: all_text.count(n) for n in candidates}
        best = max(freqs, key=freqs.get)
        new_abbrev[key] = best

# Process lowercase pinyin
lowercase_map = {
    'kj': '科技', 'gf': '股份', 'jt': '集团', 'yx': '有限',
    'kg': '控股', 'zb': '资本', 'dz': '电子', 'gk': '光电',
    'dl': '电力', 'sy': '实业', 'ny': '能源', 'hb': '环保',
    'cy': '产业', 'js': '建设', 'xx': '信息', 'tx': '通信',
}
for (prefix, letters), count in cnt3.most_common():
    key = f'{prefix}{letters}'
    if key in existing_map or key in new_abbrev:
        continue
    # Try matching by common suffix mappings
    if letters in lowercase_map:
        suffix = lowercase_map[letters]
        full_name = f'{prefix}{suffix}'
        if full_name in name_map:
            new_abbrev[key] = full_name
        else:
            # Try fuzzy: prefix might be abbrev of first 2 chars
            # e.g. 宏景kj -> 宏景科技, but some use 宏景 -> 宏景科技
            full_name = prefix + suffix
            if full_name in name_map:
                new_abbrev[key] = full_name

# Force-add some known ones
force_add = {
    '工业富L': '工业富联',
    '宏景kj': '宏景科技',
    '韶能gf': '韶能股份',
    '汉缆gf': '汉缆股份',
}
for k, v in force_add.items():
    if k not in existing_map and k not in new_abbrev:
        if v in name_map:
            new_abbrev[k] = v
            print(f'  强制添加: {k} -> {v}')

print(f'\n新增 {len(new_abbrev)} 条映射')

# Show new mappings
print(f'\n新增映射列表:')
for abbr, full in sorted(new_abbrev.items()):
    c = all_text.count(abbr)
    print(f'  {abbr} -> {full} ({c}次)')

# ===== Merge and save =====
merged_map = {**existing_map, **new_abbrev}

# Remove no-op entries (key == value)
merged_map = {k:v for k,v in merged_map.items() if k != v}

with open(os.path.join(root, 'abbrev_map.json'), 'w', encoding='utf-8') as f:
    json.dump(merged_map, f, ensure_ascii=False, indent=2)
print(f'\n合并后共 {len(merged_map)} 条映射')

# ===== Apply replacements =====
print('\n=== 开始替换 ===')
replacements = sorted(merged_map.items(), key=lambda x: -len(x[0]))

total_replaced = 0
file_count_modified = 0
max_show = 5

for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    for f in os.listdir(d):
        if not f.endswith('.html'):
            continue
        fpath = os.path.join(d, f)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except:
            continue

        new_content = content
        file_count_here = 0
        for abbr, full in replacements:
            if abbr in new_content:
                new_content = new_content.replace(abbr, full)
                file_count_here += 1

        if file_count_here > 0:
            with open(fpath, 'w', encoding='utf-8') as fh:
                fh.write(new_content)
            total_replaced += file_count_here
            file_count_modified += 1
            if file_count_modified <= max_show:
                print(f'  {acct}/{f[:50]}: {file_count_here}处替换')

print(f'\n修改 {file_count_modified} 个文件, 共 {total_replaced} 处替换')
print('完成!')
