# -*- coding: utf-8 -*-
"""
CCI (Commodity Channel Index) 顺势指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


class CCIIndicator:
    """
    CCI指标计算类（无状态版本，TradingView标准）

    CCI用于衡量价格偏离其统计平均值的程度。

    计算公式：
    1. 典型价格 TP = (高 + 低 + 收) / 3
    2. SMA = TP的简单移动平均
    3. 平均偏差 MD = |TP - SMA| 的平均值
    4. CCI = (TP - SMA) / (0.015 × MD)

    其中0.015是常数，确保70%-80%的CCI值在-100到+100之间
    """

    def __init__(self, period: int = 20):
        """
        初始化CCI指标参数

        Args:
            period: CCI计算周期，默认20
        """
        self.period = period
        self.constant = 0.015

    def _calculate_typical_price(self, high: float, low: float, close: float) -> float:
        """计算典型价格"""
        return (high + low + close) / 3.0

    def calculate(self, highs: List[float], lows: List[float], closes: List[float],
                  reverse: bool = False) -> Dict[str, Any]:
        """
        计算CCI指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含CCI值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        if reverse:
            highs = list(reversed(highs))
            lows = list(reversed(lows))
            closes = list(reversed(closes))

        if len(closes) < self.period:
            return {
                'cci': None,
                'cci_series': [],
                'typical_price': None,
                'sma': None,
                'mean_deviation': None
            }

        # 计算典型价格
        typical_prices = []
        for i in range(len(closes)):
            tp = self._calculate_typical_price(highs[i], lows[i], closes[i])
            typical_prices.append(tp)

        # 计算CCI序列
        cci_values = []
        sma_values = []
        md_values = []

        for i in range(self.period - 1, len(typical_prices)):
            # 当前窗口的典型价格
            window = typical_prices[i - self.period + 1:i + 1]

            # 计算SMA
            current_sma = sum(window) / self.period

            # 计算平均偏差
            deviations = [abs(tp - current_sma) for tp in window]
            current_md = sum(deviations) / self.period

            # 计算CCI
            current_tp = typical_prices[i]
            if current_md != 0:
                cci = (current_tp - current_sma) / (self.constant * current_md)
            else:
                cci = 0.0

            cci_values.append(cci)
            sma_values.append(current_sma)
            md_values.append(current_md)

        if reverse:
            cci_values = list(reversed(cci_values))
            sma_values = list(reversed(sma_values))
            md_values = list(reversed(md_values))

        return {
            'cci': cci_values[-1] if cci_values else None,
            'cci_series': cci_values,
            'typical_price': typical_prices[-1] if typical_prices else None,
            'sma': sma_values[-1] if sma_values else None,
            'mean_deviation': md_values[-1] if md_values else None
        }

    def calculate_latest(self, highs: List[float], lows: List[float],
                         closes: List[float]) -> Optional[float]:
        """
        快捷方法：只返回最新的CCI值

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            最新的CCI值
        """
        result = self.calculate(highs, lows, closes)
        return result['cci']

    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'constant': self.constant
        }

    def set_parameters(self, period: int = None):
        """
        更新参数设置

        Args:
            period: CCI计算周期
        """
        if period is not None:
            self.period = period


class CCIAnalyzer:
    """
    CCI分析器（无状态版本），提供买卖信号和趋势分析
    """

    def __init__(self, period: int = 20, overbought: float = 100, oversold: float = -100):
        """
        初始化CCI分析器

        Args:
            period: CCI周期
            overbought: 超买阈值，默认100
            oversold: 超卖阈值，默认-100
        """
        self.indicator = CCIIndicator(period)
        self.overbought = overbought
        self.oversold = oversold

    def analyze(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """
        综合分析CCI（无状态，基于完整历史数据）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            包含CCI值、信号、动量水平等的综合分析字典
        """
        result = self.indicator.calculate(highs, lows, closes)
        cci = result['cci']
        cci_series = result['cci_series']

        if cci is None:
            return {
                **result,
                'signal': 'HOLD',
                'momentum_level': 'UNKNOWN',
                'trend_direction': 'NEUTRAL'
            }

        # 检测信号（需要至少2个CCI值来检测穿越）
        signal = 'HOLD'
        if len(cci_series) >= 2:
            prev_cci = cci_series[-2]
            curr_cci = cci_series[-1]

            # CCI从超卖区域向上穿越
            if prev_cci <= self.oversold and curr_cci > self.oversold:
                signal = 'BUY'
            # CCI从超买区域向下穿越
            elif prev_cci >= self.overbought and curr_cci < self.overbought:
                signal = 'SELL'

        # 动量水平
        if cci > 200:
            momentum_level = 'STRONG_OVERBOUGHT'
        elif cci > 100:
            momentum_level = 'OVERBOUGHT'
        elif cci > 0:
            momentum_level = 'BULLISH'
        elif cci < -200:
            momentum_level = 'STRONG_OVERSOLD'
        elif cci < -100:
            momentum_level = 'OVERSOLD'
        elif cci < 0:
            momentum_level = 'BEARISH'
        else:
            momentum_level = 'NEUTRAL'

        # 趋势方向
        trend_direction = 'NEUTRAL'
        if len(cci_series) >= 2:
            prev_cci = cci_series[-2]
            if cci > 0 and cci > prev_cci:
                trend_direction = 'UPTREND'
            elif cci < 0 and cci < prev_cci:
                trend_direction = 'DOWNTREND'

        return {
            **result,
            'signal': signal,
            'momentum_level': momentum_level,
            'trend_direction': trend_direction
        }

    def get_signal(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取交易信号

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'BUY', 'SELL', 或 'HOLD'
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
            动量水平字符串
        """
        return self.analyze(highs, lows, closes)['momentum_level']

    def get_trend_direction(self, highs: List[float], lows: List[float], closes: List[float]) -> str:
        """
        获取趋势方向

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列

        Returns:
            'UPTREND', 'DOWNTREND', 'NEUTRAL'
        """
        return self.analyze(highs, lows, closes)['trend_direction']

    def detect_divergence(self, highs: List[float], lows: List[float], closes: List[float],
                          lookback: int = 5) -> str:
        """
        检测CCI背离信号（无状态）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            lookback: 回看周期

        Returns:
            'BULLISH_DIVERGENCE': 看涨背离
            'BEARISH_DIVERGENCE': 看跌背离
            'NO_DIVERGENCE': 无背离
        """
        result = self.indicator.calculate(highs, lows, closes)
        cci_series = result['cci_series']

        if len(cci_series) < lookback or len(closes) < lookback:
            return 'NO_DIVERGENCE'

        recent_prices = closes[-lookback:]
        recent_cci = cci_series[-lookback:]

        price_trend = recent_prices[-1] - recent_prices[0]
        cci_trend = recent_cci[-1] - recent_cci[0]

        # 看涨背离：价格下跌但CCI上升
        if price_trend < 0 and cci_trend > 0:
            return 'BULLISH_DIVERGENCE'

        # 看跌背离：价格上涨但CCI下降
        elif price_trend > 0 and cci_trend < 0:
            return 'BEARISH_DIVERGENCE'

        return 'NO_DIVERGENCE'
