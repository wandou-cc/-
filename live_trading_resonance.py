"""
实时交易系统（共振策略版本 - 增强版） - Binance WebSocket
基于7指标共振策略，预测10分钟、30分钟、1小时价格走势

策略核心：
1. 趋势层：EMA四线系统判断主趋势
2. 动量层：RSI + KDJ + CCI 确认动量
3. 时机层：MACD + BOLL + ATR 确认进场时机和波动率
4. 可选：VWAP 日内交易基准

共振要求：6-7个指标中至少5个同向，总评分≥70
"""

import asyncio
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

import websockets

# 使用无状态指标（来自 indicators 目录）
from indicators import (
    MACDIndicator,
    RSIIndicator,
    BollingerBandsIndicator,
    KDJIndicator,
    EMAFourLineSystem,
    CCIIndicator,
    ATRIndicator,
    VWAPIndicator
)
from resonance_strategy import ResonanceStrategy, SignalType, ResonanceScore
from config import (
    BINANCE_WS_URL,
    USE_PROXY,
    PROXY_URL,
    REQUEST_TIMEOUT,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_CLOSE_TIMEOUT,
    MAX_RETRIES,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    HEARTBEAT_INTERVAL,
    MACD_PARAMS,
    RSI_PARAMS,
    BB_PARAMS,
    KDJ_PARAMS,
    EMA_PARAMS,
    CCI_PARAMS,
    ATR_PARAMS,
    RESONANCE_PARAMS,
    INDICATOR_SWITCHES,
    get_min_resonance,
    get_enabled_indicator_count,
)
from dashboard import ConsoleDashboard


