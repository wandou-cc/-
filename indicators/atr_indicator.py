# -*- coding: utf-8 -*-
"""
ATR (Average True Range) 平均真实波动幅度指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional


class ATRIndicator:
    """
    ATR指标计算类（无状态版本）

    ATR用于衡量市场波动率：
    1. TR (True Range) = max(H-L, |H-PC|, |L-PC|)
       其中 H=最高价, L=最低价, PC=前收盘价
    2. ATR = TR的移动平均（使用Wilder平滑法）
    """

    def __init__(self, period: int = 14):
        """
        初始化ATR指标参数

        Args:
            period: ATR计算周期，默认14
        """
        self.period = period

    def _calculate_true_range(self, high: float, low: float, previous_close: Optional[float]) -> float:
        """
        计算真实波动幅度(TR)

        Args:
            high: 当前最高价
            low: 当前最低价
            previous_close: 前一日收盘价

        Returns:
            TR值
        """
        if previous_close is None:
            return high - low

        tr1 = high - low
        tr2 = abs(high - previous_close)
        tr3 = abs(low - previous_close)

        return max(tr1, tr2, tr3)

    def calculate(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """
        计算ATR指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含ATR和TR值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        n = len(closes)
        if n == 0:
            return {
                'atr': None,
                'tr': None,
                'atr_series': [],
                'tr_series': []
            }

        # 计算所有TR值（首根bar没有前收盘价，仅记录high-low）
        tr_series = [None] * n
        tr_values = []

        if n > 0:
            tr_series[0] = self._calculate_true_range(highs[0], lows[0], None)

        for i in range(1, n):
            prev_close = closes[i - 1]
            tr = self._calculate_true_range(highs[i], lows[i], prev_close)
            tr_values.append(tr)
            tr_series[i] = tr

        # 计算ATR并与价格序列对齐（需要至少period+1根K线）
        atr_series = [None] * n
        atr = None

        if len(tr_values) >= self.period:
            atr = sum(tr_values[:self.period]) / self.period
            atr_index = self.period
            if atr_index < n:
                atr_series[atr_index] = atr

            for idx in range(self.period, len(tr_values)):
                tr = tr_values[idx]
                atr = (atr * (self.period - 1) + tr) / self.period
                price_index = idx + 1
                if price_index < n:
                    atr_series[price_index] = atr

        return {
            'atr': atr_series[-1] if atr_series else None,
            'tr': tr_series[-1] if tr_series else None,
            'atr_series': atr_series,
            'tr_series': tr_series
        }

    def calculate_latest(self, highs: List[float], lows: List[float], closes: List[float]) -> Optional[float]:
        """
        快捷方法：只返回最新的ATR值

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            最新的ATR值，数据不足返回None
        """
        result = self.calculate(highs, lows, closes)
        return result['atr']

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'period': self.period
        }

    def set_parameters(self, period: int = None):
        """
        更新参数设置

        Args:
            period: ATR计算周期
        """
        if period is not None:
            self.period = period


class ATRAnalyzer:
    """
    ATR分析器（无状态版本），提供波动率分析和止损建议
    """

    def __init__(self, period: int = 14):
        """
        初始化ATR分析器

        Args:
            period: ATR周期
        """
        self.indicator = ATRIndicator(period)

    def analyze(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """
        综合分析ATR（无状态，基于完整历史数据）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含ATR值、波动率水平等的综合分析字典
        """
        result = self.indicator.calculate(highs, lows, closes)
        atr = result['atr']
        atr_series = result['atr_series']

        if atr is None:
            return {
                'atr': None,
                'tr': None,
                'volatility_level': 'UNKNOWN',
                'stop_loss_distance': None
            }

        # 判断波动率水平
        volatility_level = 'MEDIUM'
        valid_atr_series = [value for value in atr_series if value is not None]
        if len(valid_atr_series) >= 20:
            recent_atr = valid_atr_series[-20:]
            avg_atr = sum(recent_atr) / len(recent_atr)
            if avg_atr != 0:
                ratio = atr / avg_atr
                if ratio > 1.5:
                    volatility_level = 'VERY_HIGH'
                elif ratio > 1.2:
                    volatility_level = 'HIGH'
                elif ratio > 0.8:
                    volatility_level = 'MEDIUM'
                else:
                    volatility_level = 'LOW'

        return {
            'atr': atr,
            'tr': result['tr'],
            'atr_series': atr_series,
            'tr_series': result['tr_series'],
            'volatility_level': volatility_level,
            'stop_loss_distance': atr * 2.0  # 默认2倍ATR止损
        }

    def get_volatility_level(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取波动率水平

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'VERY_HIGH', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
        """
        return self.analyze(highs, lows, closes)['volatility_level']

    def get_stop_loss_distance(self, highs: List[float], lows: List[float], closes: List[float],
                               multiplier: float = 2.0) -> Optional[float]:
        """
        获取建议的止损距离

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            multiplier: ATR倍数，默认2.0

        Returns:
            建议的止损距离
        """
        result = self.indicator.calculate(highs, lows, closes)
        if result['atr'] is None:
            return None
        return result['atr'] * multiplier

    def is_breakout_valid(self, highs: List[float], lows: List[float], closes: List[float],
                          price_move: float, threshold: float = 1.0) -> bool:
        """
        判断突破是否有效（价格移动是否超过ATR的一定倍数）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            price_move: 价格移动幅度
            threshold: ATR倍数阈值，默认1.0

        Returns:
            True: 突破有效, False: 突破无效
        """
        result = self.indicator.calculate(highs, lows, closes)
        if result['atr'] is None:
            return False
        return abs(price_move) > (result['atr'] * threshold)
