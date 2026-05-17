import os, re
from collections import defaultdict

# Scan all article sources
sources = [
    ('短线杰哥擒龙', r'D:/tools/微信公众号批量下载工具3.7/缓存/短线杰哥擒龙'),
    ('杰哥擒龙收评', r'D:/tools/微信公众号批量下载工具3.7/缓存/杰哥擒龙收评'),
    ('短线杰哥擒龙', r'D:/project/duanxian/tools/缓存/短线杰哥擒龙'),
    ('杰哥擒龙收评', r'D:/project/duanxian/tools/缓存/杰哥擒龙收评'),
    ('短线杰哥擒龙', r'D:/tools/微信公众号批量下载工具3.8/缓存/短线杰哥擒龙'),
]

for account, path in sources:
    if not os.path.exists(path):
        print(f'{account} @ {path}: 不存在')
        continue
    files = [f for f in os.listdir(path) if f.endswith('.html') or f.endswith('.htm')]
    dates = defaultdict(list)
    for f in files:
        m = re.match(r'\[(\d{4}-\d{2}-\d{2})\]', f)
        if m:
            dates[m.group(1)].append(f)
        else:
            print(f'  无日期前缀: {f}')

    dup = {k:v for k,v in dates.items() if len(v) > 1}
    print(f'\n[{account}] {path}')
    print(f'  文件数: {len(files)}, 唯一日期: {len(dates)}')
    if dup:
        print(f'  同日多篇: {len(dup)}天')
        for d in sorted(dup.keys())[:5]:
            for f in dup[d]:
                print(f'    {f}')
    date_list = sorted(dates.keys())
    if date_list:
        print(f'  日期范围: {date_list[0]} ~ {date_list[-1]}')
    print()

print('\n=== 无日期前缀的文件 ===')
for account, path in sources:
    if not os.path.exists(path):
        continue
    for f in os.listdir(path):
        if (f.endswith('.html') or f.endswith('.htm')) and not re.match(r'\[\d{4}-\d{2}-\d{2}\]', f):
            print(f'  [{account}] {f}')
