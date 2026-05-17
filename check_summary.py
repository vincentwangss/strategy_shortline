import os, re, json

root = 'D:/杰哥复盘数据'

# 1. Summary by account
print('=' * 60)
print('数据处理结果报告')
print('=' * 60)

for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    files = os.listdir(d)
    dated = sum(1 for f in files if re.match(r'^\d{8}_', f))
    undated = [f for f in files if not re.match(r'^\d{8}_', f) and f != '下载.lnk']
    html_dated = sum(1 for f in files if f.endswith('.html') and re.match(r'^\d{8}_', f))
    md_dated = sum(1 for f in files if f.endswith('.md') and re.match(r'^\d{8}_', f))
    html_undated = sum(1 for f in undated if f.endswith('.html'))
    md_undated = sum(1 for f in undated if f.endswith('.md'))

    print(f'\n--- {acct} ---')
    print(f'  总文件: {len(files)}')
    print(f'  有日期前缀: {dated} (HTML: {html_dated}, MD: {md_dated})')
    print(f'  无日期前缀: {len(undated)} (HTML: {html_undated}, MD: {md_undated})')
    if undated:
        print('  无日期文件列表:')
        for f in undated:
            print(f'    {f}')

# 2. Abbreviation check
print('\n\n--- 简写替换检查 ---')
with open(os.path.join(root, 'abbrev_map.json'), 'r', encoding='utf-8') as f:
    abbrev_map = json.load(f)
print(f'  简写映射总数: {len(abbrev_map)}')

# Check sample files
checked = 0
total_still_present = 0
for acct in ['杰哥擒龙收评', '短线杰哥擒龙']:
    d = os.path.join(root, acct)
    for f in sorted(os.listdir(d)):
        if not f.endswith('.html') or not re.match(r'^\d{8}_', f):
            continue
        if checked >= 5:
            break
        fpath = os.path.join(d, f)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)

        still_present = [a for a in abbrev_map if a in text]
        if still_present:
            print(f'  [注意] {f[:40]}: 仍有 {len(still_present)} 个简写未被替换: {still_present[:5]}')
            total_still_present += len(still_present)
        else:
            print(f'  [OK] {f[:40]}: 所有简写已替换')
        checked += 1
    if checked >= 5:
        break

if total_still_present == 0:
    print(f'  -> 抽样检查全部通过')

# 3. Check 有研新材 specifically
print('\n--- 有研新材 检查 ---')
found_youyan = False
for acct in ['短线杰哥擒龙']:
    d = os.path.join(root, acct)
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
                ctx = text[max(0,idx-10):idx+20]
                status = 'OK' if has_full and not has_abbr else 'NEED_CHECK'
                print(f'  [{status}] {f[:40]}')
                print(f'    上下文: ...{ctx}...')
                found_youyan = True
                break

if not found_youyan:
    print('  未找到含有"有研"的文章')

# 4. Check a few more key abbreviations
print('\n--- 关键简写替换验证 ---')
key_checks = ['红宝L', '东山精M', '东方财D', '中通客C', '浙江S', '浙江建T']
for acct in ['短线杰哥擒龙', '杰哥擒龙收评']:
    d = os.path.join(root, acct)
    for abbr in key_checks:
        full = abbrev_map.get(abbr, '?')
        for f in sorted(os.listdir(d)):
            if not f.endswith('.html'):
                continue
            fpath = os.path.join(d, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            if abbr in content:
                # Check if replaced
                if full in content:
                    print(f'  [OK] {abbr} -> {full} 已替换 (文件: {f[:30]})')
                else:
                    print(f'  [??] {abbr} 出现在 {f[:30]} 但未找到 {full}')
                break

print('\n\n检查完毕')
