# -*- coding: utf-8 -*-
"""
布林带(Bollinger Bands)指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

import numpy as np
from typing import List, Dict, Any, Optional


class BollingerBandsIndicator:
    """
    布林带指标计算类（无状态版本，TradingView标准）

    布林带包含三条线：
    1. 中轨线 = SMA(20) - 简单移动平均线
    2. 上轨线 = 中轨线 + (标准差 × 2)
    3. 下轨线 = 中轨线 - (标准差 × 2)

    附加指标：
    - %B：价格在布林带中的位置，范围0-1（可能超出）
    - BandWidth：带宽，衡量波动率大小
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        """
        初始化布林带指标参数

        Args:
            period: SMA周期，默认20
            std_dev: 标准差倍数，默认2.0
        """
        if period <= 0:
            raise ValueError("period必须大于0")
        if std_dev <= 0:
            raise ValueError("std_dev必须大于0")

        self.period = period
        self.std_dev = std_dev

    def calculate(self, prices: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算布林带指标（无状态，每次完整重算）

        Args:
            prices: 价格序列（通常是收盘价）
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含上轨、中轨、下轨、带宽、%B、标准差的字典
        """
        if reverse:
            prices = list(reversed(prices))

        if len(prices) < self.period:
            return {
                'upper_band': None,
                'middle_band': None,
                'lower_band': None,
                'bandwidth': None,
                'percent_b': None,
                'std_dev': None,
                'upper_band_series': [],
                'middle_band_series': [],
                'lower_band_series': [],
                'bandwidth_series': [],
                'percent_b_series': [],
                'std_dev_series': []
            }

        upper_band = []
        middle_band = []
        lower_band = []
        percent_b = []
        bandwidth = []
        std_dev_list = []

        # 使用滑动窗口计算
        window_sum = sum(prices[:self.period])
        window_sum_sq = sum(price ** 2 for price in prices[:self.period])

        for i in range(self.period - 1, len(prices)):
            if i > self.period - 1:
                entering = prices[i]
                leaving = prices[i - self.period]
                window_sum += entering - leaving
                window_sum_sq += entering ** 2 - leaving ** 2

            current_sma = window_sum / self.period
            variance = max(window_sum_sq / self.period - current_sma ** 2, 0.0)
            std = np.sqrt(variance)

            upper = current_sma + self.std_dev * std
            lower = current_sma - self.std_dev * std

            current_price = prices[i]
            if upper != lower:
                pb = (current_price - lower) / (upper - lower)
            else:
                pb = 0.5

            if current_sma != 0:
                bw = (upper - lower) / current_sma
            else:
                bw = 0

            upper_band.append(upper)
            middle_band.append(current_sma)
            lower_band.append(lower)
            percent_b.append(pb)
            bandwidth.append(bw)
            std_dev_list.append(std)

        if reverse:
            upper_band = list(reversed(upper_band))
            middle_band = list(reversed(middle_band))
            lower_band = list(reversed(lower_band))
            percent_b = list(reversed(percent_b))
            bandwidth = list(reversed(bandwidth))
            std_dev_list = list(reversed(std_dev_list))

        return {
            'upper_band': upper_band[-1] if upper_band else None,
            'middle_band': middle_band[-1] if middle_band else None,
            'lower_band': lower_band[-1] if lower_band else None,
            'bandwidth': bandwidth[-1] if bandwidth else None,
            'percent_b': percent_b[-1] if percent_b else None,
            'std_dev': std_dev_list[-1] if std_dev_list else None,
            'upper_band_series': upper_band,
            'middle_band_series': middle_band,
            'lower_band_series': lower_band,
            'bandwidth_series': bandwidth,
            'percent_b_series': percent_b,
            'std_dev_series': std_dev_list
        }

    def calculate_latest(self, prices: List[float]) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的布林带值

        Args:
            prices: 价格序列

        Returns:
            包含最新布林带值的字典
        """
        result = self.calculate(prices)
        return {
            'upper_band': result['upper_band'],
            'middle_band': result['middle_band'],
            'lower_band': result['lower_band'],
            'bandwidth': result['bandwidth'],
            'percent_b': result['percent_b'],
            'std_dev': result['std_dev']
        }

    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'std_dev': self.std_dev
        }

    def set_parameters(self, period: int = None, std_dev: float = None):
        """
        更新参数设置

        Args:
            period: 移动平均线周期
            std_dev: 标准差倍数
        """
        if period is not None:
            self.period = period
        if std_dev is not None:
            self.std_dev = std_dev


