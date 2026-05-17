import os, re

# Check ALL accounts - do articles from 2024 exist and have extractable text?
sources = [
    ('短线杰哥擒龙', 'D:/tools/微信公众号批量下载工具3.7'),
    ('杰哥擒龙收评', 'D:/tools/微信公众号批量下载工具3.7'),
    ('短线杰哥擒龙', 'D:/project/duanxian/tools'),
    ('杰哥擒龙收评', 'D:/project/duanxian/tools'),
]

for acct_name, base_dir in sources:
    for item in os.listdir(base_dir):
        cache_dir = os.path.join(base_dir, item)
        if not os.path.isdir(cache_dir):
            continue
        for sub in os.listdir(cache_dir):
            if sub != acct_name:
                continue
            account_dir = os.path.join(cache_dir, sub)
            htmls = sorted([f for f in os.listdir(account_dir) if f.endswith('.html') and '2024' in f])
            if htmls:
                print(f'\n=== {acct_name} ({base_dir}) ===')
                print(f'  2024年文件: {len(htmls)}篇')
                # Check first article
                fpath = os.path.join(account_dir, htmls[0])
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                # Strip HTML to get text
                body = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', '', body)
                text = re.sub(r'\s+', '', text)
                print(f'  首篇: {htmls[0]}')
                print(f'  纯文本长度: {len(text)}字')
                if text:
                    print(f'  [前150字]: {text[:150]}')
                    # Check for stock names :: we load stock_name_map
PYEOF
