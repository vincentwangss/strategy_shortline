import json, os
import pandas as pd
import numpy as np
from collections import defaultdict, OrderedDict

# ========== 过滤条件 ==========
def is_fan_question(ctx):
    """判断是否为粉丝提问（非杰哥本人的推荐）"""
    markers = ['杰哥，', '杰哥：', '杰哥、', '杰哥:', '请教', '请问', '杰哥你好', '杰哥好']
    return any(m in ctx for m in markers)

# ========== 加载信号 ==========
with open(r'D:/杰哥复盘数据/stock_signals.json', 'r', encoding='utf-8') as f:
    all_signals = json.load(f)

# 过滤粉丝提问
signals = [s for s in all_signals if not is_fan_question(s['context'])]
filtered_count = len(all_signals) - len(signals)

signals.sort(key=lambda x: x['date'])

# ========== 只测试2024年之后 ==========
START_DATE = '2024-01-01'
signals = [s for s in signals if s['date'] >= START_DATE]
print(f'原始信号: {len(all_signals)}')
print(f'过滤粉丝提问: {filtered_count}条')
print(f'有效信号: {len(signals)}, 唯一股票: {len(set(s["stock_code"] for s in signals))}')
print(f'时间范围: {signals[0]["date"] if signals else "无"} ~ {signals[-1]["date"] if signals else "无"}')

# ========== 加载板块分类 ==========
with open(r'D:/杰哥复盘数据/stock_sector.json', 'r', encoding='utf-8') as f:
    stock_sector = json.load(f)

def get_sector(code):
    return stock_sector.get(code, {}).get('sector', '其他')

# ========== 信号筛选：策略评分 + 板块/总量限制 ==========

# 策略评分：基于 短线交易策略体系.md 提炼的规则
def strategy_score(ctx):
    """根据策略体系给信号打分"""
    score = 0
    # 核心标的（龙头/核心/辨识度）→ 高分
    if any(kw in ctx for kw in ['龙头', '核心', '辨识度', '前排', '阵眼', '总龙头',
                                  '板块龙头', '补涨龙', '趋势龙头', '高标']):
        score += 3
    # 买入信号
    if any(kw in ctx for kw in ['低吸', '关注', '看好', '分歧低吸', '反核',
                                  '打板', '回封', '弱转强']):
        score += 2
    # 去弱存强/聚焦核心
    if any(kw in ctx for kw in ['去弱存强', '切核心', '聚焦核心']):
        score += 1
    # 情绪有利（修复/回暖）
    if any(kw in ctx for kw in ['修复', '回暖', '企稳', '反弹']):
        score += 1
    # 分歧=买入机会（策略核心原则）
    if any(kw in ctx for kw in ['分歧', '冰点']):
        score += 1
    # 弱势/风险信号 → 减分
    if any(kw in ctx for kw in ['跟风', '杂毛', '后排', '补跌', '风险',
                                  '亏钱效应', 'A杀', '退潮', '出货']):
        score -= 2
    if any(kw in ctx for kw in ['卖出', '止损', '出局', '回避']):
        score -= 1
    return score

MAX_STOCKS_PER_DAY = 5
MAX_PER_SECTOR = 1

daily = OrderedDict()
for s in signals:
    daily.setdefault(s['date'], []).append(s)

filtered_signals = []
total_filtered = 0
for date in sorted(daily):
    day_signals = daily[date]
    # Score and sort by strategy criteria
    scored = [(strategy_score(s['context']), s) for s in day_signals]
    scored.sort(key=lambda x: -x[0])  # descending by score
    selected = []
    used_sectors = set()
    for score, s in scored:
        if len(selected) >= MAX_STOCKS_PER_DAY:
            total_filtered += 1
            continue
        sector = get_sector(s['stock_code'])
        if sector in used_sectors and MAX_PER_SECTOR <= 1:
            total_filtered += 1
            continue
        selected.append(s)
        used_sectors.add(sector)
    filtered_signals.extend(selected)

print(f'信号筛选: 策略评分排序, 每日最多{MAX_STOCKS_PER_DAY}只, 每板块最多{MAX_PER_SECTOR}只')
print(f'原始信号: {len(signals)}, 筛选后: {len(filtered_signals)}, 过滤: {total_filtered}')
if filtered_signals:
    scores_track = [strategy_score(s['context']) for s in filtered_signals[:10]]
    print(f'前10条信号评分: {scores_track}')
signals = filtered_signals
unique_stocks = sorted(set(s['stock_code'] for s in signals))

