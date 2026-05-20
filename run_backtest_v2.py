"""
回测引擎 v2（基于投资原则）
=============================
修复：
1. 止损按实际价格算（处理跳空低开）
2. 情绪周期影响仓位和执行
3. 信心度决定每只仓位大小
4. 资金滚动管理（不是每次全仓）
5. 买卖触发条件更贴近实战
"""

import json, os
import pandas as pd
import numpy as np
from collections import defaultdict, OrderedDict

ROOT = r'D:/杰哥复盘数据'

# ═══════════════════════════════════════════════
# 配置参数
# ═══════════════════════════════════════════════

# 情绪周期对应的最大总仓位（全不限=全100%）
PHASE_MAX_POSITION = {
    '冰点': 1.00,
    '修复': 1.00,
    '高潮': 1.00,
    '退潮': 1.00,  # 退潮仍保留核心/龙头过滤
    '震荡': 1.00,
}

# 退潮期只允许这些角色的信号
RETREAT_ALLOWED_ROLES = ['总龙头', '板块龙头', '核心辨识度']

# 单只股票最大仓位
CONVICTION_POSITION = {
    5: 0.20,
    4: 0.20,
    3: 0.20,
    2: 0.20,
    1: 0.20,
}

STOP_LOSS_PCT = -0.05       # -5% 止损线
STOP_LOSS_FIXED_PCT = -0.06 # 止损触发后的实际损失



MAX_POSITIONS_PER_DAY = 5   # 每天最多建仓几只
MAX_PER_SECTOR = 1          # 每板块最多一只

PROFIT_TAKE_PCT = 0.05      # +5% 分批止盈触发线
PROFIT_TAKE_RATIO = 0.5     # 触发后卖一半