@dataclass
class KlineData:
    """K线数据"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False


@dataclass
class ResonanceTradeSignal:
    """共振交易信号"""
    signal_id: str
    timestamp: int
    datetime_str: str
    signal_type: SignalType
    entry_price: float

    # 共振评分
    total_score: float
    confidence: float
    resonance_count: int  # 共振指标数量
    trend_aligned: bool

    reasons: List[str] = field(default_factory=list)
    score_details: Dict = field(default_factory=dict)

    # 指标数据
    indicators: Dict = field(default_factory=dict)

    # 预测验证
    predicted_10min: str = None  # HIGHER/LOWER
    predicted_30min: str = None
    predicted_1hour: str = None

    # 实际结果
    actual_10min_price: Optional[float] = None
    actual_30min_price: Optional[float] = None
    actual_1hour_price: Optional[float] = None

    actual_10min_result: Optional[str] = None
    actual_30min_result: Optional[str] = None
    actual_1hour_result: Optional[str] = None

    # 验证时间点
    check_10min_time: Optional[int] = None
    check_30min_time: Optional[int] = None
    check_1hour_time: Optional[int] = None

    # 状态
    is_10min_checked: bool = False
    is_30min_checked: bool = False
    is_1hour_checked: bool = False


class ResonanceMultiIndicatorStrategy:
    """共振多指标交易策略（实时版本 - 无状态版）

    使用无状态指标，每次基于完整K线历史重新计算，避免回滚机制导致的数值错误。
    """

    def __init__(self,
                 # 指标参数（从config.py读取默认值）
                 macd_fast: int = None,
                 macd_slow: int = None,
                 macd_signal: int = None,
                 rsi_period: int = None,
                 bb_period: int = None,
                 bb_std: float = None,
                 kdj_period: int = None,
                 kdj_signal: int = None,
                 cci_period: int = None,
                 atr_period: int = None,
                 ema_ultra_fast: int = None,
                 ema_fast: int = None,
                 ema_medium: int = None,
                 ema_slow: int = None,
                 # 共振策略参数
                 min_resonance: int = None,
                 min_score: float = None,
                 # 指标开关（从config.py的INDICATOR_SWITCHES读取）
                 use_macd: bool = None,
                 use_rsi: bool = None,
                 use_kdj: bool = None,
                 use_boll: bool = None,
                 use_ema: bool = None,
                 use_cci: bool = None,
                 use_atr: bool = None,
                 use_vwap: bool = None):
        """初始化共振策略（无状态版）"""

        # 从config.py读取默认参数（如果未指定）
        self._macd_fast = macd_fast if macd_fast is not None else MACD_PARAMS['fast_period']
        self._macd_slow = macd_slow if macd_slow is not None else MACD_PARAMS['slow_period']
        self._macd_signal = macd_signal if macd_signal is not None else MACD_PARAMS['signal_period']

        self._rsi_period = rsi_period if rsi_period is not None else RSI_PARAMS['period']

        self._bb_period = bb_period if bb_period is not None else BB_PARAMS['period']
        self._bb_std = bb_std if bb_std is not None else BB_PARAMS['std_dev']

        self._kdj_period = kdj_period if kdj_period is not None else KDJ_PARAMS['period']
        self._kdj_signal = kdj_signal if kdj_signal is not None else KDJ_PARAMS['signal']

        self._cci_period = cci_period if cci_period is not None else CCI_PARAMS['period']
        self._atr_period = atr_period if atr_period is not None else ATR_PARAMS['period']

        self._ema_ultra_fast = ema_ultra_fast if ema_ultra_fast is not None else EMA_PARAMS['ultra_fast']
        self._ema_fast = ema_fast if ema_fast is not None else EMA_PARAMS['fast']
        self._ema_medium = ema_medium if ema_medium is not None else EMA_PARAMS['medium']
        self._ema_slow = ema_slow if ema_slow is not None else EMA_PARAMS['slow']

        # 从config.py读取指标开关（如果未指定）
        self._use_macd = use_macd if use_macd is not None else INDICATOR_SWITCHES['use_macd']
        self._use_rsi = use_rsi if use_rsi is not None else INDICATOR_SWITCHES['use_rsi']
        self._use_kdj = use_kdj if use_kdj is not None else INDICATOR_SWITCHES['use_kdj']
        self._use_boll = use_boll if use_boll is not None else INDICATOR_SWITCHES['use_boll']
        self._use_ema = use_ema if use_ema is not None else INDICATOR_SWITCHES['use_ema']
        self._use_cci = use_cci if use_cci is not None else INDICATOR_SWITCHES['use_cci']
        self._use_atr = use_atr if use_atr is not None else INDICATOR_SWITCHES['use_atr']
        self._use_vwap = use_vwap if use_vwap is not None else INDICATOR_SWITCHES['use_vwap']

        # 从config.py读取共振策略参数（如果未指定）
        if min_resonance is None:
            if RESONANCE_PARAMS['min_resonance'] is None:
                min_resonance = get_min_resonance()
            else:
                min_resonance = RESONANCE_PARAMS['min_resonance']

        min_score = min_score if min_score is not None else RESONANCE_PARAMS['min_score']

        # 初始化无状态指标（每次基于完整历史数组计算）
        self.macd = MACDIndicator(self._macd_fast, self._macd_slow, self._macd_signal) if self._use_macd else None
        self.rsi = RSIIndicator(self._rsi_period) if self._use_rsi else None
        self.bb = BollingerBandsIndicator(self._bb_period, self._bb_std) if self._use_boll else None
        self.kdj = KDJIndicator(self._kdj_period, self._kdj_signal) if self._use_kdj else None
        self.ema = EMAFourLineSystem(self._ema_ultra_fast, self._ema_fast, self._ema_medium, self._ema_slow) if self._use_ema else None
        self.cci = CCIIndicator(self._cci_period) if self._use_cci else None
        self.atr = ATRIndicator(self._atr_period) if self._use_atr else None
        self.vwap = VWAPIndicator() if self._use_vwap else None

        # 共振策略
        self.resonance_strategy = ResonanceStrategy(
            min_resonance=min_resonance,
            min_score=min_score,
            use_trend_filter=True,
            use_momentum_filter=True,
            use_volatility_filter=True,
            use_macd=self._use_macd,
            use_rsi=self._use_rsi,
            use_kdj=self._use_kdj,
            use_boll=self._use_boll,
            use_ema=self._use_ema,
            use_cci=self._use_cci,
            use_atr=self._use_atr,
            use_vwap=self._use_vwap
        )

        # K线历史数据（由外部传入或内部维护）
        self._kline_history: List[KlineData] = []

        # 上一根已关闭K线的指标值（用于趋势判断）
        self._last_closed_values: Dict[str, Any] = {}

        # 最新的指标信号（用于dashboard显示）
        self.latest_indicator_signals: Dict[str, str] = {}
        self.latest_resonance_score: Optional[ResonanceScore] = None

        # 缓存当前计算结果（用于 get_indicator_snapshot）
        self._cached_values: Dict[str, Any] = {}

    def update(self, kline: KlineData, kline_history: List[KlineData] = None) -> Optional[ResonanceTradeSignal]:
        """
        更新指标并判断是否产生交易信号（无状态版本）

        基于完整K线历史数组计算指标值，不使用回滚机制，避免 ATR 等指标的数值错误。

        Args:
            kline: 当前K线数据
            kline_history: 已关闭的K线历史（可选，若不传则使用内部维护的历史）
        """
        # 使用传入的历史或内部维护的历史
        if kline_history is not None:
            history = list(kline_history)
        else:
            history = self._kline_history.copy()

        # 构建包含当前K线的完整数组
        # 注意：history 只包含已关闭的K线，当前K线可能是未关闭的
        all_klines = history + [kline]

        # 提取价格数组
        closes = [k.close for k in all_klines]
        highs = [k.high for k in all_klines]
        lows = [k.low for k in all_klines]

        # 使用无状态指标计算（每次完整重算）
        # MACD - 新API返回字典
        macd_values = {'macd_line': None, 'signal_line': None, 'histogram': None}
        if self.macd:
            macd_result = self.macd.calculate(closes)
            macd_values = {
                'macd_line': macd_result['macd_line'],
                'signal_line': macd_result['signal_line'],
                'histogram': macd_result['histogram']
            }

        # RSI - 新API返回字典
        rsi_values = {'rsi': None}
        if self.rsi:
            rsi_result = self.rsi.calculate(closes)
            rsi_values = {'rsi': rsi_result['rsi']}

        # Bollinger Bands - 新API返回字典
        bb_values = {'upper_band': None, 'middle_band': None, 'lower_band': None, 'percent_b': None}
        if self.bb:
            bb_result = self.bb.calculate(closes)
            bb_values = {
                'upper_band': bb_result['upper_band'],
                'middle_band': bb_result['middle_band'],
                'lower_band': bb_result['lower_band'],
                'percent_b': bb_result['percent_b']
            }

        # KDJ - 新API返回字典
        kdj_values = {'k': None, 'd': None, 'j': None}
        if self.kdj:
            kdj_result = self.kdj.calculate(highs, lows, closes)
            kdj_values = {'k': kdj_result['k'], 'd': kdj_result['d'], 'j': kdj_result['j']}

        # EMA - 新API使用calculate方法返回字典
        ema_values = {'ema_ultra_fast': None, 'ema_fast': None, 'ema_medium': None, 'ema_slow': None}
        if self.ema:
            ema_result = self.ema.calculate(closes)
            ema_values = {
                'ema_ultra_fast': ema_result['ema_ultra_fast'],
                'ema_fast': ema_result['ema_fast'],
                'ema_medium': ema_result['ema_medium'],
                'ema_slow': ema_result['ema_slow']
            }

        # CCI - 新API返回字典
        cci_values = {'cci': None}
        if self.cci:
            cci_result = self.cci.calculate(highs, lows, closes)
            cci_values = {'cci': cci_result['cci']}

        # ATR（无状态，基于完整历史计算）- 新API返回字典
        atr_values = {'atr': None}
        if self.atr:
            atr_result = self.atr.calculate(highs, lows, closes)
            atr_values = {'atr': atr_result['atr']}

        # VWAP（无状态，基于完整历史计算）- 新API返回字典
        vwap_value = None
        if self.vwap:
            volumes = [k.volume for k in all_klines]
            vwap_result = self.vwap.calculate(highs, lows, closes, volumes)
            vwap_value = vwap_result['vwap']

        # 缓存计算结果（用于 get_indicator_snapshot）
        self._cached_values = {
            'macd': macd_values,
            'rsi': rsi_values,
            'bb': bb_values,
            'kdj': kdj_values,
            'ema': ema_values,
            'cci': cci_values,
            'atr': atr_values,
            'vwap': vwap_value,
            'current_price': kline.close
        }

        # 检查至少有一个启用的指标有足够的数据
        has_sufficient_data = False
        if self.macd and macd_values['macd_line'] is not None:
            has_sufficient_data = True
        if self.rsi and rsi_values['rsi'] is not None:
            has_sufficient_data = True
        if self.kdj and kdj_values['k'] is not None:
            has_sufficient_data = True
        if self.bb and bb_values['middle_band'] is not None:
            has_sufficient_data = True
        if self.ema and ema_values['ema_slow'] is not None:
            has_sufficient_data = True
        if self.cci and cci_values['cci'] is not None:
            has_sufficient_data = True
        if self.atr and atr_values['atr'] is not None:
            has_sufficient_data = True

        if not has_sufficient_data:
            return None

        # 获取上一根K线的指标值（用于趋势判断）
        prev_rsi = self._last_closed_values.get('rsi')
        prev_k = self._last_closed_values.get('k')
        prev_d = self._last_closed_values.get('d')
        prev_macd = self._last_closed_values.get('macd')
        prev_macd_signal = self._last_closed_values.get('macd_signal')
        prev_cci = self._last_closed_values.get('cci')
        prev_atr = self._last_closed_values.get('atr')
        prev_price = self._last_closed_values.get('price')

        # 计算共振得分
        resonance_score = self.resonance_strategy.calculate_resonance(
            # RSI
            rsi=rsi_values['rsi'],
            previous_rsi=prev_rsi,
            # KDJ
            kdj_k=kdj_values['k'],
            kdj_d=kdj_values['d'],
            kdj_j=kdj_values['j'],
            previous_k=prev_k,
            previous_d=prev_d,
            # MACD
            macd=macd_values['macd_line'],
            macd_signal=macd_values['signal_line'],
            macd_histogram=macd_values['histogram'],
            previous_macd=prev_macd,
            previous_macd_signal=prev_macd_signal,
            # EMA
            ema_ultra_fast=ema_values['ema_ultra_fast'],
            ema_fast=ema_values['ema_fast'],
            ema_medium=ema_values['ema_medium'],
            ema_slow=ema_values['ema_slow'],
            # BOLL
            bb_upper=bb_values['upper_band'],
            bb_middle=bb_values['middle_band'],
            bb_lower=bb_values['lower_band'],
            bb_percent_b=bb_values['percent_b'],
            # CCI
            cci=cci_values['cci'],
            previous_cci=prev_cci,
            # ATR
            atr=atr_values['atr'],
            previous_atr=prev_atr,
            # VWAP
            vwap=vwap_value,
            # 价格和K线
            current_price=kline.close,
            previous_price=prev_price,
            high=kline.high,
            low=kline.low
        )

        # 保存最新的共振得分（用于dashboard）
        self.latest_resonance_score = resonance_score

        # 更新最新的指标信号（用于dashboard）
        self.latest_indicator_signals = {}
        for indicator, detail in resonance_score.details.items():
            if indicator in ['RSI', 'KDJ', 'MACD', 'BOLL', 'CCI', 'ATR', 'VWAP', 'trend']:
                signal = detail.get('signal', 'NEUTRAL')
                if indicator == 'trend':
                    direction = detail.get('direction', 'NEUTRAL')
                    self.latest_indicator_signals['EMA'] = 'BUY' if direction == 'BULLISH' else 'SELL' if direction == 'BEARISH' else 'WAIT'
                else:
                    self.latest_indicator_signals[indicator] = 'BUY' if signal == 'BUY' else 'SELL' if signal == 'SELL' else 'WAIT'

        # K线关闭时更新历史值和内部K线历史
        if kline.is_closed:
            self._last_closed_values = {
                'rsi': rsi_values.get('rsi'),
                'k': kdj_values.get('k'),
                'd': kdj_values.get('d'),
                'macd': macd_values.get('macd_line'),
                'macd_signal': macd_values.get('signal_line'),
                'cci': cci_values.get('cci'),
                'atr': atr_values.get('atr'),
                'price': kline.close
            }
            # 更新内部K线历史
            self._kline_history.append(kline)
            # 保持历史长度
            if len(self._kline_history) > 200:
                self._kline_history = self._kline_history[-200:]

        # 判断是否产生交易信号（只在K线关闭时）
        if not kline.is_closed:
            return None

        if resonance_score.signal_type == SignalType.HOLD:
            return None

        # 检查是否达到最低评分要求
        if resonance_score.strength < self.resonance_strategy.min_score:
            return None

        # 生成信号原因
        reasons = self.resonance_strategy.get_signal_reasons(resonance_score)

        # 创建交易信号
        if resonance_score.signal_type == SignalType.BUY:
            predicted = "HIGHER"
        else:
            predicted = "LOWER"

        signal_id = f"{resonance_score.signal_type.value}_{kline.timestamp}"
        current_time = kline.timestamp

        signal = ResonanceTradeSignal(
            signal_id=signal_id,
            timestamp=current_time,
            datetime_str=datetime.fromtimestamp(current_time/1000).strftime('%Y-%m-%d %H:%M:%S'),
            signal_type=resonance_score.signal_type,
            entry_price=kline.close,
            total_score=resonance_score.strength,
            confidence=resonance_score.confidence,
            resonance_count=resonance_score.resonance_count,
            trend_aligned=resonance_score.trend_aligned,
            reasons=reasons,
            score_details=resonance_score.details,
            predicted_10min=predicted,
            predicted_30min=predicted,
            predicted_1hour=predicted,
            check_10min_time=current_time + 10 * 60 * 1000,
            check_30min_time=current_time + 30 * 60 * 1000,
            check_1hour_time=current_time + 60 * 60 * 1000,
            indicators={
                'macd': {
                    'macd': macd_values['macd_line'],
                    'signal': macd_values['signal_line'],
                    'histogram': macd_values['histogram']
                },
                'rsi': {'rsi': rsi_values['rsi']},
                'bb': {
                    'upper': bb_values['upper_band'],
                    'middle': bb_values['middle_band'],
                    'lower': bb_values['lower_band'],
                    'percent_b': bb_values['percent_b']
                },
                'kdj': {
                    'k': kdj_values['k'],
                    'd': kdj_values['d'],
                    'j': kdj_values['j']
                },
                'ema': {
                    'ultra_fast': ema_values['ema_ultra_fast'],
                    'fast': ema_values['ema_fast'],
                    'medium': ema_values['ema_medium'],
                    'slow': ema_values['ema_slow']
                },
                'cci': {'cci': cci_values['cci']} if cci_values['cci'] is not None else None,
                'atr': {'atr': atr_values['atr']} if atr_values['atr'] is not None else None,
                'vwap': {'vwap': vwap_value} if vwap_value is not None else None
            }
        )

        return signal

    def get_indicator_snapshot(self) -> Dict[str, Any]:
        """返回最近一次计算的指标结构化数据（使用缓存值）"""
        snapshot: Dict[str, Any] = {}

        # 使用缓存的计算结果
        cached = self._cached_values

        if self._use_macd and cached.get('macd'):
            macd_values = cached['macd']
            if macd_values.get('macd_line') is not None:
                snapshot['macd'] = {
                    'macd': macd_values['macd_line'],
                    'signal': macd_values['signal_line'],
                    'histogram': macd_values['histogram'],
                    'signal_type': self.latest_indicator_signals.get('MACD', 'WAIT')
                }

        if self._use_rsi and cached.get('rsi'):
            rsi_values = cached['rsi']
            if rsi_values.get('rsi') is not None:
                snapshot['rsi'] = {
                    'rsi': rsi_values['rsi'],
                    'signal_type': self.latest_indicator_signals.get('RSI', 'WAIT')
                }

        if self._use_boll and cached.get('bb'):
            bb_values = cached['bb']
            if bb_values.get('upper_band') is not None:
                snapshot['bb'] = {
                    'upper': bb_values['upper_band'],
                    'middle': bb_values['middle_band'],
                    'lower': bb_values['lower_band'],
                    'percent_b': bb_values['percent_b'],
                    'signal_type': self.latest_indicator_signals.get('BOLL', 'WAIT')
                }

        if self._use_kdj and cached.get('kdj'):
            kdj_values = cached['kdj']
            if kdj_values.get('k') is not None:
                snapshot['kdj'] = {
                    'k': kdj_values['k'],
                    'd': kdj_values['d'],
                    'j': kdj_values['j'],
                    'signal_type': self.latest_indicator_signals.get('KDJ', 'WAIT')
                }

        if self._use_ema and cached.get('ema'):
            ema_values = cached['ema']
            if ema_values.get('ema_slow') is not None:
                # 推断趋势方向
                trend = 'NEUTRAL'
                if ema_values['ema_fast'] and ema_values['ema_slow']:
                    if ema_values['ema_fast'] > ema_values['ema_slow']:
                        trend = 'UP'
                    elif ema_values['ema_fast'] < ema_values['ema_slow']:
                        trend = 'DOWN'
                snapshot['ema'] = {
                    'ultra_fast': ema_values['ema_ultra_fast'],
                    'fast': ema_values['ema_fast'],
                    'medium': ema_values['ema_medium'],
                    'slow': ema_values['ema_slow'],
                    'signal_type': self.latest_indicator_signals.get('EMA', 'WAIT'),
                    'trend': trend
                }

        if self._use_cci and cached.get('cci'):
            cci_values = cached['cci']
            if cci_values.get('cci') is not None:
                snapshot['cci'] = {
                    'cci': cci_values['cci'],
                    'signal_type': self.latest_indicator_signals.get('CCI', 'WAIT')
                }

        if self._use_atr and cached.get('atr'):
            atr_values = cached['atr']
            if atr_values.get('atr') is not None:
                snapshot['atr'] = {
                    'atr': atr_values['atr'],
                    'signal_type': self.latest_indicator_signals.get('ATR', 'WAIT')
                }

        if self._use_vwap and cached.get('vwap') is not None:
            snapshot['vwap'] = {
                'vwap': cached['vwap'],
                'signal_type': self.latest_indicator_signals.get('VWAP', 'WAIT')
            }

        # 添加共振得分信息
        if self.latest_resonance_score:
            snapshot['resonance'] = {
                'total_score': self.latest_resonance_score.strength,
                'confidence': self.latest_resonance_score.confidence,
                'resonance_count': self.latest_resonance_score.resonance_count,
                'signal': self.latest_resonance_score.signal_type.value,
                'trend_aligned': self.latest_resonance_score.trend_aligned
            }

        return snapshot


class BinanceResonanceLiveTradingSystem:
    """Binance实时交易系统（共振策略版本）"""

    def __init__(self,
                 symbol: str = None,
                 interval: str = None,
                 contract_type: str = None,
                 strategy: ResonanceMultiIndicatorStrategy = None,
                 heartbeat_interval: float = None,
                 trade_log_file: str = "trade_signals_resonance.log"):
        """初始化实时交易系统"""
        # 从config.py读取默认参数（如果未指定）
        symbol = symbol if symbol is not None else DEFAULT_SYMBOL
        interval = interval if interval is not None else DEFAULT_INTERVAL
        contract_type = contract_type if contract_type is not None else DEFAULT_CONTRACT_TYPE
        heartbeat_interval = heartbeat_interval if heartbeat_interval is not None else HEARTBEAT_INTERVAL

        self.symbol = symbol.lower()
        self.interval = interval
        self.contract_type = contract_type.lower()
        self.strategy = strategy or ResonanceMultiIndicatorStrategy()
        self.heartbeat_interval = heartbeat_interval
        self.trade_log_file = trade_log_file

        # WebSocket配置
        ws_base = BINANCE_WS_URL.rstrip('/')
        stream = f"{self.symbol}_{self.contract_type}@continuousKline_{self.interval}"
        self.ws_url = f"{ws_base}/ws/{stream}"
        self.use_proxy = USE_PROXY
        self.proxy_url = PROXY_URL
        self.max_retries = MAX_RETRIES

        # K线历史数据
        self.kline_history: deque = deque(maxlen=200)
        self.current_kline: Optional[KlineData] = None
        self.latest_stream_kline: Optional[KlineData] = None

        # 活跃的交易信号
        self.active_signals: List[ResonanceTradeSignal] = []
        self.completed_signals: List[ResonanceTradeSignal] = []

        # 统计数据
        self.total_signals = 0
        self.correct_10min = 0
        self.correct_30min = 0
        self.correct_1hour = 0
        self.checked_10min = 0
        self.checked_30min = 0
        self.checked_1hour = 0

        # Dashboard初始化
        min_signals = strategy.resonance_strategy.min_resonance if strategy else 5
        self.dashboard = ConsoleDashboard(
            symbol=self.symbol.upper(),
            interval=self.interval,
            contract_type=self.contract_type.upper(),
            min_signals=min_signals,  # 根据策略配置
        )
        self.dashboard.update_meta(ws_url=self.ws_url, connection="初始化中")
        self._sync_stats_to_dashboard()
        self.use_dashboard = True

        # 初始化日志文件
        self._initialize_log_file()

        # 计算启用的指标总数
        enabled_indicators = []
        if strategy:
            if strategy.resonance_strategy.use_macd:
                enabled_indicators.append('MACD')
            if strategy.resonance_strategy.use_rsi:
                enabled_indicators.append('RSI')
            if strategy.resonance_strategy.use_kdj:
                enabled_indicators.append('KDJ')
            if strategy.resonance_strategy.use_boll:
                enabled_indicators.append('BOLL')
            if strategy.resonance_strategy.use_ema:
                enabled_indicators.append('EMA')
            if strategy.resonance_strategy.use_cci:
                enabled_indicators.append('CCI')
            if strategy.resonance_strategy.use_atr:
                enabled_indicators.append('ATR')
            if strategy.resonance_strategy.use_vwap:
                enabled_indicators.append('VWAP')

        total_indicators = len(enabled_indicators)
        min_score = strategy.resonance_strategy.min_score if strategy else 70.0

        print(f"[初始化] 交易对: {symbol}, 周期: {interval}, 合约: {self.contract_type.upper()}")
        print(f"[初始化] 策略: 增强共振策略 ({min_signals}/{total_indicators}指标共振，评分≥{min_score})")
        print(f"[初始化] 启用指标: {' + '.join(enabled_indicators)}")
        print(f"[初始化] WebSocket URL: {self.ws_url}")
        print(f"[初始化] 交易日志文件: {self.trade_log_file}")

    def _initialize_log_file(self):
        """初始化日志文件"""
        if not os.path.exists(self.trade_log_file):
            min_resonance = self.strategy.resonance_strategy.min_resonance
            min_score = self.strategy.resonance_strategy.min_score

            # 统计启用的指标
            enabled_indicators = []
            if self.strategy.resonance_strategy.use_macd:
                enabled_indicators.append('MACD')
            if self.strategy.resonance_strategy.use_rsi:
                enabled_indicators.append('RSI')
            if self.strategy.resonance_strategy.use_kdj:
                enabled_indicators.append('KDJ')
            if self.strategy.resonance_strategy.use_boll:
                enabled_indicators.append('BOLL')
            if self.strategy.resonance_strategy.use_ema:
                enabled_indicators.append('EMA')
            if self.strategy.resonance_strategy.use_cci:
                enabled_indicators.append('CCI')
            if self.strategy.resonance_strategy.use_atr:
                enabled_indicators.append('ATR')
            if self.strategy.resonance_strategy.use_vwap:
                enabled_indicators.append('VWAP')

            total_indicators = len(enabled_indicators)

            with open(self.trade_log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write(f"交易信号日志（增强共振策略） - {self.symbol.upper()} {self.interval}\n")
                f.write(f"策略配置: {min_resonance}/{total_indicators}指标共振，总评分≥{min_score}，趋势+动量+波动率过滤\n")
                f.write(f"启用指标: {' + '.join(enabled_indicators)}\n")
                f.write(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 100 + "\n\n")

    def _write_signal_to_log(self, signal: ResonanceTradeSignal):
        """将新信号写入日志文件"""
        # 统计启用的指标数量
        enabled_count = sum([
            self.strategy.resonance_strategy.use_macd,
            self.strategy.resonance_strategy.use_rsi,
            self.strategy.resonance_strategy.use_kdj,
            self.strategy.resonance_strategy.use_boll,
            self.strategy.resonance_strategy.use_ema,
            self.strategy.resonance_strategy.use_cci,
            self.strategy.resonance_strategy.use_atr,
            self.strategy.resonance_strategy.use_vwap,
        ])
        total_indicators = enabled_count

        with open(self.trade_log_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 100 + "\n")
            f.write(f"[新信号] ID: {signal.signal_id}\n")
            f.write(f"时间: {signal.datetime_str}\n")
            f.write(f"类型: {signal.signal_type.value}\n")
            f.write(f"开仓价格: {signal.entry_price:.2f}\n")
            f.write(f"评分: 总分{signal.total_score:.2f}/100, 信心度{signal.confidence:.2%}\n")
            f.write(f"共振: {signal.resonance_count}/{total_indicators}个指标, 趋势一致: {'✓' if signal.trend_aligned else '✗'}\n")
            f.write(f"\n各指标详情:\n")
            for indicator, detail in signal.score_details.items():
                f.write(f"  [{indicator}] {detail.get('reason', 'N/A')}\n")
                if 'score' in detail:
                    f.write(f"           得分: {detail['score']:.2f}\n")
            f.write(f"\n预测:\n")
            f.write(f"  - 10分钟: {signal.predicted_10min}\n")
            f.write(f"  - 30分钟: {signal.predicted_30min}\n")
            f.write(f"  - 1小时: {signal.predicted_1hour}\n")
            f.write(f"\n信号原因:\n")
            for reason in signal.reasons:
                f.write(f"  - {reason}\n")
            f.write("=" * 100 + "\n")
            f.flush()

    def _write_verification_to_log(self, signal: ResonanceTradeSignal, timeframe: str,
                                   predicted: str, actual_price: float, actual_result: str,
                                   is_correct: bool):
        """将验证结果写入日志文件"""
        change = actual_price - signal.entry_price
        change_pct = change / signal.entry_price * 100
        result_str = "✓ 正确" if is_correct else "✗ 错误"

        with open(self.trade_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{timeframe}验证] ID: {signal.signal_id}\n")
            f.write(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"预测方向: {predicted} | 实际结果: {actual_result} | {result_str}\n")
            f.write(f"开仓价格: {signal.entry_price:.2f}\n")
            f.write(f"当前价格: {actual_price:.2f}\n")
            f.write(f"价格变化: {change:+.2f} ({change_pct:+.2f}%)\n")

            if timeframe == "1小时" and signal.is_1hour_checked:
                f.write(f"\n[信号总结] ID: {signal.signal_id}\n")
                f.write(f"开仓时间: {signal.datetime_str}\n")
                f.write(f"开仓价格: {signal.entry_price:.2f}\n")
                f.write(f"信号类型: {signal.signal_type.value}\n")
                f.write(f"总评分: {signal.total_score:.2f} (信心度: {signal.confidence:.2%})\n")

                result_10 = "✓" if signal.predicted_10min == signal.actual_10min_result else "✗"
                f.write(f"10分钟: {signal.predicted_10min} -> {signal.actual_10min_result} {result_10}\n")

                result_30 = "✓" if signal.predicted_30min == signal.actual_30min_result else "✗"
                f.write(f"30分钟: {signal.predicted_30min} -> {signal.actual_30min_result} {result_30}\n")

                result_1h = "✓" if signal.predicted_1hour == signal.actual_1hour_result else "✗"
                f.write(f"1小时: {signal.predicted_1hour} -> {signal.actual_1hour_result} {result_1h}\n")

                f.write(f"信号已完成所有验证\n")
                f.write("=" * 100 + "\n")

            f.flush()

    def _sync_stats_to_dashboard(self):
        """同步统计数据到dashboard"""
        stats = {
            'total': self.total_signals,
            'active': len(self.active_signals),
            'completed': len(self.completed_signals),
            'accuracy': {
                '10m': {
                    'correct': self.correct_10min,
                    'checked': self.checked_10min
                },
                '30m': {
                    'correct': self.correct_30min,
                    'checked': self.checked_30min
                },
                '1h': {
                    'correct': self.correct_1hour,
                    'checked': self.checked_1hour
                }
            }
        }
        self.dashboard.update_stats(stats)

    def _generate_trading_suggestion(self) -> Optional[Dict[str, Any]]:
        """根据当前共振得分生成交易建议"""
        if not self.strategy.latest_resonance_score:
            return None

        score = self.strategy.latest_resonance_score

        if score.signal_type == SignalType.BUY and score.strength >= self.strategy.resonance_strategy.min_score:
            bias = "LONG"
            action = "建议做多"
            summary = f"共振{score.resonance_count}/5, 评分{score.strength:.1f}, 信心{score.confidence:.1%}"
        elif score.signal_type == SignalType.SELL and score.strength >= self.strategy.resonance_strategy.min_score:
            bias = "SHORT"
            action = "建议做空"
            summary = f"共振{score.resonance_count}/5, 评分{score.strength:.1f}, 信心{score.confidence:.1%}"
        else:
            bias = "NEUTRAL"
            action = "观望等待"
            summary = f"共振{score.resonance_count}/5, 评分{score.strength:.1f}未达阈值"

        # 统计各指标倾向
        details = {'buy': [], 'sell': [], 'wait': []}
        for indicator, signal in self.strategy.latest_indicator_signals.items():
            if signal == 'BUY':
                details['buy'].append(indicator)
            elif signal == 'SELL':
                details['sell'].append(indicator)
            else:
                details['wait'].append(indicator)

        return {
            'bias': bias,
            'confidence': score.confidence,
            'action': action,
            'summary': summary,
            'votes': {
                'buy': len(details['buy']),
                'sell': len(details['sell']),
                'wait': len(details['wait'])
            },
            'details': details,
            'score': {
                'total': score.strength,
                'resonance': score.resonance_count,
                'trend_aligned': score.trend_aligned
            },
            'updated_at': datetime.now().strftime("%H:%M:%S")
        }

    async def initialize_klines(self):
        """初始化历史K线数据"""
        import aiohttp

        # 如果使用代理，导入ProxyConnector
        if self.use_proxy:
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(self.proxy_url)
        else:
            connector = None

        params = {
            'pair': self.symbol.upper(),
            'contractType': self.contract_type.upper(),
            'interval': self.interval,
            'limit': 200
        }

        base_url = "https://fapi.binance.com"
        url = f"{base_url}/fapi/v1/continuousKlines"

        print(f"[初始化] 正在获取历史K线数据...")

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")

                    klines = await response.json()

                    if not klines:
                        print(f"[警告] 返回的K线数据为空")
                        return

                    for k in klines:
                        kline = KlineData(
                            timestamp=int(k[0]),
                            open=float(k[1]),
                            high=float(k[2]),
                            low=float(k[3]),
                            close=float(k[4]),
                            volume=float(k[5]),
                            is_closed=True
                        )
                        self.kline_history.append(kline)
                        # 传入当前已有的K线历史（不包含当前kline，因为已经append了）
                        self.strategy.update(kline, list(self.kline_history)[:-1])

                    first_ts = datetime.fromtimestamp(klines[0][0] / 1000)
                    last_ts = datetime.fromtimestamp(klines[-1][0] / 1000)
                    print(f"[成功] 已加载 {len(klines)} 条历史K线数据")
                    print(f"[时间范围] {first_ts} 到 {last_ts}")
        except Exception as e:
            print(f"[错误] 获取历史K线数据失败: {e}")

    async def process_kline_message(self, msg: dict):
        """处理K线消息"""
        k = msg['k']

        kline = KlineData(
            timestamp=int(k['t']),
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v']),
            is_closed=k['x']
        )

        self.latest_stream_kline = kline

        # 实时用最新价格刷新指标（传入K线历史）
        signal = self.strategy.update(kline, list(self.kline_history))

        # 更新dashboard
        if self.use_dashboard:
            kline_dict = self._kline_to_dict(kline)
            indicator_snapshot = self.strategy.get_indicator_snapshot()
            suggestion = self._generate_trading_suggestion()

            self.dashboard.update_market(kline=kline_dict, suggestion=suggestion)
            self.dashboard.update_indicators(indicator_snapshot, suggestion=suggestion)

        # 只在K线关闭时处理信号
        if kline.is_closed:
            self.current_kline = kline
            self.kline_history.append(kline)

            if signal:
                self.active_signals.append(signal)
                self.total_signals += 1

                # 写入日志
                self._write_signal_to_log(signal)

                # 更新dashboard
                if self.use_dashboard:
                    latest_signal_dict = self._signal_to_dict(signal)
                    active_signals_list = [self._signal_to_dict(s) for s in self.active_signals[-5:]]
                    self.dashboard.update_signals(latest_signal_dict, active_signals_list)
                    self.dashboard.push_alert(
                        f"新{signal.signal_type.value}信号 @ {signal.entry_price:.2f} (评分{signal.total_score:.1f})",
                        level="success"
                    )

            # 检查待验证的信号
            await self.check_pending_signals(kline)

            # 同步统计数据到dashboard
            if self.use_dashboard:
                self._sync_stats_to_dashboard()

    async def check_pending_signals(self, current_kline: KlineData):
        """检查待验证的信号"""
        current_time = current_kline.timestamp
        current_price = current_kline.close

        for signal in self.active_signals[:]:
            # 10分钟验证
            if not signal.is_10min_checked and current_time >= signal.check_10min_time:
                signal.actual_10min_price = current_price
                if current_price > signal.entry_price:
                    signal.actual_10min_result = "HIGHER"
                elif current_price < signal.entry_price:
                    signal.actual_10min_result = "LOWER"
                else:
                    signal.actual_10min_result = "EQUAL"

                signal.is_10min_checked = True
                self.checked_10min += 1

                is_correct = signal.predicted_10min == signal.actual_10min_result
                if is_correct:
                    self.correct_10min += 1

                self._write_verification_to_log(
                    signal, "10分钟", signal.predicted_10min,
                    current_price, signal.actual_10min_result, is_correct
                )

                if self.use_dashboard:
                    change_pct = (current_price - signal.entry_price) / signal.entry_price * 100
                    result_str = "正确" if is_correct else "错误"
                    self.dashboard.push_alert(
                        f"10分验证{result_str}: 变化{change_pct:+.2f}%",
                        level="success" if is_correct else "warning"
                    )

            # 30分钟验证
            if not signal.is_30min_checked and current_time >= signal.check_30min_time:
                signal.actual_30min_price = current_price
                if current_price > signal.entry_price:
                    signal.actual_30min_result = "HIGHER"
                elif current_price < signal.entry_price:
                    signal.actual_30min_result = "LOWER"
                else:
                    signal.actual_30min_result = "EQUAL"

                signal.is_30min_checked = True
                self.checked_30min += 1

                is_correct = signal.predicted_30min == signal.actual_30min_result
                if is_correct:
                    self.correct_30min += 1

                self._write_verification_to_log(
                    signal, "30分钟", signal.predicted_30min,
                    current_price, signal.actual_30min_result, is_correct
                )

                if self.use_dashboard:
                    change_pct = (current_price - signal.entry_price) / signal.entry_price * 100
                    result_str = "正确" if is_correct else "错误"
                    self.dashboard.push_alert(
                        f"30分验证{result_str}: 变化{change_pct:+.2f}%",
                        level="success" if is_correct else "warning"
                    )

            # 1小时验证
            if not signal.is_1hour_checked and current_time >= signal.check_1hour_time:
                signal.actual_1hour_price = current_price
                if current_price > signal.entry_price:
                    signal.actual_1hour_result = "HIGHER"
                elif current_price < signal.entry_price:
                    signal.actual_1hour_result = "LOWER"
                else:
                    signal.actual_1hour_result = "EQUAL"

                signal.is_1hour_checked = True
                self.checked_1hour += 1

                is_correct = signal.predicted_1hour == signal.actual_1hour_result
                if is_correct:
                    self.correct_1hour += 1

                self._write_verification_to_log(
                    signal, "1小时", signal.predicted_1hour,
                    current_price, signal.actual_1hour_result, is_correct
                )

                if self.use_dashboard:
                    change_pct = (current_price - signal.entry_price) / signal.entry_price * 100
                    result_str = "正确" if is_correct else "错误"
                    self.dashboard.push_alert(
                        f"1小时验证{result_str}: 变化{change_pct:+.2f}%",
                        level="success" if is_correct else "warning"
                    )
                    self.dashboard.push_alert(
                        f"信号 {signal.signal_id[:15]} 已完成所有验证",
                        level="info"
                    )

                # 移到已完成列表
                self.completed_signals.append(signal)
                self.active_signals.remove(signal)

    def _kline_to_dict(self, kline: KlineData) -> Dict[str, Any]:
        """将K线数据转换为字典"""
        return {
            'timestamp': kline.timestamp,
            'datetime': datetime.fromtimestamp(kline.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'open': kline.open,
            'high': kline.high,
            'low': kline.low,
            'close': kline.close,
            'volume': kline.volume,
            'is_closed': kline.is_closed
        }

    def _signal_to_dict(self, signal: ResonanceTradeSignal) -> Dict[str, Any]:
        """将信号转换为dashboard格式"""
        progress = []

        if signal.check_10min_time:
            progress.append({
                'label': '10分钟',
                'predicted': signal.predicted_10min,
                'actual': f"{signal.actual_10min_price:.2f}" if signal.actual_10min_price else None,
                'result': '命中' if signal.is_10min_checked and signal.predicted_10min == signal.actual_10min_result
                         else '偏离' if signal.is_10min_checked else '等待'
            })

        if signal.check_30min_time:
            progress.append({
                'label': '30分钟',
                'predicted': signal.predicted_30min,
                'actual': f"{signal.actual_30min_price:.2f}" if signal.actual_30min_price else None,
                'result': '命中' if signal.is_30min_checked and signal.predicted_30min == signal.actual_30min_result
                         else '偏离' if signal.is_30min_checked else '等待'
            })

        if signal.check_1hour_time:
            progress.append({
                'label': '1小时',
                'predicted': signal.predicted_1hour,
                'actual': f"{signal.actual_1hour_price:.2f}" if signal.actual_1hour_price else None,
                'result': '命中' if signal.is_1hour_checked and signal.predicted_1hour == signal.actual_1hour_result
                         else '偏离' if signal.is_1hour_checked else '等待'
            })

        if signal.is_1hour_checked:
            status = "已完成"
        elif signal.is_30min_checked:
            status = "进行中 (2/3)"
        elif signal.is_10min_checked:
            status = "进行中 (1/3)"
        else:
            status = "等待验证"

        return {
            'id': signal.signal_id,
            'type': signal.signal_type.value,
            'direction': 'LONG' if signal.signal_type == SignalType.BUY else 'SHORT',
            'entry_price': signal.entry_price,
            'time': signal.datetime_str,
            'reasons': signal.reasons,
            'status': status,
            'progress': progress,
            'score': {
                'total': signal.total_score,
                'confidence': signal.confidence,
                'resonance': signal.resonance_count
            }
        }

    async def run(self):
        """运行实时交易系统"""
        self.dashboard.update_meta(connection="加载历史数据...")
        await self.initialize_klines()

        if self.use_dashboard:
            self.dashboard.start()
            self.dashboard.push_alert("系统启动中...", level="info")

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                ws_kwargs = {
                    'ping_interval': WS_PING_INTERVAL,
                    'ping_timeout': WS_PING_TIMEOUT,
                    'close_timeout': WS_CLOSE_TIMEOUT
                }

                if self.use_dashboard:
                    self.dashboard.update_meta(connection=f"连接中 ({retry_count + 1}/{self.max_retries})")

                async with websockets.connect(self.ws_url, **ws_kwargs) as websocket:
                    retry_count = 0

                    if self.use_dashboard:
                        self.dashboard.update_meta(connection="已连接")
                        self.dashboard.push_alert("WebSocket已连接", level="success")

                    msg_count = 0
                    last_heartbeat_time = time.time()

                    while True:
                        try:
                            message = await websocket.recv()
                            msg_count += 1

                            current_time = time.time()
                            if current_time - last_heartbeat_time >= self.heartbeat_interval:
                                if self.use_dashboard:
                                    self.dashboard.update_heartbeat(msg_count)
                                last_heartbeat_time = current_time

                            data = json.loads(message)

                            if 'k' in data:
                                await self.process_kline_message(data)

                        except websockets.exceptions.ConnectionClosed:
                            if self.use_dashboard:
                                self.dashboard.update_meta(connection="连接断开")
                                self.dashboard.push_alert("WebSocket连接断开，重连中...", level="warning")
                            break
                        except Exception as e:
                            if self.use_dashboard:
                                self.dashboard.push_alert(f"处理消息错误: {str(e)}", level="error")
                            print(f"[错误] 处理K线消息时出错: {e}")
                            import traceback
                            traceback.print_exc()
                            await asyncio.sleep(1)

            except Exception as e:
                retry_count += 1
                if self.use_dashboard:
                    self.dashboard.update_meta(connection=f"连接失败 ({retry_count}/{self.max_retries})")
                    self.dashboard.push_alert(f"连接失败，重试中...", level="error")
                await asyncio.sleep(5)

        if self.use_dashboard:
            self.dashboard.update_meta(connection="已停止")
            self.dashboard.push_alert("达到最大重试次数，系统停止", level="error")
            await asyncio.sleep(3)
            self.dashboard.stop()

    def export_results(self, filename: str = "live_trading_resonance_results.json"):
        """导出结果到JSON文件"""
        results = {
            'summary': {
                'strategy': 'resonance',
                'min_resonance': self.strategy.resonance_strategy.min_resonance,
                'min_score': self.strategy.resonance_strategy.min_score,
                'total_signals': self.total_signals,
                'accuracy_10min': self.correct_10min / self.checked_10min * 100 if self.checked_10min > 0 else 0,
                'accuracy_30min': self.correct_30min / self.checked_30min * 100 if self.checked_30min > 0 else 0,
                'accuracy_1hour': self.correct_1hour / self.checked_1hour * 100 if self.checked_1hour > 0 else 0,
                'checked_10min': self.checked_10min,
                'checked_30min': self.checked_30min,
                'checked_1hour': self.checked_1hour,
                'correct_10min': self.correct_10min,
                'correct_30min': self.correct_30min,
                'correct_1hour': self.correct_1hour
            },
            'completed_signals': [
                {
                    'signal_id': s.signal_id,
                    'timestamp': s.timestamp,
                    'datetime': s.datetime_str,
                    'type': s.signal_type.value,
                    'entry_price': s.entry_price,
                    'score': {
                        'total': s.total_score,
                        'confidence': s.confidence,
                        'resonance_count': s.resonance_count,
                        'trend_aligned': s.trend_aligned
                    },
                    'score_details': s.score_details,
                    'reasons': s.reasons,
                    'indicators': s.indicators,
                    '10min': {
                        'predicted': s.predicted_10min,
                        'actual_price': s.actual_10min_price,
                        'actual_result': s.actual_10min_result,
                        'correct': s.predicted_10min == s.actual_10min_result
                    },
                    '30min': {
                        'predicted': s.predicted_30min,
                        'actual_price': s.actual_30min_price,
                        'actual_result': s.actual_30min_result,
                        'correct': s.predicted_30min == s.actual_30min_result
                    },
                    '1hour': {
                        'predicted': s.predicted_1hour,
                        'actual_price': s.actual_1hour_price,
                        'actual_result': s.actual_1hour_result,
                        'correct': s.predicted_1hour == s.actual_1hour_result
                    }
                }
                for s in self.completed_signals
            ]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n[导出] 结果已保存到: {filename}")


async def main():
    """主函数"""
    # 创建共振策略（所有参数从config.py读取）
    # 如果需要自定义参数，可以传入参数覆盖config.py的默认值
    strategy = ResonanceMultiIndicatorStrategy()

    # 创建实时交易系统（所有参数从config.py读取）
    # 如果需要自定义参数，可以传入参数覆盖config.py的默认值
    system = BinanceResonanceLiveTradingSystem(strategy=strategy)

    try:
        await system.run()
    except KeyboardInterrupt:
        if system.use_dashboard:
            system.dashboard.stop()
        print("\n[停止] 用户中断，正在保存结果...")
        system.export_results()
        print("[完成] 系统已停止")


if __name__ == '__main__':
    asyncio.run(main())
