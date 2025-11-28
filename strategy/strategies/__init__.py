# -*- coding: utf-8 -*-
"""
子策略模块

包含三种交易策略：
- RangingStrategy: 震荡策略（ADX < 20时使用）
- TrendingStrategy: 趋势策略（ADX 20-40时使用）
- BreakoutStrategy: 突破策略（ADX > 40或突破信号时使用）
"""

from .base_strategy import BaseStrategy, StrategySignal, SignalDirection
from .ranging_strategy import RangingStrategy
from .trending_strategy import TrendingStrategy
from .breakout_strategy import BreakoutStrategy

__all__ = [
    'BaseStrategy',
    'StrategySignal',
    'SignalDirection',
    'RangingStrategy',
    'TrendingStrategy',
    'BreakoutStrategy',
]
