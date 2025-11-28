# -*- coding: utf-8 -*-
"""
趋势策略 (Trending Strategy)

适用场景：ADX 20-40 的趋势市场
核心思路：顺势回调入场

做多条件（上升趋势中）：
- EMA排列: EMA5 > EMA20 > EMA60
- ���格回调至 EMA20 附近 (距离 < 1.5%)
- MACD: 柱状图 > 0 或 即将金叉
- RSI: 40 < RSI < 70 (健康区间)
- (加分) 回调时成交量萎缩，反弹时放量

做空条件（下降趋势中）：
- EMA排列: EMA5 < EMA20 < EMA60
- 价格反弹至 EMA20 附近 (距离 < 1.5%)
- MACD: 柱状图 < 0 或 即将死叉
- RSI: 30 < RSI < 60 (健康区间)
- (加分) 反弹时成交量萎缩，下跌时放量
"""

from typing import Dict, Any, Optional, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from indicators import (
    RSIIndicator,
    MACDIndicator,
    EMAIndicator,
    ATRIndicator,
    VolumeAnalyzer, VolumeCondition
)
from strategy_config import get_strategy_config

from .base_strategy import BaseStrategy, StrategySignal, SignalDirection


class TrendingStrategy(BaseStrategy):
    """
    趋势策略

    在趋势市场中，价格沿主趋势方向运动。
    本策略在价格回调到关键支撑位时顺势入场。
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化趋势策略

        Args:
            config: 策略配置，如果为None则使用默认配置
        """
        # 从全局配置获取默认值
        default_config = get_strategy_config("trending") or {}

        # 合并配置
        merged_config = {**default_config, **(config or {})}
        super().__init__(name="trending", config=merged_config)

        # 初始化指标
        self.rsi_indicator = RSIIndicator(period=14)
        self.macd_indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        self.ema_fast = EMAIndicator(period=5)
        self.ema_medium = EMAIndicator(period=20)
        self.ema_slow = EMAIndicator(period=60)
        self.atr_indicator = ATRIndicator(period=14)
        self.volume_analyzer = VolumeAnalyzer(ma_period=20)

        # 策略参数
        self.ema_pullback_threshold = self.get_config_value("ema_pullback_threshold", 0.015)
        self.rsi_healthy_low = self.get_config_value("rsi_healthy_low", 40)
        self.rsi_healthy_high = self.get_config_value("rsi_healthy_high", 70)
        self.macd_confirmation = self.get_config_value("macd_confirmation", True)

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
        if len(closes) < 60:
            return self._no_signal("数据不足（需要至少60根K线）")

        current_price = closes[-1]

        # 计算或获取指标
        if indicators:
            rsi = indicators.get('rsi')
            macd = indicators.get('macd', {})
            ema5 = indicators.get('ema5')
            ema20 = indicators.get('ema20')
            ema60 = indicators.get('ema60')
            atr = indicators.get('atr')
        else:
            # 计算RSI
            rsi_result = self.rsi_indicator.calculate(closes)
            rsi = rsi_result['rsi']

            # 计算MACD
            macd_result = self.macd_indicator.calculate(closes)
            macd = {
                'macd': macd_result['macd_line'],
                'signal': macd_result['signal_line'],
                'histogram': macd_result['histogram'],
                'macd_series': macd_result.get('macd_series', []),
                'signal_series': macd_result.get('signal_series', []),
                'histogram_series': macd_result.get('histogram_series', [])
            }

            # 计算EMA
            ema5_result = self.ema_fast.calculate(closes)
            ema20_result = self.ema_medium.calculate(closes)
            ema60_result = self.ema_slow.calculate(closes)

            ema5 = ema5_result['ema']
            ema20 = ema20_result['ema']
            ema60 = ema60_result['ema']

            # 计算ATR
            atr_result = self.atr_indicator.calculate(highs, lows, closes)
            atr = atr_result['atr']

        # 分析成交量
        volume_condition = VolumeCondition.NORMAL
        volume_ratio = None
        if volumes is not None and len(volumes) > 0:
            vol_result = self.volume_analyzer.analyze(volumes, closes)
            volume_condition = vol_result['volume_condition']
            volume_ratio = vol_result.get('volume_ratio')

        # 构建指标值快照（提前计算，确保所有路径都能返回）
        indicator_values = {
            'rsi': rsi,
            'macd': macd.get('macd'),
            'macd_signal': macd.get('signal'),
            'macd_histogram': macd.get('histogram'),
            'ema5': ema5,
            'ema20': ema20,
            'ema60': ema60,
            'atr': atr,
            'volume_ratio': volume_ratio,
            'trend_direction': None
        }

        # 判断趋势方向
        trend_direction = self._determine_trend(ema5, ema20, ema60, current_price)
        indicator_values['trend_direction'] = trend_direction

        if trend_direction == 'none':
            return self._no_signal("无明确趋势方向", indicator_values=indicator_values)

        # 检查信号条件
        if trend_direction == 'up':
            signal_result = self._check_buy_conditions(
                current_price, rsi, macd, ema5, ema20, ema60, volume_condition
            )
        else:
            signal_result = self._check_sell_conditions(
                current_price, rsi, macd, ema5, ema20, ema60, volume_condition
            )

        signals, reasons, strength = signal_result

        # 决定最终信号（提高阈值：需要至少3个信号且强度>=0.5）
        if signals >= 3 and strength >= 0.5:
            direction = SignalDirection.BUY if trend_direction == 'up' else SignalDirection.SELL

            # 计算止损止盈
            if direction == SignalDirection.BUY:
                stop_loss = current_price - (atr * 2) if atr else ema60
                take_profit = current_price + (atr * 3) if atr else None
            else:
                stop_loss = current_price + (atr * 2) if atr else ema60
                take_profit = current_price - (atr * 3) if atr else None

            return self._create_signal(
                direction=direction,
                strength=strength,
                reasons=reasons,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicator_values=indicator_values,
                metadata={
                    'trend_direction': trend_direction,
                    'signal_count': signals
                }
            )

        return self._no_signal("未满足趋势策略条件", indicator_values=indicator_values)

    def _determine_trend(
        self,
        ema5: Optional[float],
        ema20: Optional[float],
        ema60: Optional[float],
        current_price: float
    ) -> str:
        """
        判断趋势方向

        Returns:
            'up': 上升趋势
            'down': 下降趋势
            'none': 无明确趋势
        """
        if ema5 is None or ema20 is None or ema60 is None:
            return 'none'

        # 完美多头排列
        if ema5 > ema20 > ema60:
            return 'up'

        # 完美空头排列
        if ema5 < ema20 < ema60:
            return 'down'

        # 部分排列也算趋势
        if ema5 > ema20 and current_price > ema60:
            return 'up'
        if ema5 < ema20 and current_price < ema60:
            return 'down'

        return 'none'

    def _check_buy_conditions(
        self,
        current_price: float,
        rsi: Optional[float],
        macd: Dict[str, Any],
        ema5: float,
        ema20: float,
        ema60: float,
        volume_condition: VolumeCondition
    ) -> tuple:
        """
        检查做多条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        # 条件1：EMA多头排列
        if ema5 > ema20 > ema60:
            signals += 1
            strength += 0.25
            reasons.append(f"EMA完美多头排列 (EMA5={ema5:.2f} > EMA20={ema20:.2f} > EMA60={ema60:.2f})")
        elif ema5 > ema20:
            strength += 0.15
            reasons.append(f"EMA部分多头排列 (EMA5 > EMA20)")

        # 条件2：价格回调至EMA20附近
        if ema20 > 0:
            distance_to_ema20 = abs(current_price - ema20) / ema20
            if distance_to_ema20 <= self.ema_pullback_threshold:
                signals += 1
                strength += 0.25
                reasons.append(f"价格回调至EMA20附近 (距离{distance_to_ema20*100:.1f}%)")
            elif distance_to_ema20 <= self.ema_pullback_threshold * 2:
                strength += 0.10
                reasons.append(f"价格接近EMA20 (距离{distance_to_ema20*100:.1f}%)")

        # 条件3：RSI在健康区间
        if rsi is not None:
            if self.rsi_healthy_low < rsi < self.rsi_healthy_high:
                signals += 1
                strength += 0.20
                reasons.append(f"RSI在健康区间 ({rsi:.1f})")
            elif rsi < self.rsi_healthy_low:
                strength += 0.10
                reasons.append(f"RSI偏低但可接受 ({rsi:.1f})")

        # 条件4：MACD确认
        if self.macd_confirmation:
            histogram = macd.get('histogram')
            macd_line = macd.get('macd')
            signal_line = macd.get('signal')

            if histogram is not None:
                if histogram > 0:
                    signals += 1
                    strength += 0.20
                    reasons.append(f"MACD柱状图为正 ({histogram:.4f})")
                else:
                    # 检查是否即将金叉
                    hist_series = macd.get('histogram_series', [])
                    if len(hist_series) >= 2:
                        prev_hist = hist_series[-2]
                        if prev_hist is not None and histogram > prev_hist:
                            strength += 0.10
                            reasons.append("MACD柱状图收敛（可能金叉）")

        # 加分条件：回调时成交量萎缩
        if volume_condition in [VolumeCondition.LOW, VolumeCondition.VERY_LOW]:
            strength += 0.10
            reasons.append("成交量萎缩（健康回调）")

        return signals, reasons, min(strength, 1.0)

    def _check_sell_conditions(
        self,
        current_price: float,
        rsi: Optional[float],
        macd: Dict[str, Any],
        ema5: float,
        ema20: float,
        ema60: float,
        volume_condition: VolumeCondition
    ) -> tuple:
        """
        检查做空条件

        Returns:
            (信号数量, 原因列表, 综合强度)
        """
        signals = 0
        reasons = []
        strength = 0.0

        # 条件1：EMA空头排列
        if ema5 < ema20 < ema60:
            signals += 1
            strength += 0.25
            reasons.append(f"EMA完美空头排列 (EMA5={ema5:.2f} < EMA20={ema20:.2f} < EMA60={ema60:.2f})")
        elif ema5 < ema20:
            strength += 0.15
            reasons.append(f"EMA部分空头排列 (EMA5 < EMA20)")

        # 条件2：价格反弹至EMA20附近
        if ema20 > 0:
            distance_to_ema20 = abs(current_price - ema20) / ema20
            if distance_to_ema20 <= self.ema_pullback_threshold:
                signals += 1
                strength += 0.25
                reasons.append(f"价格反弹至EMA20附近 (距离{distance_to_ema20*100:.1f}%)")
            elif distance_to_ema20 <= self.ema_pullback_threshold * 2:
                strength += 0.10
                reasons.append(f"价格接近EMA20 (距离{distance_to_ema20*100:.1f}%)")

        # 条件3：RSI在健康区间
        rsi_sell_low = 30
        rsi_sell_high = 60
        if rsi is not None:
            if rsi_sell_low < rsi < rsi_sell_high:
                signals += 1
                strength += 0.20
                reasons.append(f"RSI在健康区间 ({rsi:.1f})")
            elif rsi > rsi_sell_high:
                strength += 0.10
                reasons.append(f"RSI偏高但可接受 ({rsi:.1f})")

        # 条件4：MACD确认
        if self.macd_confirmation:
            histogram = macd.get('histogram')

            if histogram is not None:
                if histogram < 0:
                    signals += 1
                    strength += 0.20
                    reasons.append(f"MACD柱状图为负 ({histogram:.4f})")
                else:
                    # 检查是否即将死叉
                    hist_series = macd.get('histogram_series', [])
                    if len(hist_series) >= 2:
                        prev_hist = hist_series[-2]
                        if prev_hist is not None and histogram < prev_hist:
                            strength += 0.10
                            reasons.append("MACD柱状图收敛（可能死叉）")

        # 加分条件：反弹时成交量萎缩
        if volume_condition in [VolumeCondition.LOW, VolumeCondition.VERY_LOW]:
            strength += 0.10
            reasons.append("成交量萎缩（健康反弹）")

        return signals, reasons, min(strength, 1.0)