class BacktestEngineV2:
    def __init__(self):
        self.price_cache = {}
        self.sector_map = self._load_sector()
        self.signals = self._load_signals()
        self.phase_info = self._load_phase()

    def _load_sector(self):
        path = os.path.join(ROOT, 'stock_sector.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_signals(self):
        path = os.path.join(ROOT, 'stock_signals.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_phase(self):
        path = os.path.join(ROOT, 'daily_phase.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_sector(self, code):
        return self.sector_map.get(code, {}).get('sector', '其他')

    def load_prices(self, codes):
        loaded = 0
        for code in codes:
            if code in self.price_cache:
                continue
            csv_path = os.path.join(ROOT, 'price_data', f'{code}.csv')
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                for col in ['open', 'close', 'high', 'low', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.sort_values('date')
                self.price_cache[code] = df
                loaded += 1
        return loaded

    def get_next_trading_day(self, df, date_str):
        dates = sorted(df['date'].values)
        for d in dates:
            if d > date_str:
                return d
        return None

    def get_prev_trading_day(self, df, date_str):
        dates = sorted(df['date'].values)
        for d in reversed(dates):
            if d < date_str:
                return d
        return None

    def get_price_at(self, df, date_str, field='open'):
        row = df[df['date'] == date_str]
        if row.empty:
            return None
        val = row[field].values[0]
        if pd.isna(val) or val == 0:
            return None
        return val

    def is_limit_up_open(self, df, date_str, threshold=0.095):
        """涨停开盘（买不到）"""
        prev = self.get_prev_trading_day(df, date_str)
        if not prev:
            return False
        prev_close = self.get_price_at(df, prev, 'close')
        open_price = self.get_price_at(df, date_str, 'open')
        if not prev_close or not open_price:
            return False
        return (open_price / prev_close - 1) >= threshold

    def is_limit_down_close(self, df, date_str, threshold=0.095):
        """跌停收盘（卖不出）"""
        prev = self.get_prev_trading_day(df, date_str)
        if not prev:
            return False
        prev_close = self.get_price_at(df, prev, 'close')
        close_price = self.get_price_at(df, date_str, 'close')
        if not prev_close or not close_price:
            return False
        return (close_price / prev_close - 1) <= -threshold

    def is_limit_down_open(self, df, date_str, threshold=0.095):
        """跌停开盘（一字跌停，全天无流动性，卖不出）"""
        prev = self.get_prev_trading_day(df, date_str)
        if not prev:
            return False
        prev_close = self.get_price_at(df, prev, 'close')
        open_price = self.get_price_at(df, date_str, 'open')
        if not prev_close or not open_price:
            return False
        return (open_price / prev_close - 1) <= -threshold

    def can_sell_today(self, df, date_str):
        """判断当天是否能卖出：一字跌停开盘则无法卖出"""
        if self.is_limit_down_open(df, date_str):
            return False
        return True

    # ═══════════════════════════════════════════════
    # 每日信号筛选
    # ═══════════════════════════════════════════════

    def filter_daily_signals(self):
        """
        按天筛选信号：
        1. 按信心度降序排列
        2. 每板块最多1只
        3. 每天最多5只
        """
        daily = OrderedDict()
        for s in self.signals:
            if s.get('intent', 'buy') != 'buy':
                continue
            daily.setdefault(s['date'], []).append(s)

        filtered = []
        for date in sorted(daily):
            day_sigs = daily[date]
            # 按信心度排序（conviction降序）
            day_sigs.sort(key=lambda x: -x.get('conviction', 0))
            selected = []
            used_sectors = set()
            for s in day_sigs:
                if len(selected) >= MAX_POSITIONS_PER_DAY:
                    break
                sector = self.get_sector(s['stock_code'])
                if sector in used_sectors and MAX_PER_SECTOR <= 1:
                    continue
                selected.append(s)
                used_sectors.add(sector)
            filtered.extend(selected)

        return filtered

    # ═══════════════════════════════════════════════
    # 单笔交易模拟
    # ═══════════════════════════════════════════════

    def simulate_trade(self, signal, date_idx=None):
        """
        模拟一笔交易，返回详细的每日持仓信息
        修复：止损按实际价格算
        """
        code = signal['stock_code']
        sig_date = signal['date']
        conviction = signal.get('conviction', 1)
        stop_loss_pct, stop_loss_fixed = STOP_LOSS_PCT, STOP_LOSS_FIXED_PCT

        if code not in self.price_cache:
            return None
        df = self.price_cache[code]

        buy_date = self.get_next_trading_day(df, sig_date)
        if not buy_date:
            return None

        # 检查涨停开盘（买不到）
        if self.is_limit_up_open(df, buy_date):
            return {'skipped': True, 'reason': 'limit_up', 'signal': signal}

        # 买入价 = 次日开盘价
        buy_price = self.get_price_at(df, buy_date, 'open')
        if not buy_price:
            return None

        # 持有到下一个交易日卖出（隔日策略）
        sell_date = self.get_next_trading_day(df, buy_date)
        if not sell_date or sell_date == buy_date:
            return None

        # ════════════════════════════════════════
        # 止损检查（用实际价格，不用固定值）
        # ════════════════════════════════════════
        stop_hit = False
        stop_date = None
        stop_exit_price = None

        # 买入日和卖出日之间的所有交易日
        mask = (df['date'] > buy_date) & (df['date'] <= sell_date)
        holding_period = df[mask].sort_values('date')

        for _, row in holding_period.iterrows():
            current_date = row['date']
            low = row['low']
            if pd.notna(low) and low > 0:
                # 一字跌停开盘，全天无流动性，无法卖出，跳过
                if self.is_limit_down_open(df, current_date):
                    continue

                # 日内最低价触及止损线
                if (low / buy_price - 1) <= stop_loss_pct:
                    stop_hit = True
                    stop_date = current_date
                    # 按止损日的实际成交价算
                    open_today = row['open'] if pd.notna(row['open']) else low
                    exit_price = (open_today + low) / 2
                    # 但不能比止损线更低超过2%（防止跳空低开）
                    # 注意：一字跌停的情况在上面已经跳过，这里不会出现
                    max_loss_price = buy_price * (1 + stop_loss_fixed)
                    stop_exit_price = max(exit_price, max_loss_price)
                    break

        if stop_hit:
            sell_price = stop_exit_price
            sell_date_actual = stop_date
            ret = (sell_price - buy_price) / buy_price
            trade_type = 'stop_loss'
        else:
            # 正常卖出
            # 检查卖出日是否跌停或一字跌停开盘（卖不出则延后最多5天）
            extra_delay = 0
            current_sell = sell_date
            while extra_delay < 5:
                can_sell = (self.can_sell_today(df, current_sell)
                            and not self.is_limit_down_close(df, current_sell))
                if can_sell:
                    break
                extra_delay += 1
                next_s = self.get_next_trading_day(df, current_sell)
                if not next_s:
                    break
                current_sell = next_s

            # 最终能卖出日：如果是跌停打开的，用收盘价；否则用开盘价（真实流动性恢复）
            if self.can_sell_today(df, current_sell):
                sell_price = self.get_price_at(df, current_sell, 'close')
            else:
                # 连一字跌停5天后仍封死，按当天均价估算（真实会更惨）
                open_p = self.get_price_at(df, current_sell, 'open')
                close_p = self.get_price_at(df, current_sell, 'close')
                sell_price = (open_p + close_p) / 2 if (open_p and close_p) else (open_p or close_p)

            if not sell_price:
                return None
            sell_date_actual = current_sell
            ret = (sell_price - buy_price) / buy_price
            trade_type = 'normal'

        return {
            'stock': signal['stock_name'],
            'code': code,
            'signal_date': sig_date,
            'buy_date': buy_date,
            'buy_price': round(buy_price, 2),
            'sell_date': sell_date_actual,
            'sell_price': round(sell_price, 2),
            'return_pct': round(ret * 100, 2),
            'conviction': conviction,
            'phase': signal.get('phase', '震荡'),
            'role': signal.get('role', '普通'),
            'trade_type': trade_type,
            'limit_down_delay': extra_delay if not stop_hit else 0,
        }

    # ═══════════════════════════════════════════════
    # 组合模拟（资金管理）
    # ═══════════════════════════════════════════════

    def run_portfolio(self, initial_capital=1_000_000):
        """
        组合级别模拟：
        - 情绪周期决定总仓位上限
        - 信心度决定每只仓位大小
        - 每日资金分配
        """
        filtered = self.filter_daily_signals()

        # 加载价格数据
        codes = set(s['stock_code'] for s in filtered)
        self.load_prices(codes)
        print(f'加载价格数据: {sum(1 for c in codes if c in self.price_cache)}/{len(codes)}')

        # 按日期分组
        daily_signals = OrderedDict()
        for s in filtered:
            daily_signals.setdefault(s['date'], []).append(s)

        # 收集所有交易日（从价格数据中获取）
        all_trading_dates = set()
        for code in codes:
            if code in self.price_cache:
                for d in self.price_cache[code]['date'].values:
                    all_trading_dates.add(d)
        # 同时包含信号日期（可能不是交易日）
        all_trading_dates.update(daily_signals.keys())
        all_trading_dates = sorted(all_trading_dates)

        # 逐日模拟
        cash = initial_capital
        positions = {}  # id -> {code, shares, buy_price, cost, buy_date}

        trade_log = []
        daily_log = []
        next_id = 0
        month_start_value = initial_capital  # 月初净值
        prev_month = ''
        monthly_protection = False  # 月度亏损保护

        for current_date in all_trading_dates:
            phase = self.phase_info.get(current_date, '震荡')
            max_total_pct = PHASE_MAX_POSITION.get(phase, 0.30)

            # 1. 检查是否有持仓需要卖出
            for pid in list(positions.keys()):
                pos = positions[pid]
                exit_info = self.check_position_exit(pos, current_date)
                if exit_info:
                    code = pos['code']
                    sell_price = exit_info['exit_price']
                    ret = (sell_price - pos['avg_cost']) / pos['avg_cost']
                    proceeds = pos['shares'] * sell_price

                    trade_log.append({
                        **pos['signal'],
                        'buy_date': pos['buy_date'],
                        'buy_price': round(pos['avg_cost'], 2),
                        'sell_date': current_date,
                        'sell_price': round(sell_price, 2),
                        'return_pct': round(ret * 100, 2),
                        'trade_type': exit_info['type'].replace('normal_delayed', 'normal'),
                        'shares': pos['shares'],
                        'invested': round(pos['cost'], 2),
                        'pnl': round(proceeds - pos['cost'], 2),
                    })
                    cash += proceeds
                    del positions[pid]

            # 1.5 分批止盈：持仓盈利>5%时卖一半，让利润奔跑
            for pid in list(positions.keys()):
                pos = positions[pid]
                code = pos['code']
                df = self.price_cache.get(code)
                if df is None:
                    continue
                close_px = self.get_price_at(df, current_date, 'close')
                if not close_px:
                    continue
                ret = (close_px - pos['avg_cost']) / pos['avg_cost']
                if ret > PROFIT_TAKE_PCT and self.can_sell_today(df, current_date):
                    # 买入当天不触发
                    if current_date <= pos['buy_date']:
                        continue
                    sell_shares = int(pos['shares'] * PROFIT_TAKE_RATIO / 100) * 100
                    if sell_shares < 100:
                        continue
                    proceeds = sell_shares * close_px
                    # 按比例扣减成本
                    cost_ratio = sell_shares / pos['shares']
                    sold_cost = pos['cost'] * cost_ratio
                    pos['shares'] -= sell_shares
                    pos['cost'] -= sold_cost
                    cash += proceeds
                    trade_log.append({
                        **pos['signal'],
                        'buy_date': pos['buy_date'],
                        'buy_price': round(pos['avg_cost'], 2),
                        'sell_date': current_date,
                        'sell_price': round(close_px, 2),
                        'return_pct': round(ret * 100, 2),
                        'trade_type': 'partial_take_profit',
                        'shares': sell_shares,
                        'invested': round(sold_cost, 2),
                        'pnl': round(proceeds - sold_cost, 2),
                    })

            # 2. 市值重估（按当前价更新持仓市值）
            total_position_value = 0
            for pos in positions.values():
                df = self.price_cache.get(pos['code'])
                if df is not None:
                    px = self.get_price_at(df, current_date, 'close')
                else:
                    px = pos['avg_cost']
                if px:
                    total_position_value += pos['shares'] * px
                else:
                    total_position_value += pos['cost']  # fallback

            portfolio_value = cash + total_position_value
            current_position_pct = total_position_value / portfolio_value if portfolio_value > 0 else 0

            # ── 月度亏损保护 ──
            # 如果当月累计亏损超10%，触发保护：
            #   - 剩余时间只允许核心/龙头买入
            #   - 买单仓位减半
            this_month = current_date[:7]
            if this_month != prev_month:
                month_start_value = portfolio_value
                prev_month = this_month
                monthly_protection = False

            month_return = (portfolio_value / month_start_value - 1) * 100
            if month_return <= -10 and not monthly_protection:
                monthly_protection = True
                print(f'  [月保护] {current_date} 当月亏损{month_return:.1f}%，触发月保护（强制清仓+仅核心/龙头+仓位减半）')

                # 强制清仓所有持仓
                for pid in list(positions.keys()):
                    pos = positions[pid]
                    code = pos['code']
                    df = self.price_cache.get(code)
                    if df is None:
                        continue
                    # 当前价卖出（一字跌停则用均价估算）
                    force_sell_date = current_date
                    if self.is_limit_down_open(df, current_date):
                        open_p = self.get_price_at(df, current_date, 'open')
                        close_p = self.get_price_at(df, current_date, 'close')
                        sell_price = (open_p + close_p) / 2 if (open_p and close_p) else (open_p or close_p or pos['avg_cost'])
                    elif self.is_limit_down_close(df, current_date):
                        # 跌停收盘：延后到能卖出为止（最多5天）
                        for _ in range(5):
                            next_d = self.get_next_trading_day(df, force_sell_date)
                            if not next_d:
                                break
                            force_sell_date = next_d
                            if self.can_sell_today(df, force_sell_date) and not self.is_limit_down_close(df, force_sell_date):
                                break
                        close_p = self.get_price_at(df, force_sell_date, 'close')
                        if close_p and self.can_sell_today(df, force_sell_date) and not self.is_limit_down_close(df, force_sell_date):
                            sell_price = close_p
                        else:
                            open_p = self.get_price_at(df, force_sell_date, 'open')
                            sell_price = (open_p + close_p) / 2 if (open_p and close_p) else (open_p or close_p or pos['avg_cost'])
                    else:
                        sell_price = self.get_price_at(df, current_date, 'close') or pos['avg_cost']

                    ret = (sell_price - pos['avg_cost']) / pos['avg_cost']
                    proceeds = pos['shares'] * sell_price
                    trade_log.append({
                        **pos['signal'],
                        'buy_date': pos['buy_date'],
                        'buy_price': round(pos['avg_cost'], 2),
                        'sell_date': force_sell_date,
                        'sell_price': round(sell_price, 2),
                        'return_pct': round(ret * 100, 2),
                        'trade_type': 'force_close',
                        'shares': pos['shares'],
                        'invested': round(pos['cost'], 2),
                        'pnl': round(proceeds - pos['cost'], 2),
                    })
                    cash += proceeds
                    del positions[pid]

                # 清仓后重算总市值
                total_position_value = 0
                portfolio_value = cash

            # 3. 新的一天建仓
            if current_date in daily_signals:
                day_signals = daily_signals[current_date]
                available_pct = max(0, max_total_pct - current_position_pct)
                remaining_capacity = available_pct  # 剩余可用仓位比例

                for s in day_signals:
                    if len(positions) >= 20:
                        break
                    if remaining_capacity <= 0:
                        break

                    # 退潮期只允许核心/龙头股
                    if phase == '退潮' and s.get('role', '普通') not in RETREAT_ALLOWED_ROLES:
                        continue

                    # 月保护：只允许核心/龙头，仓位减半
                    if monthly_protection:
                        if s.get('role', '普通') not in RETREAT_ALLOWED_ROLES:
                            continue
                        target_pct = CONVICTION_POSITION.get(round(s.get('conviction', 1)), 0.20) * 0.5
                    else:
                        target_pct = CONVICTION_POSITION.get(round(s.get('conviction', 1)), 0.20)

                    # 不超过剩余可用仓位
                    target_pct = min(target_pct, remaining_capacity)

                    code = s['stock_code']
                    if code not in self.price_cache:
                        continue

                    position_size = max(portfolio_value * target_pct, 20000)

                    df = self.price_cache[code]
                    buy_date = self.get_next_trading_day(df, current_date)
                    if not buy_date:
                        continue
                    if self.is_limit_up_open(df, buy_date):
                        trade_log.append({**s, 'buy_date': buy_date, 'skipped': True, 'reason': 'limit_up', 'return_pct': 0})
                        continue

                    buy_price = self.get_price_at(df, buy_date, 'open')
                    if not buy_price:
                        continue

                    # 如果现金不够目标仓位，剩多少买多少
                    shares = int(min(position_size, cash) / buy_price / 100) * 100
                    if shares < 100:
                        continue
                    cost = shares * buy_price
                    cash -= cost
                    positions[next_id] = {
                        'code': code, 'shares': shares,
                        'avg_cost': buy_price, 'cost': cost,
                        'buy_date': buy_date,
                        'signal': s,
                    }
                    next_id += 1
                    # 扣减可用仓位
                    remaining_capacity -= cost / portfolio_value

            # 重新计算持仓市值（新买的仓位也要计入）
            total_position_value = 0
            for pos in positions.values():
                df = self.price_cache.get(pos['code'])
                if df is not None:
                    px = self.get_price_at(df, current_date, 'close')
                else:
                    px = pos['avg_cost']
                if px:
                    total_position_value += pos['shares'] * px
                else:
                    total_position_value += pos['cost']

            # 4. 记录每日状态
            total_value = cash + total_position_value
            daily_log.append({
                'date': current_date,
                'phase': phase,
                'cash': round(cash, 2),
                'position_value': round(total_position_value, 2),
                'portfolio_value': round(total_value, 2),
                'num_positions': len(positions),
                'max_position_pct': max_total_pct,
                'month_return': round(month_return, 2),
                'monthly_protection': monthly_protection,
            })

        return trade_log, daily_log

    def check_position_exit(self, pos, current_date):
        """检查持仓是否需要在当天卖出（止损或到期）"""
        code = pos['code']
        if code not in self.price_cache:
            return None

        df = self.price_cache[code]
        buy_date = pos['buy_date']

        # 按角色获取差异化止损
        sl_pct, sl_fixed = STOP_LOSS_PCT, STOP_LOSS_FIXED_PCT

        # 买入当天不卖出
        if current_date <= buy_date:
            return None

        # 一字跌停开盘，全天无流动性，无法卖出
        if not self.can_sell_today(df, current_date):
            return None

        # 获取卖出日（买入后第一个交易日）
        sell_date = self.get_next_trading_day(df, buy_date)
        if not sell_date:
            return None

        # 如果当天还没到卖出日，只检查止损
        if current_date < sell_date:
            close_price = self.get_price_at(df, current_date, 'close')
            low_price = self.get_price_at(df, current_date, 'low')
            if close_price and low_price:
                if (low_price / pos['avg_cost'] - 1) <= sl_pct:
                    exit_price = max(
                        close_price,
                        pos['avg_cost'] * (1 + sl_fixed)
                    )
                    return {'exit_price': exit_price, 'type': 'stop_loss'}
            return None

        # 当天是卖出日
        if current_date == sell_date:
            close_price = self.get_price_at(df, current_date, 'close')
            low_price = self.get_price_at(df, current_date, 'low')
            open_price = self.get_price_at(df, current_date, 'open')

            # 检查止损（能卖出才执行止损）
            if open_price and low_price:
                if (low_price / pos['avg_cost'] - 1) <= sl_pct:
                    exit_price = max(
                        (open_price + low_price) / 2,
                        pos['avg_cost'] * (1 + sl_fixed)
                    )
                    return {'exit_price': exit_price, 'type': 'stop_loss'}

            # 正常卖出
            if not close_price:
                return None

            # 跌停延后
            if self.is_limit_down_close(df, current_date):
                return None

            return {'exit_price': close_price, 'type': 'normal'}

        # current_date > sell_date: 应该已经卖出了
        # 但如果之前跌停没卖出，看今天能不能卖
        if current_date > sell_date:
            close_price = self.get_price_at(df, current_date, 'close')
            if close_price and not self.is_limit_down_close(df, current_date):
                return {'exit_price': close_price, 'type': 'normal_delayed'}
            return None

        return None

    # ═══════════════════════════════════════════════
    # 简化回测（等权，用于对比旧版）
    # ═══════════════════════════════════════════════

    def run_simple_backtest(self):
        """
        简化版回测：每笔等权，用于策略对比
        但修复了止损按实际价格和跌停延迟的问题
        """
        filtered = self.filter_daily_signals()
        codes = set(s['stock_code'] for s in filtered)
        loaded = self.load_prices(codes)
        print(f'加载价格数据: {loaded}/{len(codes)}')

        trades = []
        skipped = {'limit_up': 0}
        stop_loss_hits = 0
        limit_down_delays = 0

        for s in filtered:
            result = self.simulate_trade(s)
            if result is None:
                continue
            if result.get('skipped'):
                skipped['limit_up'] += 1
                continue
            trades.append(result)
            if result['trade_type'] == 'stop_loss':
                stop_loss_hits += 1
            if result.get('limit_down_delay', 0) > 0:
                limit_down_delays += 1

        return trades, skipped, stop_loss_hits, limit_down_delays


# ═══════════════════════════════════════════════
# 统计输出
# ═══════════════════════════════════════════════

def print_stats(trades, label, skipped=None, stopped=0, delayed=0):
    print()
    print('=' * 70)
    print(f'  {label}')
    print('=' * 70)
    print(f'交易次数: {len(trades)}')

    if skipped:
        for k, v in skipped.items():
            print(f'{k}: {v}次')
    if delayed:
        print(f'跌停延迟卖出: {delayed}次')
    if stopped:
        print(f'止损触发: {stopped}次')

    if not trades:
        print('无交易')
        return

    r = np.array([t['return_pct'] for t in trades])
    w = sum(r > 0)
    l = sum(r < 0)
    win_rate = w / len(r) * 100
    avg_ret = r.mean()
    cum_ret = r.sum()
    std_ret = r.std()

    equity = pd.Series((1 + r / 100).cumprod())
    total_return = (equity.iloc[-1] - 1) * 100
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min() * 100

    avg_win = r[r > 0].mean() if w > 0 else 0
    avg_loss = r[r < 0].mean() if l > 0 else 0
    profit_factor = abs(r[r > 0].sum() / r[r < 0].sum()) if l > 0 and r[r < 0].sum() != 0 else float('inf')

    # 实际最大亏损（修复后能看到真实亏损）
    max_loss = r.min()
    max_loss_trade = trades[np.argmin(r)]
    max_loss_code = max_loss_trade.get('code', '')

    print(f'胜率: {win_rate:.1f}% ({w}胜/{l}负)')
    print(f'平均收益: {avg_ret:.2f}%')
    print(f'累计等权收益: {cum_ret:.2f}%')
    print(f'累计净值收益: {total_return:.2f}%')
    print(f'最大回撤: {max_dd:.2f}%')
    print(f'收益标准差: {std_ret:.2f}%')
    print(f'盈亏比: {avg_win:.2f}% / {avg_loss:.2f}% = {abs(avg_win / avg_loss) if avg_loss != 0 else 0:.2f}')
    print(f'利润因子: {profit_factor:.2f}')
    print(f'单笔最大亏损: {max_loss:.2f}% ({max_loss_trade["stock"]} {max_loss_code})')

    # 按情绪周期统计
    print()
    print('按情绪周期统计:')
    phase_ret = defaultdict(list)
    for t in trades:
        phase_ret[t.get('phase', '震荡')].append(t['return_pct'])
    for phase in ['冰点', '修复', '高潮', '退潮', '震荡']:
        rr = phase_ret.get(phase, [])
        if rr:
            arr = np.array(rr)
            wr = sum(arr > 0) / len(arr) * 100
            print(f'  {phase}: {len(arr)}笔 胜率{wr:.0f}% 平均{arr.mean():+.2f}%')


def print_portfolio_summary(trade_log, daily_log):
    """输出组合模拟结果"""
    if not daily_log:
        return
    df = pd.DataFrame(daily_log)
    final = df.iloc[-1]
    total_ret = (final['portfolio_value'] / 1000000 - 1) * 100
    max_dd = ((df['portfolio_value'] / df['portfolio_value'].cummax()) - 1).min() * 100

    print()
    print('=' * 60)
    print('  组合模拟结果（资金管理版）')
    print('=' * 60)
    print(f'  最终净值: {final["portfolio_value"]:.2f}  总收益: {total_ret:.2f}%')
    print(f'  最大回撤: {max_dd:.2f}%')
    print(f'  平均持仓数: {df["num_positions"].mean():.1f}')

    if trade_log:
        valid = [t for t in trade_log if not t.get('skipped')]
        if valid:
            r = np.array([t['return_pct'] for t in valid])
            w = sum(r > 0)
            print(f'  交易笔数: {len(valid)}  胜率: {w/len(r)*100:.1f}%')
            print(f'  平均单笔收益: {r.mean():+.2f}%')

            # 按情绪周期统计收益率
            phase_trades = defaultdict(list)
            for t in valid:
                phase_trades[t.get('phase', '震荡')].append(t['return_pct'])
            print('\n  分阶段表现:')
            for phase in ['冰点', '修复', '高潮', '退潮', '震荡']:
                rr = phase_trades.get(phase, [])
                if rr:
                    arr = np.array(rr)
                    print(f'    {phase}: {len(arr)}笔 胜率{sum(arr>0)/len(arr)*100:.0f}% 平均{arr.mean():+.2f}%')


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    engine = BacktestEngineV2()

    print('=' * 70)
    print('  回测引擎 v2（基于投资原则）')
    print('=' * 70)

    # 简化回测（等权，跟旧版对比）
    trades, skipped, stopped, delayed = engine.run_simple_backtest()
    print_stats(trades, '隔日+止损-5%（实算按实际价格）', skipped, stopped, delayed)

    # 组合模拟（资金管理版）
    trade_log, daily_log = engine.run_portfolio()
    print_portfolio_summary(trade_log, daily_log)

    # 保存结果
    output = {
        'simple_trades': trades,
        'portfolio_trades': trade_log,
    }
    with open(os.path.join(ROOT, 'backtest_trades_v2.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n结果已保存到 backtest_trades_v2.json')
