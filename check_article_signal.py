import os, re, json

# Check a 2024-01 article from 短线杰哥擒龙 to understand signal extraction gap
merged_dir = 'D:/杰哥复盘数据/merged'
for entry in os.scandir(merged_dir):
    if entry.is_dir() and '短线' in entry.name:
        d = entry.path
        files = sorted(os.listdir(d))
        # Find a 2024-01 file
        for f in files:
            if '2024-01' in f and '0103' in f:
                fpath = os.path.join(d, f)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()

                # Extract clean text
                body = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL|re.IGNORECASE)
                body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL|re.IGNORECASE)
                text = re.sub(r'<[^>]+>', '', body)
                text = re.sub(r'\s+', '', text)

                print(f'文件: {f}')
                print(f'纯文本: {len(text)}字')
                print(f'\n全文内容:')
                print(text)
                print()

                # Load stock name map
                with open('D:/杰哥复盘数据/stock_name_map.json', 'r', encoding='utf-8') as sm:
                    name_map = json.load(sm)

                # Check which stock names appear in the text
                found_stocks = []
                for name, code in name_map.items():
                    if name in text and len(name) > 1:
                        found_stocks.append((name, code))

                print(f'\n文中出现的股票名:')
                for name, code in sorted(found_stocks, key=lambda x: text.count(x[0]), reverse=True)[:30]:
                    count = text.count(name)
                    pos = text.find(name)
                    ctx = text[max(0,pos-20):pos+len(name)+20]
                    print(f'  {name}({code}): {count}次 -> ...{ctx}...')
                break
        break
