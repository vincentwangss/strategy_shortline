import json, os
import pandas as pd
import numpy as np
from collections import defaultdict

# Load trades
with open(r'D:/杰哥复盘数据/backtest_trades.json', 'r', encoding='utf-8') as f:
    bt_data = json.load(f)

trades = bt_data['strategy_1day_stop_loss']

# Load price cache
price_cache = {}
price_dir = r'D:/杰哥复盘数据/price_data'
unique_codes = set(t['code'] for t in trades)
loaded = 0
for code in unique_codes:
    csv_path = f'{price_dir}/{code}.csv'
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        for col in ['open','close','high','low','volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        price_cache[code] = df
        loaded += 1

print(f'加载价格数据: {loaded}/{len(unique_codes)}, 交易: {len(trades)}')

# Build daily position map for each trade
trade_daily_values = []
for t in trades:
    code = t['code']
    buy_date = t['buy_date']
    sell_date = t['sell_date']
    buy_price = t['buy_price']

    if code not in price_cache:
        continue
    df = price_cache[code]
    mask = (df['date'] >= buy_date) & (df['date'] <= sell_date)
    period = df[mask].sort_values('date')
    if period.empty:
        continue

    is_stop_loss = t.get('stop_loss', False)

    for _, row in period.iterrows():
        d = row['date']
        close = row['close']
        if pd.isna(close) or close == 0:
            continue
        daily_ret = (close / buy_price - 1) * 100
        trade_daily_values.append({
            'date': d,
            'code': code,
            'name': t['stock'],
            'buy_date': buy_date,
            'sell_date': sell_date,
            'buy_price': buy_price,
            'close': close,
            'return_pct': round(daily_ret, 2),
            'is_stop_loss': is_stop_loss,
        })

df_positions = pd.DataFrame(trade_daily_values)
dates = sorted(df_positions['date'].unique())
print(f'交易日: {len(dates)}')

# ========== 模拟1：等权（全仓均分） ==========
daily_portfolio_eq = []
for d in dates:
    day_data = df_positions[df_positions['date'] == d]
    n_positions = len(day_data)
    if n_positions == 0:
        continue
    avg_ret = day_data['return_pct'].mean()
    best = day_data.loc[day_data['return_pct'].idxmax()]
    worst = day_data.loc[day_data['return_pct'].idxmin()]
    daily_portfolio_eq.append({
        'date': d, 'positions': n_positions, 'avg_return_pct': round(avg_ret, 2),
        'best_stock': f"{best['name']}({best['code']}) {best['return_pct']:+.2f}%",
        'worst_stock': f"{worst['name']}({worst['code']}) {worst['return_pct']:+.2f}%",
    })
df_eq = pd.DataFrame(daily_portfolio_eq)
df_eq['equity'] = (1 + df_eq['avg_return_pct'] / 100).cumprod() * 100
df_eq['peak'] = df_eq['equity'].cummax()
df_eq['drawdown_pct'] = (df_eq['equity'] - df_eq['peak']) / df_eq['peak'] * 100

# ========== 模拟2：每只固定2成，剩余现金收益0 ==========
ALLOC_PCT = 0.20
portfolio_value = 100.0
cash = 100.0
active = {}
history_20pct = []

# Use a unique key per trade to avoid same-code conflicts
next_id = 0

for d in dates:
    day_data = df_positions[df_positions['date'] == d]
    if day_data.empty:
        history_20pct.append({'date': d, 'portfolio_value': portfolio_value, 'positions': 0, 'invested_pct': 0})
        continue

    # 1. New buys
    new_buys = day_data[day_data['buy_date'] == d]
    for _, pos in new_buys.iterrows():
        code = pos['code']
        invest = portfolio_value * ALLOC_PCT
        cash -= invest
        trade_key = f"{code}_{d}_{next_id}"
        next_id += 1
        active[trade_key] = {
            'code': code,
            'invested': invest,
            'buy_price': pos['buy_price'],
            'sell_date': pos['sell_date'],
        }

    # 2. Update positions and check sells
    total_position_value = 0
    for key in list(active.keys()):
        info = active[key]
        mask = (day_data['code'] == info['code'])
        if mask.any():
            row = day_data[mask].iloc[0]
            ret_pct = row['return_pct']
            position_value = info['invested'] * (1 + ret_pct / 100)

            is_sell_today = row['sell_date'] == d
            if is_sell_today:
                cash += position_value
                del active[key]
            else:
                total_position_value += position_value

    # 3. Clean up any positions that disappeared from data (shouldn't happen)
    active_codes_today = set(day_data['code'].unique())
    for key in list(active.keys()):
        if active[key]['code'] not in active_codes_today:
            cash += active[key]['invested']
            del active[key]

    # 4. Portfolio value
    portfolio_value = cash + total_position_value
    invested_ratio = 1 - cash / portfolio_value if portfolio_value > 0 else 0
    history_20pct.append({
        'date': d,
        'portfolio_value': round(portfolio_value, 2),
        'positions': len(active),
        'cash': round(cash, 2),
        'invested_pct': round(invested_ratio * 100, 1),
    })

df_20pct = pd.DataFrame(history_20pct)
df_20pct['equity'] = df_20pct['portfolio_value']
df_20pct['daily_pnl'] = df_20pct['portfolio_value'].diff()
df_20pct.loc[df_20pct.index[0], 'daily_pnl'] = df_20pct.loc[df_20pct.index[0], 'portfolio_value'] - 100
df_20pct['daily_return_pct'] = df_20pct['daily_pnl'] / (df_20pct['portfolio_value'] - df_20pct['daily_pnl']) * 100
df_20pct.loc[df_20pct.index[0], 'daily_return_pct'] = (df_20pct.loc[df_20pct.index[0], 'portfolio_value'] / 100 - 1) * 100
df_20pct['peak'] = df_20pct['equity'].cummax()
df_20pct['drawdown_pct'] = (df_20pct['equity'] - df_20pct['peak']) / df_20pct['peak'] * 100

# ========== Save CSVs ==========
detailed_path = r'D:/杰哥复盘数据/daily_positions_detail.csv'
df_positions_sorted = df_positions.sort_values(['date', 'code'])
df_positions_sorted.to_csv(detailed_path, index=False, encoding='utf-8-sig')

eq_path = r'D:/杰哥复盘数据/daily_positions_equal.csv'
df_eq.to_csv(eq_path, index=False, encoding='utf-8-sig')

pct_path = r'D:/杰哥复盘数据/daily_positions_20pct.csv'
df_20pct.to_csv(pct_path, index=False, encoding='utf-8-sig')

# ========== Print comparison ==========
print()
print('=' * 60)
print('  组合收益对比（隔日+止损-5% 实算-6%）')
print('=' * 60)

eq_final = df_eq['equity'].iloc[-1]
eq_max_dd = df_eq['drawdown_pct'].min()
eq_pos_days = (df_eq['avg_return_pct'] > 0).sum()

pct_final = df_20pct['portfolio_value'].iloc[-1]
pct_max_dd = df_20pct['drawdown_pct'].min()
pct_pos_days = (df_20pct['daily_return_pct'] > 0).sum()
avg_invested = df_20pct['invested_pct'].mean()

print(f'\n【等权（全仓）】')
print(f'  最终净值: {eq_final:.2f}  总收益: {eq_final-100:.2f}%')
print(f'  最大回撤: {eq_max_dd:.2f}%  胜率(日): {eq_pos_days/len(df_eq)*100:.1f}%')

print(f'\n【每只固定2成+剩余现金(0收益)】')
print(f'  最终净值: {pct_final:.2f}  总收益: {pct_final-100:.2f}%')
print(f'  最大回撤: {pct_max_dd:.2f}%  胜率(日): {pct_pos_days/len(df_20pct)*100:.1f}%')
print(f'  平均仓位: {avg_invested:.1f}%')

# Monthly comparison
print()
print(f'{"月份":>8} {"等权收益":>10} {"2成收益":>10} {"等权净值":>10} {"2成净值":>10} {"日均持仓":>8}')
print('-' * 56)

df_eq['month'] = df_eq['date'].str[:7]
df_20pct['month'] = df_20pct['date'].str[:7]

eq_monthly = df_eq.groupby('month').agg({'equity': ['first', 'last']})
eq_monthly.columns = ['start_eq', 'end_eq']
eq_monthly['return_pct'] = (eq_monthly['end_eq'] / eq_monthly['start_eq'] - 1) * 100

pct_monthly = df_20pct.groupby('month').agg({'portfolio_value': ['first', 'last']})
pct_monthly.columns = ['start_pct', 'end_pct']
pct_monthly['return_pct'] = (pct_monthly['end_pct'] / pct_monthly['start_pct'] - 1) * 100

for m in sorted(set(df_eq['month']) | set(df_20pct['month'])):
    eq_r = eq_monthly.loc[m, 'return_pct'] if m in eq_monthly.index else 0
    pct_r = pct_monthly.loc[m, 'return_pct'] if m in pct_monthly.index else 0
    eq_e = eq_monthly.loc[m, 'end_eq'] if m in eq_monthly.index else 0
    pct_e = pct_monthly.loc[m, 'end_pct'] if m in pct_monthly.index else 0
    month_rows = [r for r in history_20pct if r['date'][:7] == m]
    avg_pos = sum(r['positions'] for r in month_rows) / len(month_rows) if month_rows else 0
    print(f'{m:>8} {eq_r:>+8.2f}%  {pct_r:>+8.2f}%  {eq_e:>8.2f}  {pct_e:>8.2f}  {avg_pos:>6.1f}')
