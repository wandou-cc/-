# -*- coding: utf-8 -*-
"""
ADX (Average Directional Index) 平均趋向指数指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用

ADX 用于衡量趋势的强度（不判断方向）：
- ADX < 20: 无趋势/震荡市场
- ADX 20-25: 趋势开始形成
- ADX 25-40: 趋势较强
- ADX 40-50: 强趋势
- ADX > 50: 极强趋势（较少见）

+DI 和 -DI 用于判断趋势方向：
- +DI > -DI: 上升趋势
- -DI > +DI: 下降趋势
"""

from typing import List, Dict, Any, Optional
from enum import Enum


class TrendDirection(Enum):
    """趋势方向枚举"""
    UP = "up"
    DOWN = "down"
    NONE = "none"


class TrendStrength(Enum):
    """趋势强度枚举"""
    NO_TREND = "no_trend"          # ADX < 20
    WEAK = "weak"                   # ADX 20-25
    MODERATE = "moderate"           # ADX 25-40
    STRONG = "strong"               # ADX 40-50
    VERY_STRONG = "very_strong"     # ADX > 50


class ADXIndicator:
    """
    ADX指标计算类（无状态版本）

    计算步骤：
    1. TR (True Range) = max(H-L, |H-PC|, |L-PC|)
    2. +DM = H - PH (若 > 0 且 > |L-PL|，否则为0)
    3. -DM = PL - L (若 > 0 且 > H-PH，否则为0)
    4. Smoothed TR/+DM/-DM = Wilder平滑 (初始为SMA，后续用 prev*(n-1)/n + current/n)
    5. +DI = 100 * Smoothed(+DM) / Smoothed(TR)
    6. -DI = 100 * Smoothed(-DM) / Smoothed(TR)
    7. DX = 100 * |+DI - -DI| / (+DI + -DI)
    8. ADX = Wilder平滑(DX)
    """

    def __init__(self, period: int = 14):
        """
        初始化ADX指标参数

        Args:
            period: ADX计算周期，默认14（TradingView标准）
        """
        self.period = period

    def _calculate_true_range(self, high: float, low: float, prev_close: Optional[float]) -> float:
        """
        计算真实波动幅度(TR)

        Args:
            high: 当前最高价
            low: 当前最低价
            prev_close: 前一根K线收盘价

        Returns:
            TR值
        """
        if prev_close is None:
            return high - low

        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        return max(tr1, tr2, tr3)

    def _calculate_directional_movement(
        self,
        high: float,
        low: float,
        prev_high: float,
        prev_low: float
    ) -> tuple:
        """
        计算方向性移动 (+DM 和 -DM)

        Args:
            high: 当前最高价
            low: 当前最低价
            prev_high: 前一根K线最高价
            prev_low: 前一根K线最低价

        Returns:
            (+DM, -DM) 元组
        """
        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = 0.0
        minus_dm = 0.0

        if up_move > down_move and up_move > 0:
            plus_dm = up_move
        if down_move > up_move and down_move > 0:
            minus_dm = down_move

        return plus_dm, minus_dm

    def _wilder_smooth(self, values: List[float], period: int) -> List[Optional[float]]:
        """
        Wilder平滑方法
        - 第一个值使用SMA
        - 后续使用: prev * (period-1)/period + current/period

        Args:
            values: 原始数据序列
            period: 平滑周期

        Returns:
            平滑后的序列
        """
        n = len(values)
        result = [None] * n

        if n < period:
            return result

        # 第一个平滑值 = 前period个值的SMA
        first_smooth = sum(values[:period]) / period
        result[period - 1] = first_smooth

        # 后续使用Wilder平滑
        prev_smooth = first_smooth
        for i in range(period, n):
            smoothed = (prev_smooth * (period - 1) + values[i]) / period
            result[i] = smoothed
            prev_smooth = smoothed

        return result

    def calculate(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> Dict[str, Any]:
        """
        计算ADX指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含ADX、+DI、-DI等指标的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        n = len(closes)
        if n < 2:
            return {
                'adx': None,
                'plus_di': None,
                'minus_di': None,
                'dx': None,
                'adx_series': [],
                'plus_di_series': [],
                'minus_di_series': [],
                'dx_series': []
            }

        # 步骤1: 计算TR、+DM、-DM序列
        tr_values = []
        plus_dm_values = []
        minus_dm_values = []

        for i in range(1, n):
            # TR
            tr = self._calculate_true_range(highs[i], lows[i], closes[i-1])
            tr_values.append(tr)

            # +DM, -DM
            plus_dm, minus_dm = self._calculate_directional_movement(
                highs[i], lows[i], highs[i-1], lows[i-1]
            )
            plus_dm_values.append(plus_dm)
            minus_dm_values.append(minus_dm)

        # 步骤2: Wilder平滑 TR、+DM、-DM
        smoothed_tr = self._wilder_smooth(tr_values, self.period)
        smoothed_plus_dm = self._wilder_smooth(plus_dm_values, self.period)
        smoothed_minus_dm = self._wilder_smooth(minus_dm_values, self.period)

        # 步骤3: 计算 +DI、-DI
        plus_di_values = []
        minus_di_values = []

        for i in range(len(smoothed_tr)):
            if smoothed_tr[i] is not None and smoothed_tr[i] > 0:
                plus_di = 100 * smoothed_plus_dm[i] / smoothed_tr[i]
                minus_di = 100 * smoothed_minus_dm[i] / smoothed_tr[i]
            else:
                plus_di = None
                minus_di = None
            plus_di_values.append(plus_di)
            minus_di_values.append(minus_di)

        # 步骤4: 计算 DX
        dx_values = []
        for i in range(len(plus_di_values)):
            if plus_di_values[i] is not None and minus_di_values[i] is not None:
                di_sum = plus_di_values[i] + minus_di_values[i]
                if di_sum > 0:
                    dx = 100 * abs(plus_di_values[i] - minus_di_values[i]) / di_sum
                else:
                    dx = 0
            else:
                dx = None
            dx_values.append(dx)

        # 步骤5: 对DX进行Wilder平滑得到ADX
        # 需要过滤掉None值来计算
        valid_dx_start = None
        for i, dx in enumerate(dx_values):
            if dx is not None:
                valid_dx_start = i
                break

        adx_values = [None] * len(dx_values)

        if valid_dx_start is not None:
            valid_dx = [dx for dx in dx_values[valid_dx_start:] if dx is not None]
            if len(valid_dx) >= self.period:
                # 第一个ADX = 前period个DX的SMA
                first_adx = sum(valid_dx[:self.period]) / self.period
                adx_idx = valid_dx_start + self.period - 1
                if adx_idx < len(adx_values):
                    adx_values[adx_idx] = first_adx

                # 后续ADX使用Wilder平滑
                prev_adx = first_adx
                for i in range(self.period, len(valid_dx)):
                    adx = (prev_adx * (self.period - 1) + valid_dx[i]) / self.period
                    adx_idx = valid_dx_start + i
                    if adx_idx < len(adx_values):
                        adx_values[adx_idx] = adx
                    prev_adx = adx

        # 将计算结果与原始价格序列对齐（偏移1，因为从第二根K线开始计算）
        adx_series = [None] + adx_values
        plus_di_series = [None] + plus_di_values
        minus_di_series = [None] + minus_di_values
        dx_series = [None] + dx_values

        # 确保长度与输入一致
        adx_series = adx_series[:n] if len(adx_series) > n else adx_series + [None] * (n - len(adx_series))
        plus_di_series = plus_di_series[:n] if len(plus_di_series) > n else plus_di_series + [None] * (n - len(plus_di_series))
        minus_di_series = minus_di_series[:n] if len(minus_di_series) > n else minus_di_series + [None] * (n - len(minus_di_series))
        dx_series = dx_series[:n] if len(dx_series) > n else dx_series + [None] * (n - len(dx_series))

        return {
            'adx': adx_series[-1] if adx_series else None,
            'plus_di': plus_di_series[-1] if plus_di_series else None,
            'minus_di': minus_di_series[-1] if minus_di_series else None,
            'dx': dx_series[-1] if dx_series else None,
            'adx_series': adx_series,
            'plus_di_series': plus_di_series,
            'minus_di_series': minus_di_series,
            'dx_series': dx_series
        }

    def calculate_latest(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的ADX、+DI、-DI值

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含最新ADX、+DI、-DI的字典
        """
        result = self.calculate(highs, lows, closes)
        return {
            'adx': result['adx'],
            'plus_di': result['plus_di'],
            'minus_di': result['minus_di'],
            'dx': result['dx']
        }

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {'period': self.period}

    def set_parameters(self, period: int = None):
        """更新参数设置"""
        if period is not None:
            self.period = period


class ADXAnalyzer:
    """
    ADX分析器（无状态版本），提供趋势强度和方向分析
    """

    def __init__(
        self,
        period: int = 14,
        no_trend_threshold: float = 20.0,
        weak_threshold: float = 25.0,
        moderate_threshold: float = 40.0,
        strong_threshold: float = 50.0
    ):
        """
        初始化ADX分析器

        Args:
            period: ADX周期
            no_trend_threshold: 无趋势阈值（ADX低于此值认为无趋势）
            weak_threshold: 弱趋势阈值
            moderate_threshold: 中等趋势阈值
            strong_threshold: 强趋势阈值
        """
        self.indicator = ADXIndicator(period)
        self.no_trend_threshold = no_trend_threshold
        self.weak_threshold = weak_threshold
        self.moderate_threshold = moderate_threshold
        self.strong_threshold = strong_threshold

    def analyze(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> Dict[str, Any]:
        """
        综合分析ADX

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含ADX值、趋势强度、趋势方向等的综合分析字典
        """
        result = self.indicator.calculate(highs, lows, closes)

        adx = result['adx']
        plus_di = result['plus_di']
        minus_di = result['minus_di']

        if adx is None:
            return {
                'adx': None,
                'plus_di': None,
                'minus_di': None,
                'trend_strength': TrendStrength.NO_TREND,
                'trend_direction': TrendDirection.NONE,
                'is_trending': False,
                'adx_rising': None,
                'di_crossover': None,
                **result
            }

        # 判断趋势强度
        trend_strength = self._get_trend_strength(adx)

        # 判断趋势方向
        trend_direction = TrendDirection.NONE
        if plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                trend_direction = TrendDirection.UP
            elif minus_di > plus_di:
                trend_direction = TrendDirection.DOWN

        # 是否处于趋势中
        is_trending = adx >= self.no_trend_threshold

        # ADX是否上升（趋势加强）
        adx_rising = None
        adx_series = result['adx_series']
        valid_adx = [v for v in adx_series if v is not None]
        if len(valid_adx) >= 2:
            adx_rising = valid_adx[-1] > valid_adx[-2]

        # DI交叉检测
        di_crossover = self._detect_di_crossover(
            result['plus_di_series'],
            result['minus_di_series']
        )

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'trend_strength': trend_strength,
            'trend_direction': trend_direction,
            'is_trending': is_trending,
            'adx_rising': adx_rising,
            'di_crossover': di_crossover,
            'adx_series': result['adx_series'],
            'plus_di_series': result['plus_di_series'],
            'minus_di_series': result['minus_di_series']
        }

    def _get_trend_strength(self, adx: float) -> TrendStrength:
        """根据ADX值判断趋势强度"""
        if adx < self.no_trend_threshold:
            return TrendStrength.NO_TREND
        elif adx < self.weak_threshold:
            return TrendStrength.WEAK
        elif adx < self.moderate_threshold:
            return TrendStrength.MODERATE
        elif adx < self.strong_threshold:
            return TrendStrength.STRONG
        else:
            return TrendStrength.VERY_STRONG

    def _detect_di_crossover(
        self,
        plus_di_series: List[Optional[float]],
        minus_di_series: List[Optional[float]]
    ) -> Optional[str]:
        """
        检测DI交叉

        Returns:
            'bullish_crossover': +DI上穿-DI（看涨）
            'bearish_crossover': +DI下穿-DI（看跌）
            None: 无交叉
        """
        # 获取最近两个有效值
        valid_pairs = []
        for i in range(len(plus_di_series) - 1, -1, -1):
            if plus_di_series[i] is not None and minus_di_series[i] is not None:
                valid_pairs.append((plus_di_series[i], minus_di_series[i]))
                if len(valid_pairs) >= 2:
                    break

        if len(valid_pairs) < 2:
            return None

        current_plus, current_minus = valid_pairs[0]
        prev_plus, prev_minus = valid_pairs[1]

        # +DI上穿-DI
        if prev_plus <= prev_minus and current_plus > current_minus:
            return 'bullish_crossover'

        # +DI下穿-DI
        if prev_plus >= prev_minus and current_plus < current_minus:
            return 'bearish_crossover'

        return None

    def get_trend_strength(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> TrendStrength:
        """快捷方法：获取趋势强度"""
        return self.analyze(highs, lows, closes)['trend_strength']

    def get_trend_direction(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> TrendDirection:
        """快捷方法：获取趋势方向"""
        return self.analyze(highs, lows, closes)['trend_direction']

    def is_trending_market(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> bool:
        """快捷方法：判断是否处于趋势市场"""
        return self.analyze(highs, lows, closes)['is_trending']
