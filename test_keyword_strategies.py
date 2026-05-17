"""
多策略对比回测：不同关键词组合的表现
====================================
用法: python test_keyword_strategies.py
"""

import json, os, sys
import pandas as pd
import numpy as np
from collections import defaultdict, OrderedDict

ROOT = r'D:/杰哥复盘数据'

# ========== 加载信号 ==========
with open(os.path.join(ROOT, 'stock_signals.json'), 'r', encoding='utf-8') as f:
    all_signals = json.load(f)

fan_markers = ['杰哥，', '杰哥：', '杰哥、', '杰哥:', '请教', '请问', '杰哥你好', '杰哥好']
signals_all = [s for s in all_signals if not any(m in s['context'] for m in fan_markers)]
signals_all = [s for s in signals_all if s['date'] >= '2024-01-01']

# ========== 关键词策略定义 ==========
STRATEGIES = OrderedDict({
    '全部信号(基准)': None,  # 无额外过滤
    '龙头核心': ['龙头', '核心', '辨识度', '前排', '高标'],
    '修复反弹': ['修复', '回暖', '企稳', '反弹'],
    '低吸分歧': ['低吸', '分歧', '冰点'],
    '趋势主升': ['趋势', '主升', '走强'],
    '打板涨停': ['打板', '回封', '涨停'],
    '反核': ['反核', '分歧低吸', '核按钮'],
    '风险警示': ['跟风', '杂毛', '后排', '补跌', '风险', '亏钱效应', '退潮'],
})

# ========== 板块分类 ==========
with open(os.path.join(ROOT, 'stock_sector.json'), 'r', encoding='utf-8') as f:
    stock_sector = json.load(f)

def get_sector(code):
    return stock_sector.get(code, {}).get('sector', '其他')

# ========== 策略评分 ==========
def strategy_score(ctx):
    score = 0
    if any(kw in ctx for kw in ['龙头', '核心', '辨识度', '前排', '阵眼', '总龙头',
                                  '板块龙头', '补涨龙', '趋势龙头', '高标']):
        score += 3
    if any(kw in ctx for kw in ['低吸', '关注', '看好', '分歧低吸', '反核',
                                  '打板', '回封', '弱转强']):
        score += 2
    if any(kw in ctx for kw in ['去弱存强', '切核心', '聚焦核心']):
        score += 1
    if any(kw in ctx for kw in ['修复', '回暖', '企稳', '反弹']):
        score += 1
    if any(kw in ctx for kw in ['分歧', '冰点']):
        score += 1
    if any(kw in ctx for kw in ['跟风', '杂毛', '后排', '补跌', '风险',
                                  '亏钱效应', 'A杀', '退潮', '出货']):
        score -= 2
    if any(kw in ctx for kw in ['卖出', '止损', '出局', '回避']):
        score -= 1
    return score

# ========== 价格数据 ==========
price_cache = {}
price_dir = os.path.join(ROOT, 'price_data')

