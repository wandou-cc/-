# -*- coding: utf-8 -*-
"""
RSI (Relative Strength Index) 指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


class RSIIndicator:
    """
    RSI指标计算类（无状态版本）

    RSI计算公式：
    RSI = 100 - (100 / (1 + RS))
    其中 RS = 平均涨幅 / 平均跌幅

    使用EMA（指数移动平均）方法计算平均涨跌幅：
    - 初始值：使用前N期的SMA
    - 后续值：EMA = α × 当前值 + (1-α) × 前一期EMA
    - α = 1 / period
    """

    def __init__(self, period: int = 14):
        """
        初始化RSI指标参数

        Args:
            period: RSI计算周期，默认14
        """
        self.period = period
        self.alpha = 1.0 / period

    def calculate(self, closes: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算RSI指标（无状态，每次完整重算）

        Args:
            closes: 收盘价序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含RSI值的字典，返回最新一个值和完整序列
        """
        if reverse:
            closes = list(reversed(closes))

        if len(closes) < self.period + 1:
            return {
                'rsi': None,
                'rsi_series': [],
                'avg_gain': None,
                'avg_loss': None
            }

        # 计算价格变化（涨幅和跌幅）
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        # 使用EMA方法计算RSI序列
        rsi_values = []
        avg_gains = []
        avg_losses = []

        # 初始平均涨幅和跌幅（使用SMA）
        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period

        avg_gains.append(avg_gain)
        avg_losses.append(avg_loss)

        # 计算第一个RSI
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)

        # 使用EMA计算后续的平均涨幅和跌幅
        for i in range(self.period, len(gains)):
            avg_gain = self.alpha * gains[i] + (1 - self.alpha) * avg_gain
            avg_loss = self.alpha * losses[i] + (1 - self.alpha) * avg_loss

            avg_gains.append(avg_gain)
            avg_losses.append(avg_loss)

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)

        if reverse:
            rsi_values = list(reversed(rsi_values))
            avg_gains = list(reversed(avg_gains))
            avg_losses = list(reversed(avg_losses))

        return {
            'rsi': rsi_values[-1] if rsi_values else None,
            'rsi_series': rsi_values,
            'avg_gain': avg_gains[-1] if avg_gains else None,
            'avg_loss': avg_losses[-1] if avg_losses else None
        }

    def calculate_latest(self, closes: List[float]) -> Optional[float]:
        """
        快捷方法：只返回最新的RSI值

        Args:
            closes: 收盘价序列（时间正序，旧到新）

        Returns:
            最新的RSI值，数据不足返回None
        """
        result = self.calculate(closes)
        return result['rsi']

    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数设置"""
        return {
            'period': self.period
        }

    def set_parameters(self, period: int = None):
        """
        更新参数设置

        Args:
            period: RSI计算周期
        """
        if period is not None:
            self.period = period
            self.alpha = 1.0 / period


class RSIAnalyzer:
    """
    RSI分析器（无状态版本），提供买卖信号和趋势分析
    """

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        """
        初始化RSI分析器

        Args:
            period: RSI周期
            overbought: 超买阈值，默认70
            oversold: 超卖阈值，默认30
        """
        self.indicator = RSIIndicator(period)
        self.overbought = overbought
        self.oversold = oversold

    def analyze(self, closes: List[float]) -> Dict[str, Any]:
        """
        综合分析RSI（无状态，基于完整历史数据）

        Args:
            closes: 收盘价序列（时间正序）

        Returns:
            包含RSI值、信号、动量水平等的综合分析字典
        """
        result = self.indicator.calculate(closes)
        rsi = result['rsi']
        rsi_series = result['rsi_series']

        if rsi is None:
            return {
                'rsi': None,
                'signal': 'HOLD',
                'momentum_level': 'UNKNOWN',
                'is_overbought': False,
                'is_oversold': False
            }

        # 判断信号（需要至少2个RSI值来检测穿越）
        signal = 'HOLD'
        if len(rsi_series) >= 2:
            prev_rsi = rsi_series[-2]
            curr_rsi = rsi_series[-1]

            # RSI从超卖区域反弹
            if prev_rsi <= self.oversold and curr_rsi > self.oversold:
                signal = 'BUY'
            # RSI从超买区域回落
            elif prev_rsi >= self.overbought and curr_rsi < self.overbought:
                signal = 'SELL'

        # 判断动量水平
        if rsi > self.overbought:
            momentum_level = 'OVERBOUGHT'
        elif rsi > 50:
            momentum_level = 'BULLISH'
        elif rsi < self.oversold:
            momentum_level = 'OVERSOLD'
        elif rsi < 50:
            momentum_level = 'BEARISH'
        else:
            momentum_level = 'NEUTRAL'

        return {
            'rsi': rsi,
            'rsi_series': rsi_series,
            'avg_gain': result['avg_gain'],
            'avg_loss': result['avg_loss'],
            'signal': signal,
            'momentum_level': momentum_level,
            'is_overbought': rsi > self.overbought,
            'is_oversold': rsi < self.oversold,
            'overbought_threshold': self.overbought,
            'oversold_threshold': self.oversold
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

    def get_momentum_level(self, closes: List[float]) -> str:
        """
        获取动量水平

        Args:
            closes: 收盘价序列

        Returns:
            'OVERBOUGHT', 'BULLISH', 'NEUTRAL', 'BEARISH', 'OVERSOLD'
        """
        return self.analyze(closes)['momentum_level']

    def detect_divergence(self, closes: List[float], lookback: int = 5) -> str:
        """
        检测RSI背离信号（无状态）

        Args:
            closes: 收盘价序列
            lookback: 回看周期

        Returns:
            'BULLISH_DIVERGENCE': 看涨背离
            'BEARISH_DIVERGENCE': 看跌背离
            'NO_DIVERGENCE': 无背离
        """
        result = self.indicator.calculate(closes)
        rsi_series = result['rsi_series']

        if len(rsi_series) < lookback or len(closes) < lookback:
            return 'NO_DIVERGENCE'

        # 获取最近的价格和RSI值
        recent_prices = closes[-lookback:]
        recent_rsi = rsi_series[-lookback:]

        # 检测背离
        price_trend = recent_prices[-1] - recent_prices[0]
        rsi_trend = recent_rsi[-1] - recent_rsi[0]

        # 看涨背离：价格下跌但RSI上升
        if price_trend < 0 and rsi_trend > 0:
            return 'BULLISH_DIVERGENCE'

        # 看跌背离：价格上涨但RSI下降
        elif price_trend > 0 and rsi_trend < 0:
            return 'BEARISH_DIVERGENCE'

        return 'NO_DIVERGENCE'

    def set_thresholds(self, overbought: float = None, oversold: float = None):
        """
        设置超买超卖阈值

        Args:
            overbought: 超买阈值
            oversold: 超卖阈值
        """
        if overbought is not None:
            self.overbought = overbought
        if oversold is not None:
            self.oversold = oversold
