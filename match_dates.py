import os, re, json
from datetime import datetime, timedelta

root = 'D:/杰哥复盘数据'

# Load stock name map FIRST
with open(os.path.join(root, 'stock_name_map.json'), 'r', encoding='utf-8') as f:
    name_map = json.load(f)
stock_name_list = list(name_map.keys())
print(f'Loaded {len(stock_name_list)} stock names')

# ===== STEP 1: Build a stock-mention index from dated articles =====
print('Building date index from dated articles...')

# Map of article date -> set of stock names mentioned
date_stock_index = {}
stock_date_index = {}  # stock name -> set of dates it appeared

account_names = ['杰哥擒龙收评', '短线杰哥擒龙']

for acct in account_names:
    d = os.path.join(root, acct)
    for f in os.listdir(d):
        m = re.match(r'(\d{8})_.*\.html$', f)
        if not m:
            continue
        date_str = m.group(1)
        if date_str not in date_stock_index:
            date_stock_index[date_str] = set()

        fpath = os.path.join(d, f)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)

        # Extract stock names mentioned
        for stock_name in stock_name_list:
            if stock_name in text:
                date_stock_index[date_str].add(stock_name)
                if stock_name not in stock_date_index:
                    stock_date_index[stock_name] = set()
                stock_date_index[stock_name].add(date_str)

print(f'Indexed {len(date_stock_index)} dated articles, {len(stock_date_index)} stocks')

# ===== STEP 2: For each undated article, find the best matching date =====
undated = {
    '杰哥擒龙收评': [
        '收评有主线的日子真好.html',
        '收评温水煮青蛙难搞.html',
        '收评继续轮动无奈挥别神奇.html',
    ],
    '短线杰哥擒龙': [
        '0717复盘科技强兑现弱势重归抱团.html',
        '0926复盘主线进一步加强.html',
        '1210复盘机器人板块打出韧性.html',
        '周一复盘与周二计划等分歧.html',
        '周一盘前计划.html',
        '周三复盘与周四计划亏米效应为零.html',
        '周三复盘与周四计划修复去弱存强.html',
        '周三复盘与周四计划反核.html',
        '周三复盘与周四计划总该修复下了.html',
        '周三复盘与周四计划情绪逐渐上升.html',
        '周三复盘与周四计划新的一个月要加油.html',
        '周二复盘与周三计划还是轮动.html',
        '周二复盘与周三计划靴子落地.html',
        '周四复盘与周五计划你相信光吗.html',
        '周四复盘与周五计划核心来回做.html',
        '周四复盘与周五计划科技新方向.html',
        '周四复盘与周五计划继续反核低吸.html',
        '周四复盘与周五计划逐步企稳.html',
        '周末复盘与周一计划修复预期做好去弱存强.html',
        '周末复盘与周一计划弱反弹预期.html',
    ]
}

def get_mentioned_stocks(text):
    """Extract all stock names mentioned in text"""
    mentioned = set()
    for stock_name in stock_name_list:
        if stock_name in text and len(stock_name) > 1:
            mentioned.add(stock_name)
    return mentioned

print(f'\n===== Analysing undated files =====')

results = {}
for acct, files in undated.items():
    for fname in files:
        fpath = os.path.join(root, acct, fname)
        if not os.path.exists(fpath):
            results[f'{acct}/{fname}'] = None
            continue

        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)

        stocks = get_mentioned_stocks(text)

        # Score each possible date by how many stocks overlap
        best_date = None
        best_score = 0
        best_overlap = set()

        for date_str, known_stocks in date_stock_index.items():
            overlap = stocks & known_stocks
            score = len(overlap)
            if score > best_score:
                best_score = score
                best_date = date_str
                best_overlap = overlap

        results[f'{acct}/{fname}'] = {
            'date': best_date,
            'score': best_score,
            'total_stocks': len(stocks),
            'overlap_stocks': list(best_overlap)[:10],
            'all_stocks': list(stocks),
        }

# Print results
for path, info in sorted(results.items()):
    print(f'\n--- {path}')
    if info is None:
        print('  FILE NOT FOUND')
        continue
    print(f'  Best date: {info["date"]} (score: {info["score"]}/{info["total_stocks"]} stocks)')
    if info['overlap_stocks']:
        print(f'  Key stocks: {info["overlap_stocks"][:8]}')
    else:
        print(f'  All stocks in article: {info["all_stocks"][:15]}')
        print(f'  (No overlap with any dated article)')
