import json
from collections import OrderedDict, defaultdict

def is_fan_question(ctx):
    markers = ['杰哥，', '杰哥：', '杰哥、', '杰哥:', '请教', '请问', '杰哥你好', '杰哥好']
    return any(m in ctx for m in markers)

with open(r'D:/杰哥复盘数据/stock_signals.json', 'r', encoding='utf-8') as f:
    signals = json.load(f)

# 过滤粉丝提问
valid = [s for s in signals if not is_fan_question(s['context'])]

portfolios = OrderedDict()
for s in valid:
    date = s['date']
    if date not in portfolios:
        portfolios[date] = {'articles': set(), 'stocks': []}
    portfolios[date]['stocks'].append(s)
    if 'article' in s:
        portfolios[date]['articles'].add(s['article'])

lines = []
lines.append(f'总信号数: {len(valid)}（原始{len(signals)}，过滤粉丝提问{len(signals)-len(valid)}条）')
lines.append(f'有信号的交易日: {len(portfolios)}')
lines.append('')

total_signal_count = 0
for date in sorted(portfolios):
    day = portfolios[date]
    stocks = day['stocks']
    articles = day['articles']

    # 去重统计
    seen = OrderedDict()
    for s in stocks:
        key = (s['stock_name'], s['stock_code'])
        if key not in seen:
            seen[key] = {'count': 0, 'accounts': set()}
        seen[key]['count'] += 1
        seen[key]['accounts'].add(s['account'])

    lines.append(f'【{date}】{len(seen)}只股票, {len(stocks)}条信号')
    for art in sorted(articles):
        lines.append(f'  来源: {art}')
    for (name, code), info in seen.items():
        account_tag = ' [收评]' if info['accounts'] == {'杰哥擒龙收评'} else ' [短线]' if info['accounts'] == {'短线杰哥擒龙'} else ' [混合]'
        count_tag = f' x{info["count"]}' if info['count'] > 1 else ''
        lines.append(f'  {name}({code}){account_tag}{count_tag}')
    lines.append('')

lines.append(f'共{len(portfolios)}天')

with open(r'D:/杰哥复盘数据/portfolios.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'已保存 portfolios.txt ({len(lines)}行)')
print(f'日期范围: {sorted(portfolios.keys())[0]} ~ {sorted(portfolios.keys())[-1]}')
print(f'总信号: {len(valid)}, 总天数: {len(portfolios)}')