# ========== 加载价格数据 ==========
price_cache = {}
price_dir = r'D:/杰哥复盘数据/price_data'
loaded = 0
for code in unique_stocks:
    csv_path = f'{price_dir}/{code}.csv'
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        for col in ['open','close','high','low','volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        price_cache[code] = df
        loaded += 1
print(f'加载价格数据: {loaded}/{len(unique_stocks)}')

def get_next_trading_day(price_df, date_str):
    dates = sorted(price_df['date'].values)
    for d in dates:
        if d > date_str:
            return d
    return None

def get_nth_trading_day(price_df, from_date, n):
    current = from_date
    for _ in range(n):
        nd = get_next_trading_day(price_df, current)
        if nd:
            current = nd
        else:
            return None
    return current

def is_limit_up(price_df, date_str, threshold=0.095):
    """判断某天开盘是否涨停（买不到）"""
    row = price_df[price_df['date'] == date_str]
    if row.empty:
        return False
    open_price = row['open'].values[0]
    # 找前一天的收盘价
    prev = get_prev_trading_day(price_df, date_str)
    if not prev:
        return False
    prev_row = price_df[price_df['date'] == prev]
    if prev_row.empty:
        return False
    prev_close = prev_row['close'].values[0]
    if pd.isna(open_price) or pd.isna(prev_close) or prev_close == 0:
        return False
    # 涨幅 >= 9.5% 视为涨停买不到
    return (open_price / prev_close - 1) >= threshold

def is_limit_down(price_df, date_str, threshold=0.095):
    """判断某天收盘是否跌停（卖不出去）"""
    row = price_df[price_df['date'] == date_str]
    if row.empty:
        return False
    close_price = row['close'].values[0]
    prev = get_prev_trading_day(price_df, date_str)
    if not prev:
        return False
    prev_row = price_df[price_df['date'] == prev]
    if prev_row.empty:
        return False
    prev_close = prev_row['close'].values[0]
    if pd.isna(close_price) or pd.isna(prev_close) or prev_close == 0:
        return False
    # 跌幅 <= -9.5% 视为跌停卖不出去
    return (close_price / prev_close - 1) <= -threshold

def get_prev_trading_day(price_df, date_str):
    """获取前一个交易日"""
    dates = sorted(price_df['date'].values)
    for d in reversed(dates):
        if d < date_str:
            return d
    return None

# ========== 运行策略 ==========
def run_strategy(signals, hold_days, name):
    trades = []
    skipped_limit_up = 0
    limit_down_delays = 0
    for s in signals:
        code = s['stock_code']
        date = s['date']
        if code not in price_cache:
            continue
        df = price_cache[code]
        buy_date = get_next_trading_day(df, date)
        if not buy_date:
            continue

        # 检查买入日是否涨停开盘（买不到）
        if is_limit_up(df, buy_date):
            skipped_limit_up += 1
            continue

        if hold_days == 1:
            sell_date = get_next_trading_day(df, buy_date)
        else:
            sell_date = get_nth_trading_day(df, buy_date, hold_days)
        if not sell_date or sell_date == buy_date:
            continue

        # 如果卖出日跌停，延后到能卖出的交易日（最多5天）
        extra_delay = 0
        while extra_delay < 5 and is_limit_down(df, sell_date):
            extra_delay += 1
            next_sell = get_next_trading_day(df, sell_date)
            if not next_sell:
                break
            sell_date = next_sell

        if not sell_date or sell_date == buy_date:
            continue
        if extra_delay > 0:
            limit_down_delays += 1

        buy_row = df[df['date'] == buy_date]
        sell_row = df[df['date'] == sell_date]
        if buy_row.empty or sell_row.empty:
            continue
        buy_price = buy_row['open'].values[0]
        sell_price = sell_row['close'].values[0]
        if pd.isna(buy_price) or pd.isna(sell_price) or buy_price == 0:
            continue
        ret = (sell_price - buy_price) / buy_price
        trades.append({
            'stock': s['stock_name'],
            'code': code,
            'signal_date': date,
            'buy_date': buy_date,
            'buy_price': round(buy_price, 2),
            'sell_date': sell_date,
            'sell_price': round(sell_price, 2),
            'return': round(ret * 100, 2),
            'limit_down_delay': extra_delay,
        })
    return trades, skipped_limit_up, limit_down_delays

def print_stats(trades, label, skipped=0, delayed=0):
    print()
    print('=' * 70)
    print(f'  {label}')
    print('=' * 70)
    print(f'交易次数: {len(trades)}')
    if skipped:
        print(f'涨停开盘买不到跳过: {skipped}次')
    if delayed:
        print(f'跌停收盘延迟卖出: {delayed}次')
    if not trades:
        print('无交易')
        return
    r = np.array([t['return'] for t in trades])
    w = sum(r > 0)
    l = sum(r < 0)
    win_rate = w / len(r) * 100
    avg_ret = r.mean()
    cum_ret = r.sum()
    std_ret = r.std()

    # 累计净值曲线
    equity = pd.Series((1 + r / 100).cumprod())
    total_return = (equity.iloc[-1] - 1) * 100

    # 最大回撤
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min() * 100

    # 盈亏比
    avg_win = r[r > 0].mean() if w > 0 else 0
    avg_loss = r[r < 0].mean() if l > 0 else 0
    profit_factor = abs(r[r > 0].sum() / r[r < 0].sum()) if l > 0 and r[r < 0].sum() != 0 else float('inf')

    print(f'胜率: {win_rate:.1f}% ({w}胜/{l}负)')
    print(f'平均收益: {avg_ret:.2f}%')
    print(f'累计收益(等权): {cum_ret:.2f}%')
    print(f'累计净值收益: {total_return:.2f}%')
    print(f'最大回撤: {max_dd:.2f}%')
    print(f'收益标准差: {std_ret:.2f}%')
    print(f'盈亏比: {avg_win:.2f}% / {avg_loss:.2f}% = {abs(avg_win/avg_loss) if avg_loss != 0 else float("inf"):.2f}')
    print(f'利润因子: {profit_factor:.2f}')

    # 逐年
    yr = defaultdict(list)
    for t in trades:
        yr[t['buy_date'][:4]].append(t['return'])
    print()
    print('逐年表现:')
    print(f'  {"年份":>6} {"笔数":>6} {"胜率":>8} {"平均":>8} {"累计":>10} {"最大回撤":>10}')
    for y in sorted(yr):
        rr = np.array(yr[y])
        ww = sum(rr > 0)
        eq = pd.Series((1 + rr / 100).cumprod())
        pk = eq.expanding().max()
        dd = (eq - pk) / pk
        mdd = dd.min() * 100
        print(f'  {y:>6} {len(rr):>6} {ww/len(rr)*100:>7.0f}% {rr.mean():>7.2f}% {rr.sum():>9.2f}% {mdd:>9.2f}%')

# ========== 运行三个策略 ==========
trades_1, skipped_1, delayed_1 = run_strategy(signals, 1, '隔日')
trades_2, skipped_2, delayed_2 = run_strategy(signals, 3, '持3日')
trades_3, skipped_3, delayed_3 = run_strategy(signals, 5, '持5日')

print_stats(trades_1, '策略1: 隔日超短（信号次日开盘买，再次日收盘卖）', skipped_1, delayed_1)
print_stats(trades_2, '策略2: 持有3个交易日', skipped_2, delayed_2)
print_stats(trades_3, '策略3: 持有5个交易日', skipped_3, delayed_3)

# ========== 按月统计 ==========
print()
print('=' * 70)
print('  月度收益明细（策略1）')
print('=' * 70)
if trades_1:
    monthly = defaultdict(list)
    for t in trades_1:
        ym = t['buy_date'][:7]
        monthly[ym].append(t['return'])
    print(f'  {"月份":>8} {"笔数":>6} {"胜率":>8} {"平均":>8} {"累计":>10}')
    for ym in sorted(monthly):
        rr = np.array(monthly[ym])
        ww = sum(rr > 0)
        print(f'  {ym:>8} {len(rr):>6} {ww/len(rr)*100:>7.0f}% {rr.mean():>7.2f}% {rr.sum():>9.2f}%')

# ========== 股票排名 ==========
print()
print('=' * 70)
print('  股票交易次数排名（策略1）')
print('=' * 70)
if trades_1:
    stock_counts = defaultdict(list)
    for t in trades_1:
        stock_counts[t['code']].append(t['return'])
    ranked = sorted(stock_counts.items(), key=lambda x: len(x[1]), reverse=True)
    print(f'  {"代码":>8} {"名称":>10} {"次数":>6} {"胜率":>8} {"平均":>8} {"累计":>10}')
    for code, returns in ranked[:20]:
        name = next((t['stock'] for t in trades_1 if t['code'] == code), '')
        rr = np.array(returns)
        ww = sum(rr > 0)
        print(f'  {code:>8} {name:>10} {len(rr):>6} {ww/len(rr)*100:>7.0f}% {rr.mean():>7.2f}% {rr.sum():>9.2f}%')

# 保存结果
output = {
    'strategy_1day': trades_1,
    'strategy_3day': trades_2,
    'strategy_5day': trades_3
}
with open(r'D:/杰哥复盘数据/backtest_trades.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)
print()
print('结果已保存到 D:/杰哥复盘数据/backtest_trades.json')