def load_prices(unique_codes):
    global price_cache
    new_codes = [c for c in unique_codes if c not in price_cache]
    loaded = 0
    for code in new_codes:
        csv_path = f'{price_dir}/{code}.csv'
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            for col in ['open','close','high','low','volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            price_cache[code] = df
            loaded += 1
    return loaded

def get_next_trading_day(price_df, date_str):
    dates = sorted(price_df['date'].values)
    for d in dates:
        if d > date_str:
            return d
    return None

def get_prev_trading_day(price_df, date_str):
    dates = sorted(price_df['date'].values)
    for d in reversed(dates):
        if d < date_str:
            return d
    return None

def is_limit_up(price_df, date_str, threshold=0.095):
    row = price_df[price_df['date'] == date_str]
    if row.empty:
        return False
    prev = get_prev_trading_day(price_df, date_str)
    if not prev:
        return False
    prev_row = price_df[price_df['date'] == prev]
    if prev_row.empty:
        return False
    prev_close = prev_row['close'].values[0]
    if pd.isna(row['open'].values[0]) or pd.isna(prev_close) or prev_close == 0:
        return False
    return (row['open'].values[0] / prev_close - 1) >= threshold

def is_limit_down(price_df, date_str, threshold=0.095):
    row = price_df[price_df['date'] == date_str]
    if row.empty:
        return False
    prev = get_prev_trading_day(price_df, date_str)
    if not prev:
        return False
    prev_row = price_df[price_df['date'] == prev]
    if prev_row.empty:
        return False
    prev_close = prev_row['close'].values[0]
    if pd.isna(row['close'].values[0]) or pd.isna(prev_close) or prev_close == 0:
        return False
    return (row['close'].values[0] / prev_close - 1) <= -threshold

# ========== 运行单策略回测 ==========
def run_strategy(signals, hold_days=1, stop_loss_pct=-5, stop_loss_realized_pct=-6):
    trades = []
    skipped_limit_up = 0
    stop_loss_hits = 0

    for s in signals:
        code = s['stock_code']
        date = s['date']
        if code not in price_cache:
            continue
        df = price_cache[code]
        buy_date = get_next_trading_day(df, date)
        if not buy_date:
            continue
        if is_limit_up(df, buy_date):
            skipped_limit_up += 1
            continue

        sell_date = get_next_trading_day(df, buy_date)
        if not sell_date or sell_date == buy_date:
            continue

        buy_row = df[df['date'] == buy_date]
        if buy_row.empty:
            continue
        buy_price = buy_row['open'].values[0]
        if pd.isna(buy_price) or buy_price == 0:
            continue

        stop_loss_hit = False
        if stop_loss_pct is not None:
            holding = df[(df['date'] > buy_date) & (df['date'] <= sell_date)]
            for _, row in holding.iterrows():
                if pd.notna(row['low']) and row['low'] > 0:
                    if (row['low'] / buy_price - 1) * 100 <= stop_loss_pct:
                        stop_loss_hit = True
                        sell_date = row['date']
                        break

        if stop_loss_hit:
            stop_loss_hits += 1
            ret = stop_loss_realized_pct / 100
        else:
            extra_delay = 0
            while extra_delay < 5 and is_limit_down(df, sell_date):
                extra_delay += 1
                next_sell = get_next_trading_day(df, sell_date)
                if not next_sell:
                    break
                sell_date = next_sell
            if not sell_date or sell_date == buy_date:
                continue
            sell_row = df[df['date'] == sell_date]
            if sell_row.empty:
                continue
            sell_price = sell_row['close'].values[0]
            if pd.isna(sell_price) or sell_price == 0:
                continue
            ret = (sell_price - buy_price) / buy_price

        trades.append(ret * 100)
    return np.array(trades), skipped_limit_up, stop_loss_hits

# ========== 信号筛选 ==========
def filter_signals(signals, keywords):
    """按关键词过滤信号"""
    if keywords is None:
        return signals
    return [s for s in signals if any(kw in s['context'] for kw in keywords)]

def daily_filter(signals):
    """每日策略筛选（评分排序，最多5只，每板块1只）"""
    daily = OrderedDict()
    for s in signals:
        daily.setdefault(s['date'], []).append(s)

    result = []
    for date in sorted(daily):
        day_signals = daily[date]
        scored = [(strategy_score(s['context']), s) for s in day_signals]
        scored.sort(key=lambda x: -x[0])
        selected = []
        used_sectors = set()
        for score, s in scored:
            if len(selected) >= 5:
                continue
            sector = get_sector(s['stock_code'])
            if sector in used_sectors:
                continue
            selected.append(s)
            used_sectors.add(sector)
        result.extend(selected)
    return result

# ========== 主测试 ==========
print('=' * 80)
print('  多关键词策略对比回测（隔日+止损-5% 实算-6%）')
print('=' * 80)

results = []
for name, keywords in STRATEGIES.items():
    # 过滤信号
    filtered = filter_signals(signals_all, keywords)
    if len(filtered) < 10:
        print(f'\n{name}: 信号太少({len(filtered)}条)，跳过')
        continue

    # 每日策略筛选
    selected = daily_filter(filtered)

    # 加载价格数据
    unique_codes = list(set(s['stock_code'] for s in selected))
    load_prices(unique_codes)

    # 运行回测
    returns, skipped, stopped = run_strategy(selected)

    if len(returns) < 5:
        print(f'\n{name}: 交易太少({len(returns)}笔)，跳过')
        continue

    w = sum(returns > 0)
    l = sum(returns < 0)
    win_rate = w / len(returns) * 100
    avg_ret = returns.mean()
    total_ret = returns.sum()

    # 累计净值
    equity = pd.Series((1 + returns / 100).cumprod())
    final_equity = (equity.iloc[-1] - 1) * 100
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min() * 100

    avg_win = returns[returns > 0].mean() if w > 0 else 0
    avg_loss = returns[returns < 0].mean() if l > 0 else 0
    profit_factor = abs(returns[returns > 0].sum() / returns[returns < 0].sum()) if l > 0 and returns[returns < 0].sum() != 0 else float('inf')

    results.append({
        'name': name,
        'trades': len(returns),
        'win_rate': win_rate,
        'avg_ret': avg_ret,
        'total_ret': total_ret,
        'final_eq': final_equity,
        'max_dd': max_dd,
        'profit_factor': profit_factor,
        'skipped': skipped,
        'stopped': stopped,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
    })

    aw_al = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    print(f'\n{name}:')
    print(f'  信号{len(filtered)}条→交易{len(returns)}笔 胜率{win_rate:.1f}%')
    print(f'  平均收益{avg_ret:+.2f}% 累计等权{total_ret:+.2f}% 净值{final_equity:+.2f}%')
    print(f'  最大回撤{max_dd:.2f}% 盈亏比{avg_win:.2f}/{avg_loss:.2f}={aw_al:.2f}')
    print(f'  利润因子{profit_factor:.2f} 涨停跳过{skipped}次 止损{stopped}次')

# ========== 对比总结 ==========
print('\n' + '=' * 80)
print('  策略对比总结')
print('=' * 80)
print(f'{"策略":>12} {"交易":>6} {"胜率":>7} {"平均":>7} {"累计等权":>10} {"净值收益":>10} {"最大回撤":>8} {"利润因子":>8}')
print('-' * 75)
for r in sorted(results, key=lambda x: -x['final_eq']):
    nm, td, wr = r['name'], r['trades'], r['win_rate']
    ar, tr, fe = r['avg_ret'], r['total_ret'], r['final_eq']
    md, pf = r['max_dd'], r['profit_factor']
    print(f'{nm:>12} {td:>6} {wr:>5.1f}% {ar:>+6.2f}% {tr:>+9.2f}% {fe:>+9.2f}% {md:>7.2f}% {pf:>7.2f}')
