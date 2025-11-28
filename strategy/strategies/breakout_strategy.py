# -*- coding: utf-8 -*-
"""
突破策略 (Breakout Strategy)

适用场景：ADX > 40 或 (ATR突增 + 成交量放大)
核心思路：确认突破后追入

做多条件：
- ���格突破近N根K线最高点
- 成交量 > 20周期均量 × 1.5 (放量确认)
- ATR 较前一周期放大 > 20%
- MACD > 0 且向上
- +DI > -DI (方向确认)

做空条件：
- 价格跌破近N根K线最低点
- 成交量 > 20周期均量 × 1.5 (放量确认)
- ATR 较前一周期放大 > 20%
- MACD < 0 且向下
- -DI > +DI (方向确认)

假突破过滤：
- 突破幅度必须 > ATR × 0.5
- 收盘价必须站稳突破位
- 成交量必须配合
"""

from typing import Dict, Any, Optional, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from indicators import (
    MACDIndicator,
    ATRIndicator,
    ADXIndicator,
    VolumeAnalyzer, VolumeCondition
)
from strategy_config import get_strategy_config

from .base_strategy import BaseStrategy, StrategySignal, SignalDirection


class BreakoutStrategy(BaseStrategy):
    """
    突破策略

    在突破行情中，价格快速脱离盘整区间。
    本策略在确认突破后追入，需要成交量和波动率配合。
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化突破策略

        Args:
            config: 策略配置，如果为None则使用默认配置
        """
        # 从全局配置获取默认值
        default_config = get_strategy_config("breakout") or {}

        # 合并配置
        merged_config = {**default_config, **(config or {})}
        super().__init__(name="breakout", config=merged_config)

        # 初始化指标
        self.macd_indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        self.atr_indicator = ATRIndicator(period=14)
        self.adx_indicator = ADXIndicator(period=14)
        self.volume_analyzer = VolumeAnalyzer(ma_period=20)

        # 策略参数
        self.lookback_period = self.get_config_value("lookback_period", 20)
        self.min_breakout_atr = self.get_config_value("min_breakout_atr", 0.5)
        self.volume_confirmation = self.get_config_value("volume_confirmation", True)
        self.min_volume_ratio = self.get_config_value("min_volume_ratio", 1.5)
        self.atr_expansion_threshold = 1.2  # ATR放大20%

    def analyze(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None,
        indicators: Optional[Dict[str, Any]] = None
    ) -> StrategySignal:
        """
        分析市场并生成信号

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列（可选）
            indicators: 预计算的指标值（可选）

        Returns:
            StrategySignal
        """
        if len(closes) < self.lookback_period + 10:
            return self._no_signal("数据不足")

        current_price = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        # 计算或获取指标
        if indicators:
            macd = indicators.get('macd', {})
            atr = indicators.get('atr')
            atr_series = indicators.get('atr_series', [])
            adx = indicators.get('adx')
            plus_di = indicators.get('plus_di')
            minus_di = indicators.get('minus_di')
        else:
            # 计算MACD
            macd_result = self.macd_indicator.calculate(closes)
            macd = {
                'macd': macd_result['macd_line'],
                'signal': macd_result['signal_line'],
                'histogram': macd_result['histogram'],
                'histogram_series': macd_result.get('histogram_series', [])
            }

            # 计算ATR
            atr_result = self.atr_indicator.calculate(highs, lows, closes)
            atr = atr_result['atr']
            atr_series = atr_result['atr_series']

            # 计算ADX
            adx_result = self.adx_indicator.calculate(highs, lows, closes)
            adx = adx_result['adx']
            plus_di = adx_result['plus_di']
            minus_di = adx_result['minus_di']

        # 分析成交量
        volume_ratio = None
        volume_spike = False
        if volumes is not None and len(volumes) > 0:
            vol_result = self.volume_analyzer.analyze(volumes, closes)
            volume_ratio = vol_result['volume_ratio']
            volume_spike = vol_result['is_volume_spike']
            volume_condition = vol_result['volume_condition']
        else:
            volume_condition = VolumeCondition.NORMAL

        # 计算突破参考价位
        lookback_highs = highs[-self.lookback_period-1:-1]
        lookback_lows = lows[-self.lookback_period-1:-1]
        resistance = max(lookback_highs)  # 阻力位
        support = min(lookback_lows)       # 支撑位

        # 检查ATR是否扩大
        atr_expanding = self._check_atr_expanding(atr_series)

        # 检查突破
        breakout_up = self._check_breakout_up(
            current_price, current_high, resistance, atr
        )
        breakout_down = self._check_breakout_down(
            current_price, current_low, support, atr
        )

        # 构建指标值快照
        indicator_values = {
            'macd': macd.get('macd'),
            'macd_histogram': macd.get('histogram'),
            'atr': atr,
            'atr_expanding': atr_expanding,
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'resistance': resistance,
            'support': support,
            'volume_ratio': volume_ratio
        }

        # 检查做多信号
        if breakout_up:
            buy_signals, buy_reasons, buy_strength = self._check_buy_conditions(
                current_price, macd, atr, atr_expanding,
                plus_di, minus_di, volume_ratio, volume_spike, resistance
            )

            if buy_signals >= 2 and buy_strength >= 0.5:
                # 计算止损止盈
                stop_loss = support if support else current_price - (atr * 2)
                take_profit = current_price + (atr * 3) if atr else None

                return self._create_signal(
                    direction=SignalDirection.BUY,
                    strength=buy_strength,
                    reasons=buy_reasons,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicator_values=indicator_values,
                    metadata={
                        'breakout_type': 'resistance',
                        'breakout_level': resistance,
                        'signal_count': buy_signals
                    }
                )

        # 检查做空信号
        if breakout_down:
            sell_signals, sell_reasons, sell_strength = self._check_sell_conditions(
                current_price, macd, atr, atr_expanding,
                plus_di, minus_di, volume_ratio, volume_spike, support
            )

            if sell_signals >= 2 and sell_strength >= 0.5:
                # 计算止损止盈
                stop_loss = resistance if resistance else current_price + (atr * 2)
                take_profit = current_price - (atr * 3) if atr else None

                return self._create_signal(
                    direction=SignalDirection.SELL,
                    strength=sell_strength,
                    reasons=sell_reasons,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicator_values=indicator_values,
                    metadata={
                        'breakout_type': 'support',
                        'breakout_level': support,
                        'signal_count': sell_signals
                    }
                )

        return self._no_signal("未检测到有效突破", indicator_values=indicator_values)

    def _check_atr_expanding(self, atr_series: List[Optional[float]]) -> bool:
        """检查ATR是否正在扩大"""
        valid_atr = [v for v in atr_series if v is not None]
        if len(valid_atr) < 3:
            return False

        current_atr = valid_atr[-1]
        prev_avg = sum(valid_atr[-4:-1]) / 3 if len(valid_atr) >= 4 else valid_atr[-2]

        return current_atr > prev_avg * self.atr_expansion_threshold

    def _check_breakout_up(
        self,
        current_price: float,
        current_high: float,
        resistance: float,
        atr: Optional[float]
    ) -> bool:
        """检查向上突破"""
        if atr is None:
            return current_price > resistance

        # 收盘价突破阻力位，且突破幅度超过ATR的一定比例
        breakout_distance = current_price - resistance
        return (current_price > resistance and
                breakout_distance > atr * self.min_breakout_atr)

    def _check_breakout_down(
        self,
        current_price: float,
        current_low: float,
        support: float,
        atr: Optional[float]
    ) -> bool:
        """检查向下突破"""
        if atr is None:
            return current_price < support

        # 收盘价跌破支撑位，且突破幅度超过ATR的一定比例
        breakout_distance = support - current_price
        return (current_price < support and
                breakout_distance > atr * self.min_breakout_atr)

    def _check_buy_conditions(
        self,
        current_price: float,
        macd: Dict[str, Any],
        atr: Optional[float],
        atr_expanding: bool,
        plus_di: Optional[float],
        minus_di: Optional[float],
        volume_ratio: Optional[float],
        volume_spike: bool,
        resistance: float
    ) -> tuple:
        """
        检查做多条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        # 核心条件：价格突破阻力位
        signals += 1
        strength += 0.25
        reasons.append(f"价格突破阻力位 {resistance:.2f}")

        # 条件2：成交量确认
        if self.volume_confirmation:
            if volume_spike:
                signals += 1
                strength += 0.25
                reasons.append(f"成交量异常放大 (比率: {volume_ratio:.2f})")
            elif volume_ratio is not None and volume_ratio >= self.min_volume_ratio:
                signals += 1
                strength += 0.20
                reasons.append(f"成交量放大确认 (比率: {volume_ratio:.2f})")
            else:
                # 无成交量确认，降低信号强度
                strength -= 0.15
                reasons.append("警告：成交量未放大，可能假突破")

        # 条件3：ATR扩大（波动率增加）
        if atr_expanding:
            signals += 1
            strength += 0.15
            reasons.append("ATR扩大，波动率增加")

        # 条件4：MACD方向确认
        histogram = macd.get('histogram')
        if histogram is not None and histogram > 0:
            signals += 1
            strength += 0.15
            reasons.append(f"MACD柱状图为正 ({histogram:.4f})")

            # 检查MACD是否向上
            hist_series = macd.get('histogram_series', [])
            if len(hist_series) >= 2:
                prev_hist = hist_series[-2]
                if prev_hist is not None and histogram > prev_hist:
                    strength += 0.05
                    reasons.append("MACD动能增强")

        # 条件5：DI方向确认
        if plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                signals += 1
                strength += 0.10
                reasons.append(f"+DI > -DI ({plus_di:.1f} > {minus_di:.1f})")

        return signals, reasons, min(strength, 1.0)

    def _check_sell_conditions(
        self,
        current_price: float,
        macd: Dict[str, Any],
        atr: Optional[float],
        atr_expanding: bool,
        plus_di: Optional[float],
        minus_di: Optional[float],
        volume_ratio: Optional[float],
        volume_spike: bool,
        support: float
    ) -> tuple:
        """
        检查做空条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        # 核心条件：价格跌破支撑位
        signals += 1
        strength += 0.25
        reasons.append(f"价格跌破支撑位 {support:.2f}")

        # 条件2：成交量确认
        if self.volume_confirmation:
            if volume_spike:
                signals += 1
                strength += 0.25
                reasons.append(f"成交量异常放大 (比率: {volume_ratio:.2f})")
            elif volume_ratio is not None and volume_ratio >= self.min_volume_ratio:
                signals += 1
                strength += 0.20
                reasons.append(f"成交量放大确认 (比率: {volume_ratio:.2f})")
            else:
                strength -= 0.15
                reasons.append("警告：成交量未放大，可能假突破")

        # 条件3：ATR扩大
        if atr_expanding:
            signals += 1
            strength += 0.15
            reasons.append("ATR扩大，波动率增加")

        # 条件4：MACD方向确认
        histogram = macd.get('histogram')
        if histogram is not None and histogram < 0:
            signals += 1
            strength += 0.15
            reasons.append(f"MACD柱状图为负 ({histogram:.4f})")

            # 检查MACD是否向下
            hist_series = macd.get('histogram_series', [])
            if len(hist_series) >= 2:
                prev_hist = hist_series[-2]
                if prev_hist is not None and histogram < prev_hist:
                    strength += 0.05
                    reasons.append("MACD动能增强")

        # 条件5：DI方向确认
        if plus_di is not None and minus_di is not None:
            if minus_di > plus_di:
                signals += 1
                strength += 0.10
                reasons.append(f"-DI > +DI ({minus_di:.1f} > {plus_di:.1f})")

        return signals, reasons, min(strength, 1.0)
