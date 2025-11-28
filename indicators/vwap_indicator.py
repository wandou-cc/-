# -*- coding: utf-8 -*-
"""
VWAP (Volume Weighted Average Price) 成交量加权平均价实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


class VWAPIndicator:
    """
    VWAP指标计算类（无状态版本）

    VWAP = Σ(典型价格 × 成交量) / Σ(成交量)
    典型价格 = (最高价 + 最低价 + 收盘价) / 3

    特点：
    - 日内交易的基准价格
    - 机构交易员广泛使用
    - 价格在VWAP上方=强势，下方=弱势
    """

    def __init__(self):
        """初始化VWAP指标"""
        pass

    def calculate(self, highs: List[float], lows: List[float], closes: List[float],
                  volumes: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算VWAP指标（无状态，每次完整重算）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含VWAP值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes) or len(highs) != len(volumes):
            raise ValueError("数据长度必须一致")

        if reverse:
            highs = list(reversed(highs))
            lows = list(reversed(lows))
            closes = list(reversed(closes))
            volumes = list(reversed(volumes))

        if len(closes) == 0:
            return {
                'vwap': None,
                'vwap_series': []
            }

        vwap_values = []
        cumulative_pv = 0
        cumulative_volume = 0

        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_pv += typical_price * volumes[i]
            cumulative_volume += volumes[i]

            if cumulative_volume > 0:
                vwap = cumulative_pv / cumulative_volume
            else:
                vwap = typical_price

            vwap_values.append(vwap)

        if reverse:
            vwap_values = list(reversed(vwap_values))

        return {
            'vwap': vwap_values[-1] if vwap_values else None,
            'vwap_series': vwap_values
        }

    def calculate_from_typical_prices(self, prices: List[float], volumes: List[float],
                                      reverse: bool = False) -> Dict[str, Any]:
        """
        使用典型价格直接计算VWAP（无状态）

        Args:
            prices: 典型价格序列
            volumes: 成交量序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含VWAP值的字典
        """
        if len(prices) != len(volumes):
            raise ValueError("价格和成交量数据长度必须一致")

        if reverse:
            prices = list(reversed(prices))
            volumes = list(reversed(volumes))

        if len(prices) == 0:
            return {
                'vwap': None,
                'vwap_series': []
            }

        vwap_values = []
        cumulative_pv = 0
        cumulative_volume = 0

        for price, volume in zip(prices, volumes):
            cumulative_pv += price * volume
            cumulative_volume += volume

            if cumulative_volume > 0:
                vwap = cumulative_pv / cumulative_volume
            else:
                vwap = price

            vwap_values.append(vwap)

        if reverse:
            vwap_values = list(reversed(vwap_values))

        return {
            'vwap': vwap_values[-1] if vwap_values else None,
            'vwap_series': vwap_values
        }

    def calculate_latest(self, highs: List[float], lows: List[float], closes: List[float],
                         volumes: List[float]) -> Optional[float]:
        """
        快捷方法：只返回最新的VWAP值

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列

        Returns:
            最新的VWAP值
        """
        result = self.calculate(highs, lows, closes, volumes)
        return result['vwap']

    @staticmethod
    def calculate_typical_price(high: float, low: float, close: float) -> float:
        """
        计算典型价格 (Typical Price)

        Args:
            high: 最高价
            low: 最低价
            close: 收盘价

        Returns:
            典型价格 = (H + L + C) / 3
        """
        return (high + low + close) / 3


class VWAPAnalyzer:
    """
    VWAP分析器（无状态版本），提供交易信号
    """

    def __init__(self):
        """初始化VWAP分析器"""
        self.indicator = VWAPIndicator()

    def analyze(self, highs: List[float], lows: List[float], closes: List[float],
                volumes: List[float]) -> Dict[str, Any]:
        """
        综合分析VWAP（无状态，基于完整历史数据）

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列

        Returns:
            包含VWAP值、信号、价格位置等的综合分析字典
        """
        result = self.indicator.calculate(highs, lows, closes, volumes)
        vwap = result['vwap']
        vwap_series = result['vwap_series']

        if vwap is None or len(closes) < 2:
            return {
                **result,
                'signal': 'HOLD',
                'price_position': 'UNKNOWN',
                'strength': 'NEUTRAL'
            }

        current_price = closes[-1]
        prev_price = closes[-2]

        # 检测信号
        signal = 'HOLD'
        if len(vwap_series) >= 2:
            prev_vwap = vwap_series[-2]
            # 价格向上突破VWAP
            if prev_price <= prev_vwap and current_price > vwap:
                signal = 'BUY'
            # 价格向下跌破VWAP
            elif prev_price >= prev_vwap and current_price < vwap:
                signal = 'SELL'

        # 价格位置
        if vwap != 0:
            deviation = (current_price - vwap) / vwap * 100
        else:
            deviation = 0

        if deviation > 2.0:
            price_position = 'STRONG_ABOVE'
        elif deviation > 0.1:
            price_position = 'ABOVE'
        elif deviation < -2.0:
            price_position = 'STRONG_BELOW'
        elif deviation < -0.1:
            price_position = 'BELOW'
        else:
            price_position = 'AT_VWAP'

        # 市场强弱
        if current_price > vwap:
            strength = 'BULLISH'
        elif current_price < vwap:
            strength = 'BEARISH'
        else:
            strength = 'NEUTRAL'

        return {
            **result,
            'signal': signal,
            'price_position': price_position,
            'strength': strength,
            'deviation_percent': deviation
        }

    def get_signal(self, highs: List[float], lows: List[float], closes: List[float],
                   volumes: List[float]) -> str:
        """
        获取交易信号

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列

        Returns:
            'BUY', 'SELL', 或 'HOLD'
        """
        return self.analyze(highs, lows, closes, volumes)['signal']

    def get_price_position(self, highs: List[float], lows: List[float], closes: List[float],
                           volumes: List[float]) -> str:
        """
        获取价格相对于VWAP的位置

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列

        Returns:
            'STRONG_ABOVE', 'ABOVE', 'AT_VWAP', 'BELOW', 'STRONG_BELOW'
        """
        return self.analyze(highs, lows, closes, volumes)['price_position']

    def get_strength(self, highs: List[float], lows: List[float], closes: List[float],
                     volumes: List[float]) -> str:
        """
        获取市场强弱

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列

        Returns:
            'BULLISH', 'BEARISH', 'NEUTRAL'
        """
        return self.analyze(highs, lows, closes, volumes)['strength']
