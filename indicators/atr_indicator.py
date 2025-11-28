# -*- coding: utf-8 -*-
"""
ATR (Average True Range) 平均真实波动幅度指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


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

    def calculate(self, highs: List[float], lows: List[float], closes: List[float],
                  reverse: bool = False) -> Dict[str, Any]:
        """
        计算ATR指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含ATR和TR值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        if reverse:
            highs = list(reversed(highs))
            lows = list(reversed(lows))
            closes = list(reversed(closes))

        n = len(closes)
        if n < self.period + 1:
            return {
                'atr': None,
                'tr': None,
                'atr_series': [],
                'tr_series': []
            }

        # 计算所有TR值
        tr_values = []
        for i in range(n):
            if i == 0:
                tr = highs[i] - lows[i]
            else:
                tr = self._calculate_true_range(highs[i], lows[i], closes[i - 1])
            tr_values.append(tr)

        # 计算ATR（使用Wilder平滑法）
        atr_values = []

        # 初始ATR = 前N个TR的平均值（SMA）
        # 注意：TR从index 1开始才有意义（需要前收盘价）
        initial_atr = sum(tr_values[1:self.period + 1]) / self.period
        atr = initial_atr
        atr_values.append(atr)

        # 后续ATR使用Wilder平滑法
        for i in range(self.period + 1, len(tr_values)):
            atr = (atr * (self.period - 1) + tr_values[i]) / self.period
            atr_values.append(atr)

        # 对齐TR序列（从period开始）
        aligned_tr = tr_values[self.period:]

        if reverse:
            atr_values = list(reversed(atr_values))
            aligned_tr = list(reversed(aligned_tr))

        return {
            'atr': atr_values[-1] if atr_values else None,
            'tr': aligned_tr[-1] if aligned_tr else None,
            'atr_series': atr_values,
            'tr_series': aligned_tr
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
        if len(atr_series) >= 20:
            recent_atr = atr_series[-20:]
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
