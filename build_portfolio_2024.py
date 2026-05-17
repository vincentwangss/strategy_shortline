import json, os
from collections import defaultdict, OrderedDict

# Load sector data
with open(r'D:/杰哥复盘数据/stock_sector.json', 'r', encoding='utf-8') as f:
    stock_sector = json.load(f)

def get_sector(code):
    return stock_sector.get(code, {}).get('sector', '其他')

# Load raw signals
with open(r'D:/杰哥复盘数据/stock_signals.json', 'r', encoding='utf-8') as f:
    all_signals = json.load(f)

# Filter: 2024+ only
START_DATE = '2024-01-01'
signals = [s for s in all_signals if s['date'] >= START_DATE]

# Apply same constraints as backtest
MAX_STOCKS_PER_DAY = 5
MAX_PER_SECTOR = 1

daily = OrderedDict()
for s in signals:
    daily.setdefault(s['date'], []).append(s)

filtered = []
for date in sorted(daily):
    selected = []
    used_sectors = set()
    for s in daily[date]:
        if len(selected) >= MAX_STOCKS_PER_DAY:
            break
        sector = get_sector(s['stock_code'])
        if sector in used_sectors:
            continue
        selected.append(s)
        used_sectors.add(sector)
    filtered.extend(selected)

# Load backtest trades for performance
with open(r'D:/杰哥复盘数据/backtest_trades.json', 'r', encoding='utf-8') as f:
    bt_data = json.load(f)
trades_1 = bt_data['strategy_1day']

# Build trade lookup: signal_date -> [trades]
trade_by_signal = defaultdict(list)
for t in trades_1:
    trade_by_signal[t['signal_date']].append(t)

# Build portfolio report
lines = []
lines.append('=' * 80)
lines.append(f'  复盘股票组合 (2024+ 每日最多{MAX_STOCKS_PER_DAY}只, 每板块最多{MAX_PER_SECTOR}只)')
lines.append('=' * 80)
lines.append(f'')
lines.append(f'总信号: {len(filtered)}, 交易天数: {len(daily)}, 实际交易: {len(trades_1)}')

# Group filtered signals by date for daily report
filtered_daily = OrderedDict()
for s in filtered:
    filtered_daily.setdefault(s['date'], []).append(s)

# Per day report
for date in sorted(filtered_daily):
    day_stocks = filtered_daily[date]
    lines.append(f'')
    lines.append(f'【{date}】{len(day_stocks)}只')
    for s in day_stocks:
        sector = get_sector(s['stock_code'])
        lines.append(f'  {s["stock_name"]}({s["stock_code"]}) [{sector}]')

# Monthly summary
monthly = defaultdict(list)
for t in trades_1:
    monthly[t['buy_date'][:7]].append(t)

lines.append(f'')
lines.append('')
lines.append('=' * 80)
lines.append('  月度收益明细')
lines.append('=' * 80)
lines.append(f'')
lines.append(f'{"月份":>8} {"笔数":>6} {"胜率":>8} {"均收益":>9} {"累计收益":>11} {"最大回撤":>10}')
lines.append('-' * 55)
for ym in sorted(monthly):
    rr = [t['return'] for t in monthly[ym]]
    w = sum(1 for r in rr if r > 0)
    avg = sum(rr) / len(rr)
    cum = sum(rr)
    equity = [100]
    for r in rr:
        equity.append(equity[-1] * (1 + r / 100))
    peak = max(equity)
    dd = (min(equity) - peak) / peak * 100
    lines.append(f'{ym:>8} {len(rr):>6} {w/len(rr)*100:>7.0f}% {avg:>8.2f}% {cum:>10.2f}% {dd:>9.2f}%')

# Yearly
yearly = defaultdict(list)
for t in trades_1:
    yearly[t['buy_date'][:4]].append(t)
lines.append(f'')
lines.append(f'{"年份":>6} {"笔数":>6} {"胜率":>8} {"均收益":>9} {"累计收益":>11} {"最大回撤":>10}')
lines.append('-' * 48)
for y in sorted(yearly):
    rr = [t['return'] for t in yearly[y]]
    w = sum(1 for r in rr if r > 0)
    avg = sum(rr) / len(rr)
    cum = sum(rr)
    equity = [100]
    for r in rr:
        equity.append(equity[-1] * (1 + r / 100))
    peak = max(equity)
    dd = (min(equity) - peak) / peak * 100
    lines.append(f'{y:>6} {len(rr):>6} {w/len(rr)*100:>7.0f}% {avg:>8.2f}% {cum:>10.2f}% {dd:>9.2f}%')

# Best/worst stocks
lines.append(f'')
lines.append('')
lines.append('=' * 80)
lines.append('  个股收益排名（交易次数>=5）')
lines.append('=' * 80)
lines.append(f'')
stock_stats = defaultdict(list)
for t in trades_1:
    stock_stats[t['code']].append(t)
ranked = sorted(stock_stats.items(), key=lambda x: sum(t['return'] for t in x[1]), reverse=True)
lines.append(f'{"代码":>8} {"名称":>10} {"次数":>6} {"胜率":>8} {"均收益":>9} {"累计收益":>11}')
for code, tlist in ranked:
    if len(tlist) < 5:
        continue
    name = tlist[0]['stock']
    rr = [t['return'] for t in tlist]
    w = sum(1 for r in rr if r > 0)
    avg = sum(rr) / len(rr)
    cum = sum(rr)
    lines.append(f'{code:>8} {name:>10} {len(rr):>6} {w/len(rr)*100:>7.0f}% {avg:>8.2f}% {cum:>10.2f}%')

# Save
output = '\n'.join(lines)
with open(r'D:/杰哥复盘数据/portfolio_report.txt', 'w', encoding='utf-8') as f:
    f.write(output)

print(f'已保存 portfolio_report.txt ({len(lines)}行)')
print(f'日期: {sorted(daily.keys())[0]} ~ {sorted(daily.keys())[-1]}')
print(f'信号数: {len(filtered)}, 交易: {len(trades_1)}')
