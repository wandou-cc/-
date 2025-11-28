"""
技术指标库
基于TradingView标准的技术指标实现
"""

import warnings

from .atr_indicator import ATRIndicator, ATRAnalyzer
from .adx_indicator import ADXIndicator, ADXAnalyzer, TrendDirection, TrendStrength
from .bollinger_bands import BollingerBandsIndicator, BollingerBandsAnalyzer
from .cci_indicator import CCIIndicator, CCIAnalyzer
from .ema_cross import EMAIndicator, EMACrossSystem, EMACrossAnalyzer, EMAFourLineSystem, EMAFourLineAnalyzer
from .kdj_indicator import KDJIndicator, KDJAnalyzer
from .macd_indicator import MACDIndicator, MACDAnalyzer
from .rsi_indicator import RSIIndicator, RSIAnalyzer
from .volume_indicator import VolumeIndicator, VolumeAnalyzer, VolumeCondition, VolumeTrend, PriceVolumeDivergence

from .streaming_buffer import StreamingCandle, StreamingKlineBuffer

__all__ = [
    'ATRIndicator',
    'ATRAnalyzer',
    'ADXIndicator',
    'ADXAnalyzer',
    'TrendDirection',
    'TrendStrength',
    'BollingerBandsIndicator',
    'BollingerBandsAnalyzer',
    'CCIIndicator',
    'CCIAnalyzer',
    'EMAIndicator',
    'EMACrossSystem',
    'EMACrossAnalyzer',
    'EMAFourLineSystem',
    'EMAFourLineAnalyzer',
    'KDJIndicator',
    'KDJAnalyzer',
    'MACDIndicator',
    'MACDAnalyzer',
    'RSIIndicator',
    'RSIAnalyzer',
    'VolumeIndicator',
    'VolumeAnalyzer',
    'VolumeCondition',
    'VolumeTrend',
    'PriceVolumeDivergence',
    'StreamingCandle',
    'StreamingKlineBuffer',
]

__version__ = '2.0.0'
