import os, re, json
from datetime import datetime, timedelta

root = 'D:/杰哥复盘数据'

# ========== Undated HTML files ==========
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

# ========== Read each file and extract content ==========
results = {}
for acct, files in undated.items():
    for fname in files:
        fpath = os.path.join(root, acct, fname)
        if not os.path.exists(fpath):
            # Try .md extension
            fpath = os.path.join(root, acct, fname)
            if not os.path.exists(fpath):
                results[f'{acct}/{fname}'] = 'FILE NOT FOUND'
                continue

        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()

        # Extract text
        body = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', content, flags=re.DOTALL|re.IGNORECASE)
        body = re.sub(r'<br\s*/?>', '\n', body, flags=re.IGNORECASE)
        body = re.sub(r'<p[^>]*>', '\n', body, flags=re.IGNORECASE)
        body = re.sub(r'</p>', '\n', body, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', body)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', '', text)

        # Save first 2000 chars for analysis
        results[f'{acct}/{fname}'] = {
            'total_chars': len(text),
            'preview': text[:2000]
        }

# Also save to file for analysis
with open(os.path.join(root, 'undated_content_analysis.txt'), 'w', encoding='utf-8') as f:
    for path, info in results.items():
        f.write(f'========== {path} ==========\n')
        f.write(f'总字符数: {info["total_chars"]}\n\n')
        text = info['preview']
        f.write(f'{text}\n\n')

print('已完成，结果保存到 undated_content_analysis.txt')
