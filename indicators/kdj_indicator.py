# -*- coding: utf-8 -*-
"""
KDJ (随机指标) 实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
基于TradingView的Pine Script实现，使用bcwsma平滑方法
"""

from typing import List, Dict, Any, Optional
import numpy as np


class KDJIndicator:
    """
    KDJ指标计算类（无状态版本，TradingView标准实现）

    KDJ指标包含三条线：
    1. K线 = bcwsma(RSV, signal, 1)
    2. D线 = bcwsma(K, signal, 1)
    3. J线 = 3K - 2D

    其中：
    - RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) × 100
    - bcwsma是一种特殊的加权移动平均：bcwsma = (m×s + (l-m)×前值) / l
    """

    def __init__(self, period: int = 9, signal: int = 3):
        """
        初始化KDJ指标参数（TradingView标准）

        Args:
            period: RSV计算周期（ilong），默认9
            signal: 平滑周期（isig），默认3
        """
        self.period = period
        self.signal = signal

    def _bcwsma(self, source_values: List[float], length: int, weight: int,
                initial_value: float = 50.0) -> List[float]:
        """
        计算bcwsma（TradingView使用的特殊加权移动平均）

        bcwsma = (weight × source + (length - weight) × 前一个bcwsma) / length

        Args:
            source_values: 源数据序列
            length: 长度参数（isig）
            weight: 权重参数（固定为1）
            initial_value: 初始值（默认50.0，符合TradingView标准）

        Returns:
            bcwsma值序列
        """
        if not source_values:
            return []

        bcwsma_values = []
        bcwsma = initial_value

        for s in source_values:
            bcwsma = (weight * s + (length - weight) * bcwsma) / length
            bcwsma_values.append(bcwsma)

        return bcwsma_values

    def calculate(self, highs: List[float], lows: List[float], closes: List[float],
                  reverse: bool = False) -> Dict[str, Any]:
        """
        计算KDJ指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含K、D、J值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        if reverse:
            highs = list(reversed(highs))
            lows = list(reversed(lows))
            closes = list(reversed(closes))

        if len(closes) < self.period:
            return {
                'k': None,
                'd': None,
                'j': None,
                'k_series': [],
                'd_series': [],
                'j_series': []
            }

        # 第一步：计算RSV
        rsv_values = []
        for i in range(self.period - 1, len(closes)):
            period_highs = highs[i - self.period + 1:i + 1]
            period_lows = lows[i - self.period + 1:i + 1]
            close = closes[i]

            highest = max(period_highs)
            lowest = min(period_lows)

            if highest != lowest:
                rsv = 100 * ((close - lowest) / (highest - lowest))
            else:
                rsv = 50.0

            rsv_values.append(rsv)

        # 第二步：pK = bcwsma(RSV, isig, 1)
        k_values = self._bcwsma(rsv_values, self.signal, 1, initial_value=50.0)

        # 第三步：pD = bcwsma(pK, isig, 1)
        d_values = self._bcwsma(k_values, self.signal, 1, initial_value=50.0)

        # 第四步：pJ = 3 * pK - 2 * pD
        j_values = [3 * k - 2 * d for k, d in zip(k_values, d_values)]

        if reverse:
            k_values = list(reversed(k_values))
            d_values = list(reversed(d_values))
            j_values = list(reversed(j_values))

        return {
            'k': k_values[-1] if k_values else None,
            'd': d_values[-1] if d_values else None,
            'j': j_values[-1] if j_values else None,
            'k_series': k_values,
            'd_series': d_values,
            'j_series': j_values
        }

    def calculate_latest(self, highs: List[float], lows: List[float],
                         closes: List[float]) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的KDJ值

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含最新K、D、J值的字典
        """
        result = self.calculate(highs, lows, closes)
        return {
            'k': result['k'],
            'd': result['d'],
            'j': result['j']
        }

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'signal': self.signal
        }

    def set_parameters(self, period: int = None, signal: int = None):
        """
        更新参数设置

        Args:
            period: RSV计算周期
            signal: 平滑周期
        """
        if period is not None:
            self.period = period
        if signal is not None:
            self.signal = signal


class KDJAnalyzer:
    """
    KDJ分析器（无状态版本），提供买卖信号
    """

    def __init__(self, period: int = 9, signal: int = 3):
        """
        初始化KDJ分析器

        Args:
            period: RSV计算周期
            signal: 平滑周期
        """
        self.indicator = KDJIndicator(period, signal)

    def analyze(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """
        综合分析KDJ（无状态，基于完整历史数据）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含KDJ值、信号、动量水平等的综合分析字典
        """
        result = self.indicator.calculate(highs, lows, closes)

        k = result['k']
        d = result['d']
        j = result['j']
        k_series = result['k_series']
        d_series = result['d_series']

        if k is None or d is None:
            return {
                **result,
                'signal': 'HOLD',
                'momentum_level': 'UNKNOWN',
                'trend_strength': 'UNKNOWN'
            }

        # 检测信号（需要至少2个值来判断交叉）
        signal = 'HOLD'
        if len(k_series) >= 2 and len(d_series) >= 2:
            prev_k = k_series[-2]
            prev_d = d_series[-2]

            # 金叉
            if prev_k <= prev_d and k > d:
                if k < 20 or d < 20:
                    signal = 'STRONG_BUY'
                else:
                    signal = 'BUY'
            # 死叉
            elif prev_k >= prev_d and k < d:
                if k > 80 or d > 80:
                    signal = 'STRONG_SELL'
                else:
                    signal = 'SELL'

        # 动量水平
        if k > 80 and d > 80:
            momentum_level = 'OVERBOUGHT'
        elif k < 20 and d < 20:
            momentum_level = 'OVERSOLD'
        else:
            momentum_level = 'NEUTRAL'

        # 趋势强度
        if k > 80 and d > 80 and j > 80:
            trend_strength = 'STRONG_BULLISH'
        elif k > 50 and d > 50:
            trend_strength = 'BULLISH'
        elif k < 20 and d < 20 and j < 20:
            trend_strength = 'STRONG_BEARISH'
        elif k < 50 and d < 50:
            trend_strength = 'BEARISH'
        else:
            trend_strength = 'NEUTRAL'

        return {
            **result,
            'signal': signal,
            'momentum_level': momentum_level,
            'trend_strength': trend_strength
        }

    def get_signal(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取交易信号

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'BUY', 'STRONG_BUY', 'SELL', 'STRONG_SELL', 或 'HOLD'
        """
        return self.analyze(highs, lows, closes)['signal']

    def get_momentum_level(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取动量水平

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'OVERBOUGHT', 'OVERSOLD', 'NEUTRAL'
        """
        return self.analyze(highs, lows, closes)['momentum_level']

    def get_trend_strength(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取趋势强度

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH'
        """
        return self.analyze(highs, lows, closes)['trend_strength']
