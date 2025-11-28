# -*- coding: utf-8 -*-
"""
MACD (Moving Average Convergence Divergence) 指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


def _ema(values: List[float], period: int) -> List[float]:
    """
    计算EMA序列（内部函数）

    Args:
        values: 数值序列
        period: EMA周期

    Returns:
        EMA值序列
    """
    if len(values) < period:
        return []

    alpha = 2.0 / (period + 1)
    ema_values = []

    # 使用前period个数据的SMA作为初始EMA
    ema = sum(values[:period]) / period

    for i in range(period - 1, len(values)):
        if i == period - 1:
            ema_values.append(ema)
        else:
            ema = alpha * values[i] + (1 - alpha) * ema
            ema_values.append(ema)

    return ema_values


class MACDIndicator:
    """
    MACD指标计算类（无状态版本）

    MACD指标包含三个主要组成部分：
    1. MACD线 = EMA(fast) - EMA(slow)
    2. 信号线 = EMA(signal) of MACD线
    3. 柱状图 = MACD线 - 信号线
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        初始化MACD指标参数

        Args:
            fast_period: 快速EMA周期，默认12
            slow_period: 慢速EMA周期，默认26
            signal_period: 信号线EMA周期，默认9
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, closes: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算MACD指标（无状态，每次完整重算）

        Args:
            closes: 收盘价序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含MACD线、信号线、柱状图的字典
        """
        if reverse:
            closes = list(reversed(closes))

        if len(closes) < self.slow_period + self.signal_period - 1:
            return {
                'macd_line': None,
                'signal_line': None,
                'histogram': None,
                'macd_series': [],
                'signal_series': [],
                'histogram_series': []
            }

        # 计算快速和慢速EMA
        ema_fast = _ema(closes, self.fast_period)
        ema_slow = _ema(closes, self.slow_period)

        # 对齐数据：ema_slow 比 ema_fast 晚开始
        offset = len(ema_fast) - len(ema_slow)
        if offset > 0:
            ema_fast = ema_fast[offset:]

        # 计算MACD线 (DIF)
        macd_line = [fast - slow for fast, slow in zip(ema_fast, ema_slow)]

        # 计算信号线 (DEA)
        signal_line = _ema(macd_line, self.signal_period)

        # 对齐MACD线和信号线
        offset = len(macd_line) - len(signal_line)
        if offset > 0:
            macd_line = macd_line[offset:]
            ema_fast = ema_fast[offset:]
            ema_slow = ema_slow[offset:]

        # 计算柱状图
        histogram = [macd - signal for macd, signal in zip(macd_line, signal_line)]

        if reverse:
            macd_line = list(reversed(macd_line))
            signal_line = list(reversed(signal_line))
            histogram = list(reversed(histogram))

        return {
            'macd_line': macd_line[-1] if macd_line else None,
            'signal_line': signal_line[-1] if signal_line else None,
            'histogram': histogram[-1] if histogram else None,
            'macd_series': macd_line,
            'signal_series': signal_line,
            'histogram_series': histogram
        }

    def calculate_latest(self, closes: List[float]) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的MACD值

        Args:
            closes: 收盘价序列

        Returns:
            包含最新MACD线、信号线、柱状图的字典
        """
        result = self.calculate(closes)
        return {
            'macd_line': result['macd_line'],
            'signal_line': result['signal_line'],
            'histogram': result['histogram']
        }

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period
        }

    def set_parameters(self, fast_period: int = None, slow_period: int = None, signal_period: int = None):
        """
        更新参数设置

        Args:
            fast_period: 快速EMA周期
            slow_period: 慢速EMA周期
            signal_period: 信号线EMA周期
        """
        if fast_period is not None:
            self.fast_period = fast_period
        if slow_period is not None:
            self.slow_period = slow_period
        if signal_period is not None:
            self.signal_period = signal_period


