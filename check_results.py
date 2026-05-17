import os, re, json

root = 'D:/杰哥复盘数据'

# 1. Count files with/without date prefix
for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    files = os.listdir(d)
    dated = sum(1 for f in files if re.match(r'^\d{8}_', f))
    undated = [f for f in files if not re.match(r'^\d{8}_', f) and f != '下载.lnk']
    print(f'\n=== {acct} ===')
    print(f'  总计: {len(files)} 个文件')
    print(f'  有日期前缀: {dated}')
    print(f'  无日期前缀: {len(undated)}')
    if undated:
        print(f'  无日期文件:')
        for f in undated:
            print(f'    {f}')

# 2. Check abbreviation replacement
print('\n\n=== 简写替换检查 ===')
with open(os.path.join(root, 'abbrev_map.json'), 'r', encoding='utf-8') as f:
    abbrev_map = json.load(f)
print(f'简写映射总数: {len(abbrev_map)}')

# Pick a few sample HTML files and check
sample_files = []
for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    count = 0
    for f in sorted(os.listdir(d)):
        if f.endswith('.html') and re.match(r'^\d{8}_', f) and count < 3:
            sample_files.append(os.path.join(d, f))
            count += 1

for fpath in sample_files:
    fname = os.path.basename(fpath)
    acct = os.path.basename(os.path.dirname(fpath))
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', body)

    still_present = [(a, text.count(a)) for a in abbrev_map if a in text]
    full_names = [(abbrev_map[a], text.count(abbrev_map[a])) for a in abbrev_map if abbrev_map[a] in text]

    print(f'\n--- {acct}/{fname[:50]} ---')
    if still_present:
        print(f'  仍存在的简写: {still_present[:5]}')
    else:
        print(f'  所有简写已被替换')
    if full_names:
        print(f'  全名出现: {sorted(set(n for n,c in full_names), key=lambda x: -text.count(x))[:5]}')

# 3. Check 有研新材 specifically
print('\n\n=== 专门检查: 有研新材 ===')
for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    found = False
    for f in sorted(os.listdir(d)):
        if not f.endswith('.html'):
            continue
        fpath = os.path.join(d, f)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        if '有研' in content:
            body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', body)
            has_abbr = '有研XC' in text
            has_full = '有研新材' in text
            if has_full or has_abbr:
                idx = text.find('有研新材') if has_full else text.find('有研XC')
                ctx = text[max(0,idx-15):idx+25]
                status = 'OK' if has_full and not has_abbr else 'ISSUE'
                print(f'  [{status}] {acct}/{f[:50]}: 有研新材={has_full}, 有研XC={has_abbr}')
                print(f'    上下文: ...{ctx}...')
                found = True
                break
    if not found:
        print(f'  {acct}: 未找到含有研的文章')

# 4. Read the undated files list
print('\n\n=== 无日期文件 ===')
undated_path = os.path.join(root, 'undated_files.txt')
if os.path.exists(undated_path):
    with open(undated_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    lines = content.split('\n')
    print(f'共 {len(lines)} 个无日期文件:')
    for line in lines:
        print(f'  {line}')