class BollingerBandsAnalyzer:
    """
    布林带分析器（无状态版本），提供买卖信号和趋势分析
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0, squeeze_threshold: float = 0.05):
        """
        初始化分析器

        Args:
            period: SMA周期
            std_dev: 标准差倍数
            squeeze_threshold: 挤压阈值，当带宽小于此值时认为是挤压状态
        """
        self.indicator = BollingerBandsIndicator(period, std_dev)
        self.squeeze_threshold = squeeze_threshold

    def analyze(self, prices: List[float]) -> Dict[str, Any]:
        """
        综合分析布林带（无状态，基于完整历史数据）

        Args:
            prices: 价格序列

        Returns:
            包含布林带值、信号、波动率水平等的综合分析字典
        """
        result = self.indicator.calculate(prices)

        if result['upper_band'] is None:
            return {
                **result,
                'signal': 'HOLD',
                'volatility_level': 'UNKNOWN',
                'price_position': 'UNKNOWN',
                'is_squeeze': False,
                'squeeze_breakout': 'NORMAL'
            }

        current_price = prices[-1]

        # 检测信号
        signal = 'HOLD'
        if current_price <= result['lower_band'] * 1.01:
            signal = 'BUY'
        elif current_price >= result['upper_band'] * 0.99:
            signal = 'SELL'

        # 波动率水平
        bandwidth = result['bandwidth']
        if bandwidth > 0.1:
            volatility_level = 'HIGH'
        elif bandwidth > 0.05:
            volatility_level = 'MEDIUM'
        else:
            volatility_level = 'LOW'

        # 价格位置
        percent_b = result['percent_b']
        if percent_b > 1.0:
            price_position = 'ABOVE_UPPER'
        elif percent_b > 0.8:
            price_position = 'UPPER_ZONE'
        elif percent_b < 0.0:
            price_position = 'BELOW_LOWER'
        elif percent_b < 0.2:
            price_position = 'LOWER_ZONE'
        else:
            price_position = 'MIDDLE_ZONE'

        # 挤压检测
        is_squeeze = bandwidth < self.squeeze_threshold

        # 挤压突破检测
        squeeze_breakout = 'NORMAL'
        bandwidth_series = result['bandwidth_series']
        if len(bandwidth_series) >= 3:
            was_squeeze = bandwidth_series[-2] < self.squeeze_threshold
            if is_squeeze:
                squeeze_breakout = 'SQUEEZE'
            elif was_squeeze and not is_squeeze:
                if percent_b > 0.8:
                    squeeze_breakout = 'BREAKOUT_UP'
                elif percent_b < 0.2:
                    squeeze_breakout = 'BREAKOUT_DOWN'

        return {
            **result,
            'signal': signal,
            'volatility_level': volatility_level,
            'price_position': price_position,
            'is_squeeze': is_squeeze,
            'squeeze_breakout': squeeze_breakout
        }

    def get_signal(self, prices: List[float]) -> str:
        """
        获取交易信号

        Args:
            prices: 价格序列

        Returns:
            'BUY', 'SELL', 或 'HOLD'
        """
        return self.analyze(prices)['signal']

    def get_volatility_level(self, prices: List[float]) -> str:
        """
        获取波动率水平

        Args:
            prices: 价格序列

        Returns:
            'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
        """
        return self.analyze(prices)['volatility_level']

    def is_squeeze(self, prices: List[float]) -> bool:
        """
        检测是否处于布林带挤压状态

        Args:
            prices: 价格序列

        Returns:
            True: 当前处于挤压状态
        """
        return self.analyze(prices)['is_squeeze']

    def detect_squeeze_breakout(self, prices: List[float]) -> str:
        """
        检测布林带挤压突破

        Args:
            prices: 价格序列

        Returns:
            'BREAKOUT_UP', 'BREAKOUT_DOWN', 'SQUEEZE', 'NORMAL'
        """
        return self.analyze(prices)['squeeze_breakout']

    def get_price_position(self, prices: List[float]) -> str:
        """
        获取价格在布林带中的位置

        Args:
            prices: 价格序列

        Returns:
            'ABOVE_UPPER', 'UPPER_ZONE', 'MIDDLE_ZONE', 'LOWER_ZONE', 'BELOW_LOWER'
        """
        return self.analyze(prices)['price_position']
