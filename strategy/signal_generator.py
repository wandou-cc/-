# -*- coding: utf-8 -*-
"""
信号生成器 - 核心模块

整合市场状态识别、子策略、多周期确认等模块，
生成最终的交易信号。

工作流程：
1. 识别市场状态（ADX驱动）
2. 根据市场状态选择对应策略
3. 执行策略分析生成初步信号
4. 多周期确认
5. 输出最终信号（含预测信息）
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.market_state import MarketState, MarketStateDetector, MarketStateResult
from strategy.multi_timeframe import MultiTimeframeConfirmer, MultiTimeframeResult
from strategy.strategies import (
    RangingStrategy, TrendingStrategy, BreakoutStrategy,
    StrategySignal, SignalDirection
)
from strategy_config import (
    get_signal_thresholds, get_prediction_horizons,
    get_risk_config, is_strategy_enabled
)
from indicators import (
    RSIIndicator, MACDIndicator, EMAIndicator,
    BollingerBandsIndicator, ATRIndicator, VolumeAnalyzer
)


class SignalGrade(Enum):
    """信号等级"""
    A = "A"  # 强信号 >= 75%
    B = "B"  # 标准信号 >= 50%
    C = "C"  # 弱信号 >= 30%
    NONE = "NONE"  # 无信号


@dataclass
class Prediction:
    """价格预测"""
    horizon_minutes: int          # 预测周期（分钟）
    direction: str                # 预测方向 'up'/'down'/'neutral'
    confidence: float             # 置信度 0-1
    target_price: Optional[float] = None  # 目标价格（可选）


@dataclass
class TradingSignal:
    """完整的交易信号"""
    # 基本信息
    signal_id: str
    timestamp: datetime
    symbol: str

    # 信号核心
    direction: SignalDirection
    strength: float               # 原始强度 0-1
    adjusted_strength: float      # 多周期确认后的强度
    grade: SignalGrade

    # 市场状态
    market_state: MarketState
    strategy_used: str

    # 多周期确认
    is_confirmed: bool
    confirmation_count: int
    timeframe_confirmations: Dict[str, bool]

    # 价格建议
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]

    # 预测信息
    predictions: List[Prediction] = field(default_factory=list)

    # 详细信息
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    indicator_values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'signal_id': self.signal_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'direction': self.direction.value,
            'strength': self.strength,
            'adjusted_strength': self.adjusted_strength,
            'grade': self.grade.value,
            'market_state': self.market_state.value,
            'strategy_used': self.strategy_used,
            'is_confirmed': self.is_confirmed,
            'confirmation_count': self.confirmation_count,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'predictions': [
                {
                    'horizon_minutes': p.horizon_minutes,
                    'direction': p.direction,
                    'confidence': p.confidence,
                    'target_price': p.target_price
                }
                for p in self.predictions
            ],
            'reasons': self.reasons,
            'warnings': self.warnings,
            'indicator_values': self.indicator_values
        }


class SignalGenerator:
    """
    信号生成器

    核心类，整合所有模块生成交易信号
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        config: Dict[str, Any] = None
    ):
        """
        初始化信号生成器

        Args:
            symbol: 交易对符号
            config: 自定义配置
        """
        self.symbol = symbol
        self.config = config or {}

        # 初始化市场状态检测器
        self.state_detector = MarketStateDetector()

        # 初始化子策略
        self.strategies = {
            'ranging': RangingStrategy() if is_strategy_enabled('ranging') else None,
            'trending': TrendingStrategy() if is_strategy_enabled('trending') else None,
            'breakout': BreakoutStrategy() if is_strategy_enabled('breakout') else None,
        }

        # 初始化多周期确认器
        self.mtf_confirmer = MultiTimeframeConfirmer()

        # 初始化仪表盘指标计算器（确保所有指标都能被计算）
        self._rsi = RSIIndicator(period=14)
        self._macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        self._ema5 = EMAIndicator(period=5)
        self._ema20 = EMAIndicator(period=20)
        self._ema60 = EMAIndicator(period=60)
        self._bb = BollingerBandsIndicator(period=20, std_dev=2.0)
        self._atr = ATRIndicator(period=14)
        self._volume_analyzer = VolumeAnalyzer(ma_period=20)

        # 信号阈值
        self.thresholds = get_signal_thresholds()
        self.prediction_horizons = get_prediction_horizons()
        self.risk_config = get_risk_config()

    def generate(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None,
        timeframe_data: Optional[Dict[str, Dict[str, List[float]]]] = None
    ) -> TradingSignal:
        """
        生成交易信号

        Args:
            highs: 主周期最高价序列
            lows: 主周期最低价序列
            closes: 主周期收盘价序列
            volumes: 主周期成交量序列（可选）
            timeframe_data: 多周期数据（可选，用于多周期确认）
                格式: {"15m": {"highs": [...], ...}, "1h": {...}}

        Returns:
            TradingSignal 完整的交易信号
        """
        timestamp = datetime.now()
        signal_id = str(uuid.uuid4())[:8]

        # 数据验证
        if len(closes) < 60:
            return self._no_signal(signal_id, timestamp, "数据不足")

        current_price = closes[-1]

        # 步骤0：计算仪表盘基础指标（确保所有路径都有完整指标）
        dashboard_indicators = self._compute_dashboard_indicators(highs, lows, closes, volumes)

        # 步骤1：识别市场状态
        market_state_result = self.state_detector.detect(highs, lows, closes, volumes)
        market_state = market_state_result.state

        # 基础指标值（包含ADX和仪表盘指标）
        base_indicators = {
            **dashboard_indicators,
            'adx': market_state_result.adx,
            'plus_di': market_state_result.plus_di,
            'minus_di': market_state_result.minus_di,
            'market_state_confidence': market_state_result.confidence
        }

        # 步骤2：选择策略
        strategy_name = self._select_strategy(market_state)
        strategy = self.strategies.get(strategy_name)

        if strategy is None:
            return self._no_signal(
                signal_id, timestamp,
                f"策略 {strategy_name} 未启用",
                market_state=market_state,
                indicator_values=base_indicators
            )

        # 步骤3：执行策略分析
        strategy_signal = strategy.analyze(highs, lows, closes, volumes)

        if strategy_signal.direction == SignalDirection.HOLD:
            # 即使无信号也要返回完整指标值
            return self._no_signal(
                signal_id, timestamp,
                strategy_signal.reasons[0] if strategy_signal.reasons else "无信号",
                market_state=market_state,
                strategy_used=strategy_name,
                indicator_values={
                    **base_indicators,
                    **strategy_signal.indicator_values  # 策略特有指标覆盖
                }
            )

        # 步骤4：多周期确认
        mtf_result = None
        is_confirmed = True
        confirmation_count = 0
        timeframe_confirmations = {}

        if timeframe_data:
            # 添加主周期数据
            primary_data = {
                "highs": highs,
                "lows": lows,
                "closes": closes,
                "volumes": volumes or []
            }
            full_tf_data = {"5m": primary_data, **timeframe_data}

            mtf_result = self.mtf_confirmer.confirm(
                strategy_signal.direction,
                strategy_signal.strength,
                full_tf_data
            )

            is_confirmed = mtf_result.is_confirmed
            confirmation_count = mtf_result.confirmation_count
            adjusted_strength = mtf_result.adjusted_strength

            for tf, conf in mtf_result.timeframe_results.items():
                timeframe_confirmations[tf] = conf.result.value == "confirmed"
        else:
            adjusted_strength = strategy_signal.strength

        # 步骤5：计算信号等级
        grade = self._calculate_grade(adjusted_strength)

        # 步骤6：生成预测
        predictions = self._generate_predictions(
            strategy_signal.direction,
            adjusted_strength,
            current_price,
            strategy_signal.indicator_values.get('atr')
        )

        # 步骤7：收集警告
        warnings = self._collect_warnings(
            market_state_result,
            strategy_signal,
            mtf_result,
            grade
        )

        # 步骤8：构建最终信号
        return TradingSignal(
            signal_id=signal_id,
            timestamp=timestamp,
            symbol=self.symbol,
            direction=strategy_signal.direction,
            strength=strategy_signal.strength,
            adjusted_strength=adjusted_strength,
            grade=grade,
            market_state=market_state,
            strategy_used=strategy_name,
            is_confirmed=is_confirmed,
            confirmation_count=confirmation_count,
            timeframe_confirmations=timeframe_confirmations,
            entry_price=strategy_signal.entry_price or current_price,
            stop_loss=strategy_signal.stop_loss,
            take_profit=strategy_signal.take_profit,
            predictions=predictions,
            reasons=strategy_signal.reasons,
            warnings=warnings,
            indicator_values={
                **base_indicators,  # 基础仪表盘指标
                **strategy_signal.indicator_values,  # 策略特有指标（覆盖）
            },
            metadata={
                'strategy_metadata': strategy_signal.metadata,
                'market_state_details': market_state_result.details,
                'mtf_final_score': mtf_result.final_score if mtf_result else None
            }
        )

    def _select_strategy(self, market_state: MarketState) -> str:
        """根据市场状态选择策略"""
        strategy_map = {
            MarketState.RANGING: 'ranging',
            MarketState.TRENDING_UP: 'trending',
            MarketState.TRENDING_DOWN: 'trending',
            MarketState.BREAKOUT_UP: 'breakout',
            MarketState.BREAKOUT_DOWN: 'breakout',
            MarketState.UNKNOWN: 'trending'  # 默认使用趋势策略
        }
        return strategy_map.get(market_state, 'trending')

    def _calculate_grade(self, strength: float) -> SignalGrade:
        """计算信号等级"""
        if strength >= self.thresholds['strong_signal']:
            return SignalGrade.A
        elif strength >= self.thresholds['standard_signal']:
            return SignalGrade.B
        elif strength >= self.thresholds['weak_signal']:
            return SignalGrade.C
        else:
            return SignalGrade.NONE

    def _generate_predictions(
        self,
        direction: SignalDirection,
        strength: float,
        current_price: float,
        atr: Optional[float]
    ) -> List[Prediction]:
        """生成价格预测"""
        predictions = []

        if direction == SignalDirection.HOLD:
            return predictions

        pred_direction = 'up' if direction == SignalDirection.BUY else 'down'

        for horizon in self.prediction_horizons:
            # 置信度随时间衰减
            time_decay = 1.0 - (horizon / 120) * 0.3  # 2小时内衰减30%
            confidence = strength * time_decay

            # 计算目标价格（基于ATR）
            target_price = None
            if atr:
                # 根据时间周期调整目标
                atr_multiplier = horizon / 30  # 30分钟 = 1倍ATR
                if direction == SignalDirection.BUY:
                    target_price = current_price + atr * atr_multiplier
                else:
                    target_price = current_price - atr * atr_multiplier

            predictions.append(Prediction(
                horizon_minutes=horizon,
                direction=pred_direction,
                confidence=round(confidence, 3),
                target_price=round(target_price, 2) if target_price else None
            ))

        return predictions

    def _collect_warnings(
        self,
        market_state_result: MarketStateResult,
        strategy_signal: StrategySignal,
        mtf_result: Optional[MultiTimeframeResult],
        grade: SignalGrade
    ) -> List[str]:
        """收集警告信息"""
        warnings = []

        # 市场状态置信度低
        if market_state_result.confidence < 0.6:
            warnings.append(f"市场状态不明确（置信度: {market_state_result.confidence:.0%}）")

        # 多周期未确认
        if mtf_result and not mtf_result.is_confirmed:
            warnings.append(f"多周期确认未通过（确认: {mtf_result.confirmation_count}个周期）")

        # 多周期有拒绝
        if mtf_result and mtf_result.rejection_count > 0:
            warnings.append(f"有{mtf_result.rejection_count}个周期明确拒绝")

        # 信号等级低
        if grade == SignalGrade.C:
            warnings.append("信号强度较弱，建议谨慎或观望")
        elif grade == SignalGrade.NONE:
            warnings.append("信号强度不足，不建议开仓")

        # 成交量警告
        if not market_state_result.volume_spike and market_state_result.state in [
            MarketState.BREAKOUT_UP, MarketState.BREAKOUT_DOWN
        ]:
            warnings.append("突破未伴随成交量放大")

        return warnings

    def _compute_dashboard_indicators(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        计算仪表盘需要的所有基础指标

        确保无论使用哪个策略，都能返回完整的指标集合用于显示
        """
        indicators = {}

        try:
            # RSI
            rsi_result = self._rsi.calculate(closes)
            indicators['rsi'] = rsi_result.get('rsi')

            # MACD
            macd_result = self._macd.calculate(closes)
            indicators['macd'] = macd_result.get('macd_line')
            indicators['macd_signal'] = macd_result.get('signal_line')
            indicators['macd_histogram'] = macd_result.get('histogram')

            # EMA
            ema5_result = self._ema5.calculate(closes)
            ema20_result = self._ema20.calculate(closes)
            ema60_result = self._ema60.calculate(closes)
            indicators['ema5'] = ema5_result.get('ema')
            indicators['ema20'] = ema20_result.get('ema')
            indicators['ema60'] = ema60_result.get('ema')

            # Bollinger Bands
            bb_result = self._bb.calculate(closes)
            indicators['bb_upper'] = bb_result.get('upper_band')
            indicators['bb_middle'] = bb_result.get('middle_band')
            indicators['bb_lower'] = bb_result.get('lower_band')
            indicators['bb_percent_b'] = bb_result.get('percent_b')

            # ATR
            atr_result = self._atr.calculate(highs, lows, closes)
            indicators['atr'] = atr_result.get('atr')

            # Volume
            if volumes and len(volumes) > 0:
                vol_result = self._volume_analyzer.analyze(volumes, closes)
                indicators['volume_ratio'] = vol_result.get('volume_ratio')

        except Exception as e:
            # 如果计算失败，返回已计算的指标
            pass

        return indicators

    def _no_signal(
        self,
        signal_id: str,
        timestamp: datetime,
        reason: str,
        market_state: MarketState = MarketState.UNKNOWN,
        strategy_used: str = "none",
        indicator_values: Dict[str, Any] = None
    ) -> TradingSignal:
        """生成无信号结果"""
        return TradingSignal(
            signal_id=signal_id,
            timestamp=timestamp,
            symbol=self.symbol,
            direction=SignalDirection.HOLD,
            strength=0.0,
            adjusted_strength=0.0,
            grade=SignalGrade.NONE,
            market_state=market_state,
            strategy_used=strategy_used,
            is_confirmed=False,
            confirmation_count=0,
            timeframe_confirmations={},
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            predictions=[],
            reasons=[reason],
            warnings=[],
            indicator_values=indicator_values or {},
            metadata={}
        )

    def get_signal_summary(self, signal: TradingSignal) -> str:
        """生成信号摘要"""
        if signal.direction == SignalDirection.HOLD:
            return f"[{signal.signal_id}] 无信号 - {signal.reasons[0] if signal.reasons else '未知原因'}"

        direction_str = "🟢 做多" if signal.direction == SignalDirection.BUY else "🔴 做空"
        grade_str = f"[{signal.grade.value}级]"

        summary = [
            f"{'='*50}",
            f"信号ID: {signal.signal_id}",
            f"方向: {direction_str} {grade_str}",
            f"强度: {signal.strength:.0%} → {signal.adjusted_strength:.0%} (调整后)",
            f"市场状态: {signal.market_state.value}",
            f"使用策略: {signal.strategy_used}",
            f"多周期确认: {'✓' if signal.is_confirmed else '✗'} ({signal.confirmation_count}个周期)",
            f"",
            f"入场价: {signal.entry_price:.2f}",
            f"止损价: {signal.stop_loss:.2f}" if signal.stop_loss else "止损价: 未设置",
            f"止盈价: {signal.take_profit:.2f}" if signal.take_profit else "止盈价: 未设置",
            f"",
            f"预测:",
        ]

        for pred in signal.predictions:
            arrow = "↑" if pred.direction == 'up' else "↓"
            target = f" → {pred.target_price:.2f}" if pred.target_price else ""
            summary.append(f"  {pred.horizon_minutes}分钟: {arrow} (置信度: {pred.confidence:.0%}){target}")

        if signal.reasons:
            summary.append(f"")
            summary.append(f"信号原因:")
            for reason in signal.reasons[:5]:
                summary.append(f"  • {reason}")

        if signal.warnings:
            summary.append(f"")
            summary.append(f"⚠️ 警告:")
            for warning in signal.warnings:
                summary.append(f"  • {warning}")

        summary.append(f"{'='*50}")

        return "\n".join(summary)
