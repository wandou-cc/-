# -*- coding: utf-8 -*-
"""
状态机驱动的分层策略系统

核心模块：
- market_state: 市场状态识别
- signal_generator: 信号生成器
- multi_timeframe: 多周期确认
- volume_analyzer: 成交量分析（使用 indicators.volume_indicator）

子策略：
- strategies.ranging_strategy: 震荡策略
- strategies.trending_strategy: 趋势策略
- strategies.breakout_strategy: 突破策略
"""

from .market_state import MarketState, MarketStateDetector, MarketStateResult
from .signal_generator import SignalGenerator, TradingSignal, SignalGrade, Prediction
from .multi_timeframe import MultiTimeframeConfirmer, MultiTimeframeResult, ConfirmationResult
from .strategies import RangingStrategy, TrendingStrategy, BreakoutStrategy, StrategySignal, SignalDirection

__all__ = [
    'MarketState',
    'MarketStateDetector',
    'MarketStateResult',
    'SignalGenerator',
    'TradingSignal',
    'SignalGrade',
    'Prediction',
    'MultiTimeframeConfirmer',
    'MultiTimeframeResult',
    'ConfirmationResult',
    'RangingStrategy',
    'TrendingStrategy',
    'BreakoutStrategy',
    'StrategySignal',
    'SignalDirection',
]

__version__ = '1.0.0'
