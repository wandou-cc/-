# -*- coding: utf-8 -*-
"""
无状态指标系统 (Stateless Indicators)
适用于实时 WebSocket 推送，可重复计算、可回滚、无副作用。
所有指标均采用 “基于历史数组 + 当前K线” 的即时计算方式。
"""

import numpy as np


# ---------------------------------------------------------
# 1. EMA (内核)
# ---------------------------------------------------------
def ema(values, period):
    """无状态 EMA（每次完整重算）"""
    if len(values) < period:
        return None
    alpha = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = alpha * v + (1 - alpha) * e
    return e


# ---------------------------------------------------------
# 2. EMA 四线趋势
# ---------------------------------------------------------
class EMAStateless:
    def __init__(self, uf=7, fast=20, medium=60, slow=120):
        self.periods = dict(
            ultra_fast=uf,
            fast=fast,
            medium=medium,
            slow=slow
        )

    def calculate_all(self, closes):
        return dict(
            ema_ultra_fast=ema(closes, self.periods["ultra_fast"]),
            ema_fast=ema(closes, self.periods["fast"]),
            ema_medium=ema(closes, self.periods["medium"]),
            ema_slow=ema(closes, self.periods["slow"])
        )


# ---------------------------------------------------------
# 3. RSI（无状态）
# ---------------------------------------------------------
class RSIStateless:
    def __init__(self, period=14):
        self.period = period

    def calculate(self, closes):
        if len(closes) < self.period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period

        for i in range(self.period, len(gains)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - 100 / (1 + rs)


# ---------------------------------------------------------
# 4. KDJ（无状态）
# ---------------------------------------------------------
class KDJStateless:
    def __init__(self, period=9, smooth_k=3, smooth_d=3):
        self.period = period
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d

    def calculate(self, highs, lows, closes):
        n = len(closes)
        if n < self.period:
            return None, None, None

        ll = min(lows[-self.period:])
        hh = max(highs[-self.period:])
        rsv = (closes[-1] - ll) / (hh - ll) * 100 if hh != ll else 50

        # K, D 无状态：用前 smooth_k 根 RSV 重算
        if n < self.period + self.smooth_k:
            return None, None, None

        # 计算 RSV 序列
        rsv_list = []
        for i in range(n - self.smooth_k, n):
            ll_i = min(lows[i - self.period + 1:i + 1])
            hh_i = max(highs[i - self.period + 1:i + 1])
            rsv_i = (closes[i] - ll_i) / (hh_i - ll_i) * 100 if hh_i != ll_i else 50
            rsv_list.append(rsv_i)

        k = sum(rsv_list[-self.smooth_k:]) / self.smooth_k
        d = sum(rsv_list[-self.smooth_d:]) / self.smooth_d
        j = 3 * k - 2 * d
        return k, d, j


# ---------------------------------------------------------
# 5. MACD（无状态）
# ---------------------------------------------------------
class MACDStateless:
    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(self, closes):
        if len(closes) < self.slow + self.signal:
            return None, None, None

        fast_ema = ema(closes, self.fast)
        slow_ema = ema(closes, self.slow)
        macd_val = fast_ema - slow_ema

        # 计算 DIFF 数组
        diffs = []
        e_fast = sum(closes[:self.fast]) / self.fast
        for v in closes[self.fast:]:
            e_fast = (2 / (self.fast + 1)) * v + (1 - 2 / (self.fast + 1)) * e_fast
            diffs.append(e_fast)

        e_slow = sum(closes[:self.slow]) / self.slow
        real_diffs = []
        idx = 0
        for v in closes[self.slow:]:
            e_slow = (2 / (self.slow + 1)) * v + (1 - 2 / (self.slow + 1)) * e_slow
            real_diffs.append(diffs[idx] - e_slow)
            idx += 1
            if idx >= len(diffs):
                break

        signal_line = ema(real_diffs, self.signal)
        histogram = macd_val - signal_line

        return macd_val, signal_line, histogram


# ---------------------------------------------------------
# 6. BOLL（无状态）
# ---------------------------------------------------------
class BOLLStateless:
    def __init__(self, period=20, std_factor=2):
        self.period = period
        self.std_factor = std_factor

    def calculate(self, closes):
        if len(closes) < self.period:
            return None, None, None, None
        subset = closes[-self.period:]
        mid = sum(subset) / self.period
        std = np.std(subset)
        upper = mid + self.std_factor * std
        lower = mid - self.std_factor * std
        percent_b = (closes[-1] - lower) / (upper - lower) if upper != lower else 0.5
        return upper, mid, lower, percent_b


# ---------------------------------------------------------
# 7. CCI（无状态）
# ---------------------------------------------------------
class CCIStateless:
    def __init__(self, period=20):
        self.period = period

    def calculate(self, highs, lows, closes):
        n = len(closes)
        if n < self.period:
            return None
        tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
        ma = sum(tp[-self.period:]) / self.period
        md = sum(abs(x - ma) for x in tp[-self.period:]) / self.period
        if md == 0:
            return 0
        return (tp[-1] - ma) / (0.015 * md)


# ---------------------------------------------------------
# 8. ATR（无状态）
# ---------------------------------------------------------
class ATRStateless:
    def __init__(self, period=14):
        self.period = period

    def calculate(self, highs, lows, closes):
        n = len(closes)
        if n < self.period + 1:
            return None
        trs = []
        for i in range(1, n):
            h = highs[i]
            l = lows[i]
            pc = closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        first_atr = sum(trs[:self.period]) / self.period
        atr = first_atr
        for i in range(self.period, len(trs)):
            atr = (atr * (self.period - 1) + trs[i]) / self.period
        return atr


# ---------------------------------------------------------
# 9. VWAP（无状态版本）
# ---------------------------------------------------------
class VWAPStateless:
    """
    无状态 VWAP：基于完整K线历史计算
    VWAP = Σ(典型价格 * 成交量) / Σ(成交量)
    典型价格 = (最高价 + 最低价 + 收盘价) / 3
    """

    def calculate(self, highs, lows, closes, volumes):
        """
        计算 VWAP

        Args:
            highs: 最高价数组
            lows: 最低价数组
            closes: 收盘价数组
            volumes: 成交量数组

        Returns:
            VWAP 值，如果成交量为0则返回 None
        """
        if len(closes) == 0:
            return None

        cumulative_pv = 0
        cumulative_volume = 0

        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_pv += typical_price * volumes[i]
            cumulative_volume += volumes[i]

        if cumulative_volume == 0:
            return None

        return cumulative_pv / cumulative_volume


# ---------------------------------------------------------
# 9b. VWAP（实时累积版本 - 保留兼容）
# ---------------------------------------------------------
class VWAPRealtime:
    """
    VWAP 必须跨天reset，否则会累计整个月的数据
    注意：此版本有状态，在实时重复推送场景下需要配合回滚使用
    """
    def __init__(self):
        self.cumulative_pv = 0
        self.cumulative_volume = 0

    def update(self, price, volume):
        self.cumulative_pv += price * volume
        self.cumulative_volume += volume
        if self.cumulative_volume == 0:
            return None
        return self.cumulative_pv / self.cumulative_volume

    def reset(self):
        self.cumulative_pv = 0
        self.cumulative_volume = 0