class MACDAnalyzer:
    """
    MACD分析器（无状态版本），提供买卖信号和趋势分析
    """

    def __init__(self,
                 fast_period: int = 12,
                 slow_period: int = 26,
                 signal_period: int = 9,
                 angle_multiplier: float = 0.5,
                 min_hist_threshold: float = 0.0005,
                 lookback_period: int = 50,
                 min_zero_distance: float = 0.0):
        """
        初始化MACD分析器

        Args:
            fast_period: 快速EMA周期
            slow_period: 慢速EMA周期
            signal_period: 信号线EMA周期
            angle_multiplier: 角度阈值乘数
            min_hist_threshold: 最小柱状图阈值
            lookback_period: 计算标准差的回溯周期
            min_zero_distance: 距离0轴的最小距离
        """
        self.indicator = MACDIndicator(fast_period, slow_period, signal_period)
        self.angle_multiplier = angle_multiplier
        self.min_hist_threshold = min_hist_threshold
        self.lookback_period = lookback_period
        self.min_zero_distance = abs(min_zero_distance)

    def analyze(self, closes: List[float]) -> Dict[str, Any]:
        """
        综合分析MACD（无状态，基于完整历史数据）

        Args:
            closes: 收盘价序列

        Returns:
            包含MACD值、信号、趋势强度等的综合分析字典
        """
        result = self.indicator.calculate(closes)

        macd_series = result['macd_series']
        signal_series = result['signal_series']
        histogram_series = result['histogram_series']

        if not macd_series or len(macd_series) < 2:
            return {
                'macd_line': None,
                'signal_line': None,
                'histogram': None,
                'signal': 'HOLD',
                'cross_type': None,
                'trend_strength': 'NEUTRAL'
            }

        # 检测交叉
        cross_type = None
        signal = 'HOLD'

        prev_macd = macd_series[-2]
        prev_signal = signal_series[-2]
        curr_macd = macd_series[-1]
        curr_signal = signal_series[-1]

        # 金叉
        if prev_macd < prev_signal and curr_macd > curr_signal:
            cross_type = 'golden'
            signal = 'BUY'
        # 死叉
        elif prev_macd > prev_signal and curr_macd < curr_signal:
            cross_type = 'dead'
            signal = 'SELL'

        # 判断趋势强度
        histogram = histogram_series[-1]
        if len(histogram_series) >= 20:
            hist_abs = [abs(h) for h in histogram_series[-50:]]
            hist_75th = np.percentile(hist_abs, 75) if hist_abs else 0
        else:
            hist_75th = abs(histogram) * 0.5

        if curr_macd > curr_signal and histogram > 0:
            if abs(histogram) > hist_75th:
                trend_strength = 'STRONG_BULLISH'
            else:
                trend_strength = 'BULLISH'
        elif curr_macd < curr_signal and histogram < 0:
            if abs(histogram) > hist_75th:
                trend_strength = 'STRONG_BEARISH'
            else:
                trend_strength = 'BEARISH'
        else:
            trend_strength = 'NEUTRAL'

        return {
            'macd_line': result['macd_line'],
            'signal_line': result['signal_line'],
            'histogram': result['histogram'],
            'macd_series': macd_series,
            'signal_series': signal_series,
            'histogram_series': histogram_series,
            'signal': signal,
            'cross_type': cross_type,
            'trend_strength': trend_strength
        }

    def get_signal(self, closes: List[float]) -> str:
        """
        获取交易信号

        Args:
            closes: 收盘价序列

        Returns:
            'BUY', 'SELL', 或 'HOLD'
        """
        return self.analyze(closes)['signal']

    def get_filtered_signal(self, closes: List[float]) -> Dict[str, Any]:
        """
        获取过滤后的交易信号（支持多维度过滤）

        Args:
            closes: 收盘价序列

        Returns:
            包含详细信号信息的字典
        """
        result = self.indicator.calculate(closes)
        macd_series = result['macd_series']
        signal_series = result['signal_series']
        histogram_series = result['histogram_series']

        if not macd_series or len(macd_series) < 2:
            return {
                'signal': 'none',
                'cross_detected': False,
                'conditions': {
                    'angle_check': False,
                    'momentum_check': False,
                    'threshold_check': False,
                    'zero_distance_check': False
                },
                'metrics': {
                    'angle': 0.0,
                    'histogram': 0.0,
                    'macd': 0.0,
                    'signal': 0.0,
                    'zero_distance': 0.0
                }
            }

        curr_macd = macd_series[-1]
        curr_signal = signal_series[-1]
        curr_histogram = histogram_series[-1]
        zero_dist = min(abs(curr_macd), abs(curr_signal))

        # 检测交叉
        prev_macd = macd_series[-2]
        prev_signal = signal_series[-2]
        cross_type = None

        if prev_macd < prev_signal and curr_macd > curr_signal:
            cross_type = 'golden'
        elif prev_macd > prev_signal and curr_macd < curr_signal:
            cross_type = 'dead'

        if cross_type is None:
            return {
                'signal': 'none',
                'cross_detected': False,
                'conditions': {
                    'angle_check': False,
                    'momentum_check': False,
                    'threshold_check': False,
                    'zero_distance_check': False
                },
                'metrics': {
                    'angle': 0.0,
                    'histogram': curr_histogram,
                    'macd': curr_macd,
                    'signal': curr_signal,
                    'zero_distance': zero_dist
                }
            }

        # 检查角度条件
        angle_pass, angle_value = self._check_angle_condition(macd_series, signal_series)

        # 检查动能条件
        momentum_pass = self._check_histogram_momentum(histogram_series, cross_type)

        # 检查阈值条件
        threshold_pass = abs(curr_histogram) > self.min_hist_threshold

        # 检查0轴距离条件
        zero_distance_pass = zero_dist >= self.min_zero_distance if self.min_zero_distance > 0 else True

        conditions_met = sum([angle_pass, momentum_pass, threshold_pass, zero_distance_pass])

        if conditions_met == 4:
            signal_result = f'strong_{cross_type}'
        elif conditions_met >= 2:
            signal_result = f'weak_{cross_type}'
        else:
            signal_result = 'none'

        return {
            'signal': signal_result,
            'cross_detected': True,
            'conditions': {
                'angle_check': angle_pass,
                'momentum_check': momentum_pass,
                'threshold_check': threshold_pass,
                'zero_distance_check': zero_distance_pass
            },
            'metrics': {
                'angle': angle_value,
                'histogram': curr_histogram,
                'macd': curr_macd,
                'signal': curr_signal,
                'zero_distance': zero_dist
            }
        }

    def _check_angle_condition(self, macd_series: List[float], signal_series: List[float]) -> tuple:
        """检查交叉角度条件"""
        lookback = 5
        if len(macd_series) < lookback or len(signal_series) < lookback:
            return False, 0.0

        x = np.arange(lookback)
        macd_recent = macd_series[-lookback:]
        signal_recent = signal_series[-lookback:]

        macd_slope = np.polyfit(x, macd_recent, 1)[0]
        signal_slope = np.polyfit(x, signal_recent, 1)[0]

        angle = abs(macd_slope - signal_slope)

        # 计算动态阈值
        if len(macd_series) >= self.lookback_period:
            macd_diffs = np.diff(macd_series[-self.lookback_period:])
            std_dev = np.std(macd_diffs)
        else:
            macd_diffs = np.diff(macd_series) if len(macd_series) > 1 else [1.0]
            std_dev = np.std(macd_diffs) if len(macd_diffs) > 0 else 1.0

        threshold = std_dev * self.angle_multiplier

        return angle > threshold, angle

    def _check_histogram_momentum(self, histogram_series: List[float], cross_type: str) -> bool:
        """检查柱状图动能条件"""
        lookback = 5
        if len(histogram_series) < lookback:
            return False

        hist = histogram_series[-lookback:]

        if cross_type == 'golden':
            increasing_count = sum(1 for i in range(len(hist) - 1) if hist[i + 1] > hist[i])
            return increasing_count >= 3
        elif cross_type == 'dead':
            decreasing_count = sum(1 for i in range(len(hist) - 1) if hist[i + 1] < hist[i])
            return decreasing_count >= 3

        return False

    def get_trend_strength(self, closes: List[float]) -> str:
        """
        获取趋势强度

        Args:
            closes: 收盘价序列

        Returns:
            'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH'
        """
        return self.analyze(closes)['trend_strength']

    def set_filter_parameters(self,
                              angle_multiplier: float = None,
                              min_hist_threshold: float = None,
                              lookback_period: int = None,
                              min_zero_distance: float = None):
        """
        更新过滤参数

        Args:
            angle_multiplier: 角度阈值乘数
            min_hist_threshold: 最小柱状图阈值
            lookback_period: 计算标准差的回溯周期
            min_zero_distance: 距离0轴的最小距离
        """
        if angle_multiplier is not None:
            self.angle_multiplier = angle_multiplier
        if min_hist_threshold is not None:
            self.min_hist_threshold = min_hist_threshold
        if lookback_period is not None:
            self.lookback_period = lookback_period
        if min_zero_distance is not None:
            self.min_zero_distance = abs(min_zero_distance)
