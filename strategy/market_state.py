# -*- coding: utf-8 -*-
"""
市场状态识别模块

基于 ADX 指标和辅助信号识别当前市场状态：
- RANGING: 震荡盘整（ADX < 20）
- TRENDING_UP: 上升趋势（ADX >= 20 且 +DI > -DI）
- TRENDING_DOWN: 下降趋势（ADX >= 20 且 -DI > +DI）
- BREAKOUT_UP: 向上突破（ADX > 40 或 ATR/成交量异常 + 价格突破）
- BREAKOUT_DOWN: 向下突破
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import (
    ADXIndicator, ADXAnalyzer, TrendDirection, TrendStrength,
    ATRIndicator,
    VolumeAnalyzer, VolumeCondition
)
from strategy_config import get_market_state_thresholds, is_indicator_enabled


class MarketState(Enum):
    """市场状态枚举"""
    RANGING = "ranging"                 # 震荡盘整
    TRENDING_UP = "trending_up"         # 上升趋势
    TRENDING_DOWN = "trending_down"     # 下降趋势
    BREAKOUT_UP = "breakout_up"         # 向上突破
    BREAKOUT_DOWN = "breakout_down"     # 向下突破
    UNKNOWN = "unknown"                 # 未知状态


@dataclass
class MarketStateResult:
    """市场状态识别结果"""
    state: MarketState
    confidence: float                   # 置信度 0-1
    adx: Optional[float]                # ADX值
    plus_di: Optional[float]            # +DI值
    minus_di: Optional[float]           # -DI值
    trend_strength: TrendStrength       # 趋势强度
    trend_direction: TrendDirection     # 趋势方向
    is_breakout: bool                   # 是否处于突破状态
    breakout_direction: Optional[str]   # 突破方向 'up'/'down'
    volume_spike: bool                  # 是否放量
    atr_expanding: bool                 # ATR是否扩大
    details: Dict[str, Any]             # 详细信息


class MarketStateDetector:
    """
    市场状态检测器

    使用 ADX 作为核心指标，结合 ATR 和成交量判断市场状态
    """

    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        volume_ma_period: int = 20,
        ranging_threshold: float = None,
        trending_threshold: float = None,
        strong_trend_threshold: float = None,
        volume_spike_threshold: float = None,
        atr_spike_threshold: float = None
    ):
        """
        初始化市场状态检测器

        Args:
            adx_period: ADX周期
            atr_period: ATR周期
            volume_ma_period: 成交量MA周期
            ranging_threshold: 震荡阈值（ADX低于此值）
            trending_threshold: 趋势阈值（ADX高于此值认为有趋势）
            strong_trend_threshold: 强趋势阈值（ADX高于此值认为强趋势/突破）
            volume_spike_threshold: 成交量放大阈值
            atr_spike_threshold: ATR放大阈值
        """
        # 从配置获取默认值
        thresholds = get_market_state_thresholds()

        self.ranging_threshold = ranging_threshold or thresholds.get("adx_ranging_threshold", 20)
        self.trending_threshold = trending_threshold or thresholds.get("adx_trending_threshold", 25)
        self.strong_trend_threshold = strong_trend_threshold or thresholds.get("adx_strong_trend_threshold", 40)
        self.volume_spike_threshold = volume_spike_threshold or thresholds.get("volume_spike_for_breakout", 1.5)
        self.atr_spike_threshold = atr_spike_threshold or thresholds.get("atr_spike_for_breakout", 1.3)

        # 初始化指标计算器
        self.adx_analyzer = ADXAnalyzer(period=adx_period)
        self.atr_indicator = ATRIndicator(period=atr_period)
        self.volume_analyzer = VolumeAnalyzer(ma_period=volume_ma_period)

    def detect(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None
    ) -> MarketStateResult:
        """
        检测市场状态

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列（可选）

        Returns:
            MarketStateResult 包含市场状态和详细信息
        """
        # 1. 计算 ADX
        adx_result = self.adx_analyzer.analyze(highs, lows, closes)
        adx = adx_result['adx']
        plus_di = adx_result['plus_di']
        minus_di = adx_result['minus_di']
        trend_strength = adx_result['trend_strength']
        trend_direction = adx_result['trend_direction']
        adx_rising = adx_result.get('adx_rising', False)
        di_crossover = adx_result.get('di_crossover')

        # 2. 计算 ATR 变化
        atr_result = self.atr_indicator.calculate(highs, lows, closes)
        atr_series = atr_result['atr_series']
        atr_expanding = self._check_atr_expanding(atr_series)

        # 3. 分析成交量
        volume_spike = False
        volume_condition = VolumeCondition.NORMAL
        if volumes is not None and len(volumes) > 0:
            volume_result = self.volume_analyzer.analyze(volumes, closes)
            volume_spike = volume_result['is_volume_spike']
            volume_condition = volume_result['volume_condition']

        # 4. 检测价格突破
        is_breakout, breakout_direction = self._check_price_breakout(
            highs, lows, closes, atr_result['atr']
        )

        # 5. 综合判断市场状态
        state, confidence = self._determine_market_state(
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            trend_strength=trend_strength,
            trend_direction=trend_direction,
            adx_rising=adx_rising,
            di_crossover=di_crossover,
            atr_expanding=atr_expanding,
            volume_spike=volume_spike,
            volume_condition=volume_condition,
            is_breakout=is_breakout,
            breakout_direction=breakout_direction
        )

        return MarketStateResult(
            state=state,
            confidence=confidence,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            trend_strength=trend_strength,
            trend_direction=trend_direction,
            is_breakout=is_breakout,
            breakout_direction=breakout_direction,
            volume_spike=volume_spike,
            atr_expanding=atr_expanding,
            details={
                'adx_rising': adx_rising,
                'di_crossover': di_crossover,
                'volume_condition': volume_condition.value if volume_condition else None,
                'atr': atr_result['atr'],
                'atr_series': atr_series[-5:] if atr_series else [],
            }
        )

    def _check_atr_expanding(self, atr_series: List[Optional[float]]) -> bool:
        """检查ATR是否正在扩大"""
        valid_atr = [v for v in atr_series if v is not None]
        if len(valid_atr) < 3:
            return False

        # 比较最近的ATR与前几根的平均值
        recent_atr = valid_atr[-1]
        prev_avg = sum(valid_atr[-4:-1]) / 3 if len(valid_atr) >= 4 else valid_atr[-2]

        return recent_atr > prev_avg * self.atr_spike_threshold

    def _check_price_breakout(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        atr: Optional[float]
    ) -> tuple:
        """
        检测价格突破

        Returns:
            (is_breakout, direction) - direction: 'up'/'down'/None
        """
        if len(highs) < 20 or atr is None:
            return False, None

        # 获取近20根K线的最高点和最低点
        lookback = min(20, len(highs) - 1)
        recent_high = max(highs[-lookback-1:-1])
        recent_low = min(lows[-lookback-1:-1])
        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        # 向上突破：当前收盘价突破近期最高点
        if current_close > recent_high and (current_close - recent_high) > atr * 0.5:
            return True, 'up'

        # 向下突破：当前收盘价跌破近期最低点
        if current_close < recent_low and (recent_low - current_close) > atr * 0.5:
            return True, 'down'

        return False, None

    def _determine_market_state(
        self,
        adx: Optional[float],
        plus_di: Optional[float],
        minus_di: Optional[float],
        trend_strength: TrendStrength,
        trend_direction: TrendDirection,
        adx_rising: bool,
        di_crossover: Optional[str],
        atr_expanding: bool,
        volume_spike: bool,
        volume_condition: VolumeCondition,
        is_breakout: bool,
        breakout_direction: Optional[str]
    ) -> tuple:
        """
        综合判断市场状态

        Returns:
            (state, confidence)
        """
        if adx is None:
            return MarketState.UNKNOWN, 0.0

        confidence = 0.5  # 基础置信度

        # 情况1: 强趋势 + 突破特征 -> 突破状态
        if (adx > self.strong_trend_threshold or
            (is_breakout and (atr_expanding or volume_spike))):

            if is_breakout:
                confidence = 0.85

                # 成交量和ATR都确认突破，置信度更高
                if atr_expanding:
                    confidence += 0.05
                if volume_spike:
                    confidence += 0.05

                if breakout_direction == 'up':
                    return MarketState.BREAKOUT_UP, min(confidence, 1.0)
                else:
                    return MarketState.BREAKOUT_DOWN, min(confidence, 1.0)

            # ADX很高但没有明确突破信号，可能是强趋势
            elif adx > self.strong_trend_threshold:
                confidence = 0.75
                if trend_direction == TrendDirection.UP:
                    return MarketState.TRENDING_UP, confidence
                elif trend_direction == TrendDirection.DOWN:
                    return MarketState.TRENDING_DOWN, confidence

        # 情况2: ADX在趋势区间 -> 趋势状态
        if adx >= self.ranging_threshold:
            confidence = 0.6

            # ADX上升表示趋势加强
            if adx_rising:
                confidence += 0.1

            # DI交叉可能表示趋势转换初期
            if di_crossover:
                confidence += 0.1

            if trend_direction == TrendDirection.UP or plus_di > minus_di:
                return MarketState.TRENDING_UP, min(confidence, 1.0)
            elif trend_direction == TrendDirection.DOWN or minus_di > plus_di:
                return MarketState.TRENDING_DOWN, min(confidence, 1.0)

        # 情况3: ADX低 -> 震荡状态
        if adx < self.ranging_threshold:
            confidence = 0.7

            # ADX正在下降，震荡特征更明显
            if not adx_rising:
                confidence += 0.1

            # 成交量萎缩，更可能是震荡
            if volume_condition in [VolumeCondition.LOW, VolumeCondition.VERY_LOW]:
                confidence += 0.05

            return MarketState.RANGING, min(confidence, 1.0)

        # 默认返回未知
        return MarketState.UNKNOWN, 0.3

    def get_recommended_strategy(self, state: MarketState) -> str:
        """
        根据市场状态推荐策略

        Args:
            state: 市场状态

        Returns:
            推荐的策略名称
        """
        strategy_map = {
            MarketState.RANGING: "ranging",
            MarketState.TRENDING_UP: "trending",
            MarketState.TRENDING_DOWN: "trending",
            MarketState.BREAKOUT_UP: "breakout",
            MarketState.BREAKOUT_DOWN: "breakout",
            MarketState.UNKNOWN: "none"
        }
        return strategy_map.get(state, "none")

    def is_suitable_for_trading(self, result: MarketStateResult) -> bool:
        """
        判断当前市场状态是否适合交易

        Args:
            result: 市场状态检测结果

        Returns:
            是否适合交易
        """
        # 未知状态不适合交易
        if result.state == MarketState.UNKNOWN:
            return False

        # 置信度太低不适合交易
        if result.confidence < 0.5:
            return False

        return True
