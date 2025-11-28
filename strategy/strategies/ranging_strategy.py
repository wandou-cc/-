# -*- coding: utf-8 -*-
"""
震荡策略 (Ranging Strategy)

适用场景：ADX < 20 的震荡市场
核心思路：在区间上下沿反向交易

做多条件：
- 价格触及布林带下轨 (%B < 0.15)
- RSI < 35 (超卖)
- KDJ: K < 25 或 J < 10 或 金叉形成
- (可选) 成交量萎缩，表明抛压衰竭

做空条件：
- 价格触及布林带上轨 (%B > 0.85)
- RSI > 65 (超买)
- KDJ: K > 75 或 J > 90 或 死叉形成
- (可选) 成交量萎缩，表明买盘衰竭
"""

from typing import Dict, Any, Optional, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from indicators import (
    RSIIndicator, RSIAnalyzer,
    KDJIndicator, KDJAnalyzer,
    BollingerBandsIndicator, BollingerBandsAnalyzer,
    ATRIndicator,
    VolumeAnalyzer, VolumeCondition
)
from strategy_config import get_strategy_config

from .base_strategy import BaseStrategy, StrategySignal, SignalDirection


class RangingStrategy(BaseStrategy):
    """
    震荡策略

    在震荡市场中，价格倾向于在一定范围内波动。
    本策略在价格触及区间边界时反向交易。
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化震荡策略

        Args:
            config: 策略配置，如果为None则使用默认配置
        """
        # 从全局配置获取默认值
        default_config = get_strategy_config("ranging") or {}

        # 合并配置
        merged_config = {**default_config, **(config or {})}
        super().__init__(name="ranging", config=merged_config)

        # 初始化指标
        self.rsi_indicator = RSIIndicator(period=14)
        self.kdj_indicator = KDJIndicator(period=9, signal=3)
        self.bb_indicator = BollingerBandsIndicator(period=20, std_dev=2.0)
        self.atr_indicator = ATRIndicator(period=14)
        self.volume_analyzer = VolumeAnalyzer(ma_period=20)

        # 策略参数
        self.bb_lower_threshold = self.get_config_value("bb_lower_threshold", 0.15)
        self.bb_upper_threshold = self.get_config_value("bb_upper_threshold", 0.85)
        self.rsi_oversold = self.get_config_value("rsi_oversold", 35)
        self.rsi_overbought = self.get_config_value("rsi_overbought", 65)
        self.kdj_oversold = self.get_config_value("kdj_oversold", 25)
        self.kdj_overbought = self.get_config_value("kdj_overbought", 75)
        self.j_extreme_low = self.get_config_value("j_extreme_low", 10)
        self.j_extreme_high = self.get_config_value("j_extreme_high", 90)

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
        if len(closes) < 30:
            return self._no_signal("数据不足")

        current_price = closes[-1]

        # 计算或获取指标
        if indicators:
            rsi = indicators.get('rsi')
            kdj = indicators.get('kdj', {})
            bb = indicators.get('bollinger', {})
            atr = indicators.get('atr')
        else:
            # 计算RSI
            rsi_result = self.rsi_indicator.calculate(closes)
            rsi = rsi_result['rsi']

            # 计算KDJ
            kdj_result = self.kdj_indicator.calculate(highs, lows, closes)
            kdj = {
                'k': kdj_result['k'],
                'd': kdj_result['d'],
                'j': kdj_result['j'],
                'k_series': kdj_result.get('k_series', []),
                'd_series': kdj_result.get('d_series', [])
            }

            # 计算布林带
            bb_result = self.bb_indicator.calculate(closes)
            bb = {
                'upper': bb_result['upper_band'],
                'middle': bb_result['middle_band'],
                'lower': bb_result['lower_band'],
                'percent_b': bb_result['percent_b']
            }

            # 计算ATR
            atr_result = self.atr_indicator.calculate(highs, lows, closes)
            atr = atr_result['atr']

        # 分析成交量
        volume_low = False
        volume_ratio = None
        if volumes is not None and len(volumes) > 0:
            vol_result = self.volume_analyzer.analyze(volumes, closes)
            volume_condition = vol_result['volume_condition']
            volume_ratio = vol_result.get('volume_ratio')
            volume_low = volume_condition in [VolumeCondition.LOW, VolumeCondition.VERY_LOW]

        # 检查信号条件
        buy_signals, buy_reasons, buy_strength = self._check_buy_conditions(
            rsi, kdj, bb, volume_low
        )
        sell_signals, sell_reasons, sell_strength = self._check_sell_conditions(
            rsi, kdj, bb, volume_low
        )

        # 构建指标值快照
        indicator_values = {
            'rsi': rsi,
            'kdj_k': kdj.get('k'),
            'kdj_d': kdj.get('d'),
            'kdj_j': kdj.get('j'),
            'bb_percent_b': bb.get('percent_b'),
            'bb_upper': bb.get('upper'),
            'bb_lower': bb.get('lower'),
            'bb_middle': bb.get('middle'),
            'atr': atr,
            'volume_ratio': volume_ratio
        }

        # 决定最终信号
        if buy_signals >= 2 and buy_strength > sell_strength:
            # 计算止损止盈
            stop_loss = current_price - (atr * 2) if atr else None
            take_profit = bb.get('middle') if bb.get('middle') else None

            return self._create_signal(
                direction=SignalDirection.BUY,
                strength=buy_strength,
                reasons=buy_reasons,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicator_values=indicator_values,
                metadata={'buy_signals': buy_signals, 'sell_signals': sell_signals}
            )

        elif sell_signals >= 2 and sell_strength > buy_strength:
            # 计算止损止盈
            stop_loss = current_price + (atr * 2) if atr else None
            take_profit = bb.get('middle') if bb.get('middle') else None

            return self._create_signal(
                direction=SignalDirection.SELL,
                strength=sell_strength,
                reasons=sell_reasons,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicator_values=indicator_values,
                metadata={'buy_signals': buy_signals, 'sell_signals': sell_signals}
            )

        return self._no_signal("未满足震荡策略条件", indicator_values=indicator_values)

    def _check_buy_conditions(
        self,
        rsi: Optional[float],
        kdj: Dict[str, Any],
        bb: Dict[str, Any],
        volume_low: bool
    ) -> tuple:
        """
        检查做多条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        percent_b = bb.get('percent_b')
        k = kdj.get('k')
        d = kdj.get('d')
        j = kdj.get('j')

        # 条件1：布林带下轨
        if percent_b is not None:
            if percent_b < 0:
                signals += 1
                strength += 0.35
                reasons.append(f"价格跌破布林带下轨 (%B={percent_b:.2f})")
            elif percent_b < self.bb_lower_threshold:
                signals += 1
                strength += 0.25
                reasons.append(f"价格接近布林带下轨 (%B={percent_b:.2f})")

        # 条件2：RSI超卖
        if rsi is not None:
            if rsi < 20:
                signals += 1
                strength += 0.30
                reasons.append(f"RSI极度超卖 ({rsi:.1f})")
            elif rsi < self.rsi_oversold:
                signals += 1
                strength += 0.20
                reasons.append(f"RSI超卖 ({rsi:.1f})")

        # 条件3：KDJ信号
        if k is not None and d is not None:
            # J值极低
            if j is not None and j < self.j_extreme_low:
                signals += 1
                strength += 0.25
                reasons.append(f"KDJ J值极低 ({j:.1f})")
            # K值超卖
            elif k < self.kdj_oversold:
                signals += 1
                strength += 0.15
                reasons.append(f"KDJ K值超卖 ({k:.1f})")

            # 检查金叉
            k_series = kdj.get('k_series', [])
            d_series = kdj.get('d_series', [])
            if len(k_series) >= 2 and len(d_series) >= 2:
                prev_k = k_series[-2] if k_series[-2] is not None else k
                prev_d = d_series[-2] if d_series[-2] is not None else d
                if prev_k is not None and prev_d is not None:
                    if prev_k < prev_d and k > d:
                        signals += 1
                        strength += 0.20
                        reasons.append("KDJ金叉形成")

        # 加分条件：成交量萎缩
        if volume_low:
            strength += 0.10
            reasons.append("成交量萎缩（抛压减弱）")

        return signals, reasons, min(strength, 1.0)

    def _check_sell_conditions(
        self,
        rsi: Optional[float],
        kdj: Dict[str, Any],
        bb: Dict[str, Any],
        volume_low: bool
    ) -> tuple:
        """
        检查做空条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        percent_b = bb.get('percent_b')
        k = kdj.get('k')
        d = kdj.get('d')
        j = kdj.get('j')

        # 条件1：布林带上轨
        if percent_b is not None:
            if percent_b > 1:
                signals += 1
                strength += 0.35
                reasons.append(f"价格突破布林带上轨 (%B={percent_b:.2f})")
            elif percent_b > self.bb_upper_threshold:
                signals += 1
                strength += 0.25
                reasons.append(f"价格接近布林带上轨 (%B={percent_b:.2f})")

        # 条件2：RSI超买
        if rsi is not None:
            if rsi > 80:
                signals += 1
                strength += 0.30
                reasons.append(f"RSI极度超买 ({rsi:.1f})")
            elif rsi > self.rsi_overbought:
                signals += 1
                strength += 0.20
                reasons.append(f"RSI超买 ({rsi:.1f})")

        # 条件3：KDJ信号
        if k is not None and d is not None:
            # J值极高
            if j is not None and j > self.j_extreme_high:
                signals += 1
                strength += 0.25
                reasons.append(f"KDJ J值极高 ({j:.1f})")
            # K值超买
            elif k > self.kdj_overbought:
                signals += 1
                strength += 0.15
                reasons.append(f"KDJ K值超买 ({k:.1f})")

            # 检查死叉
            k_series = kdj.get('k_series', [])
            d_series = kdj.get('d_series', [])
            if len(k_series) >= 2 and len(d_series) >= 2:
                prev_k = k_series[-2] if k_series[-2] is not None else k
                prev_d = d_series[-2] if d_series[-2] is not None else d
                if prev_k is not None and prev_d is not None:
                    if prev_k > prev_d and k < d:
                        signals += 1
                        strength += 0.20
                        reasons.append("KDJ死叉形成")

        # 加分条件：成交量萎缩
        if volume_low:
            strength += 0.10
            reasons.append("成交量萎缩（买盘减弱）")

        return signals, reasons, min(strength, 1.0)
