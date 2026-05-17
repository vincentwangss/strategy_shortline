import os, re, json
from datetime import datetime, timedelta

root = 'D:/杰哥复盘数据'

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

# Try to extract dates from HTML metadata or date patterns in content
date_results = {}

for acct, files in undated.items():
    for fname in files:
        fpath = os.path.join(root, acct, fname)
        if not os.path.exists(fpath):
            date_results[f'{acct}/{fname}'] = 'NOT_FOUND'
            continue

        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()

        clues = []

        # 1. Check HTML metadata for timestamps
        # WeChat article timestamps
        m = re.search(r'create_time["\']?\s*[:=]\s*["\']?(\d{10})["\']?', content)
        if m:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts)
            clues.append(f'HTML create_time: {dt.strftime("%Y-%m-%d")}')

        m = re.search(r'ct["\']?\s*[:=]\s*["\']?(\d{10})["\']?', content)
        if m:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts)
            clues.append(f'HTML ct: {dt.strftime("%Y-%m-%d")}')

        m = re.search(r'publish_time["\']?\s*[:=]\s*["\']?(\d{10})', content)
        if m:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts)
            clues.append(f'HTML publish_time: {dt.strftime("%Y-%m-%d")}')

        # WeChat specific timestamp pattern
        m = re.search(r'var\s+create_time\s*=\s*["\']?(\d{10})', content)
        if m:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts)
            clues.append(f'var create_time: {dt.strftime("%Y-%m-%d")}')

        # 2. Look for date patterns in text
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', '', text)

        # Full date patterns: YYYY年MM月DD日
        for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text):
            clues.append(f'Text date: {m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}')

        # YYYY-MM-DD
        for m in re.finditer(r'(\d{4})-(\d{1,2})-(\d{1,2})', text):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2020 <= y <= 2026 and 1 <= mo <= 12 and 1 <= d <= 31:
                clues.append(f'Text ISO date: {y}-{mo:02d}-{d:02d}')

        # 3. Modified date at end of article
        m = re.search(r'修改于\s*(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            clues.append(f'Modified date: {m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}')

        m = re.search(r'修改于(\d{4})(\d{2})(\d{2})', text)
        if m:
            clues.append(f'Modified date: {m.group(1)}-{m.group(2)}-{m.group(3)}')

        date_results[f'{acct}/{fname}'] = clues if clues else 'NO_DATE_CLUES'

# Print results
for path, clues in sorted(date_results.items()):
    print(f'{path}:')
    if isinstance(clues, list):
        for c in clues:
            print(f'  {c}')
    else:
        print(f'  {clues}')
    print()
