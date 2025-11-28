# -*- coding: utf-8 -*-
"""
多周期确认系统

当主周期（如5分钟）产生信号后，通过更高周期（15分钟、1小时）进行确认，
提高信号的可靠性。

确认逻辑：
- 15分钟周期：检查趋势方向、RSI极端值、MACD方向
- 1小时周期：检查大趋势、成交量趋势

权重分配（默认）：
- 5分钟：40%
- 15分钟：35%
- 1小时：25%
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import (
    RSIIndicator,
    MACDIndicator,
    EMAIndicator,
    VolumeAnalyzer
)
from strategy_config import get_multi_timeframe_config
from strategy.strategies.base_strategy import SignalDirection


class ConfirmationResult(Enum):
    """确认结果"""
    CONFIRMED = "confirmed"       # 确认
    REJECTED = "rejected"         # 拒绝
    NEUTRAL = "neutral"           # 中性


@dataclass
class TimeframeConfirmation:
    """单周期确认结果"""
    timeframe: str
    result: ConfirmationResult
    score: float                  # 确认分数 0-1
    reasons: List[str] = field(default_factory=list)
    indicator_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiTimeframeResult:
    """多周期确认综合结果"""
    is_confirmed: bool                                    # 是否确认通过
    final_score: float                                    # 最终综合分数
    confirmation_count: int                               # 确认的周期数量
    rejection_count: int                                  # 拒绝的周期数量
    timeframe_results: Dict[str, TimeframeConfirmation]  # 各周期结果
    reasons: List[str] = field(default_factory=list)     # 综合原因
    adjusted_strength: float = 0.0                        # 调整后的信号强度


class MultiTimeframeConfirmer:
    """
    多周期确认器

    验证主周期信号在更高周期上是否得到支持
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化多周期确认器

        Args:
            config: 配置，如果为None则使用默认配置
        """
        default_config = get_multi_timeframe_config()
        self.config = {**default_config, **(config or {})}

        self.primary_timeframe = self.config.get("primary_timeframe", "5m")
        self.confirmation_timeframes = self.config.get("confirmation_timeframes", ["15m", "1h"])
        self.min_confirmations = self.config.get("min_confirmations", 1)
        self.weights = self.config.get("weights", {"5m": 0.4, "15m": 0.35, "1h": 0.25})
        self.confirmation_rules = self.config.get("confirmation_rules", {})

        # 初始化指标计算器
        self.rsi_indicator = RSIIndicator(period=14)
        self.macd_indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        self.ema_fast = EMAIndicator(period=20)
        self.ema_slow = EMAIndicator(period=60)
        self.volume_analyzer = VolumeAnalyzer(ma_period=20)

    def confirm(
        self,
        signal_direction: SignalDirection,
        primary_strength: float,
        timeframe_data: Dict[str, Dict[str, List[float]]]
    ) -> MultiTimeframeResult:
        """
        执行多周期确认

        Args:
            signal_direction: 主周期信号方向
            primary_strength: 主周期信号强度
            timeframe_data: 各周期的OHLCV数据
                格式: {
                    "5m": {"highs": [...], "lows": [...], "closes": [...], "volumes": [...]},
                    "15m": {...},
                    "1h": {...}
                }

        Returns:
            MultiTimeframeResult 多周期确认结果
        """
        if signal_direction == SignalDirection.HOLD:
            return MultiTimeframeResult(
                is_confirmed=False,
                final_score=0.0,
                confirmation_count=0,
                rejection_count=0,
                timeframe_results={},
                reasons=["无信号，无需确认"]
            )

        timeframe_results = {}
        confirmation_count = 0
        rejection_count = 0
        all_reasons = []

        # 对每个确认周期进行验证
        for tf in self.confirmation_timeframes:
            if tf not in timeframe_data:
                continue

            tf_data = timeframe_data[tf]
            highs = tf_data.get("highs", [])
            lows = tf_data.get("lows", [])
            closes = tf_data.get("closes", [])
            volumes = tf_data.get("volumes", [])

            if len(closes) < 30:
                timeframe_results[tf] = TimeframeConfirmation(
                    timeframe=tf,
                    result=ConfirmationResult.NEUTRAL,
                    score=0.5,
                    reasons=[f"{tf}周期数据不足"]
                )
                continue

            # 执行该周期的确认检查
            confirmation = self._check_timeframe_confirmation(
                tf, signal_direction, highs, lows, closes, volumes
            )
            timeframe_results[tf] = confirmation

            if confirmation.result == ConfirmationResult.CONFIRMED:
                confirmation_count += 1
                all_reasons.append(f"{tf}周期确认: {', '.join(confirmation.reasons)}")
            elif confirmation.result == ConfirmationResult.REJECTED:
                rejection_count += 1
                all_reasons.append(f"{tf}周期拒绝: {', '.join(confirmation.reasons)}")

        # 计算最终分数
        final_score = self._calculate_final_score(
            primary_strength, timeframe_results
        )

        # 判断是否确认通过
        is_confirmed = confirmation_count >= self.min_confirmations

        # 如果有周期明确拒绝，降低确认度
        if rejection_count > 0:
            if rejection_count >= len(self.confirmation_timeframes):
                is_confirmed = False
                final_score *= 0.3
            else:
                final_score *= (1 - 0.2 * rejection_count)

        # 计算调整后的信号强度
        adjusted_strength = primary_strength * final_score

        return MultiTimeframeResult(
            is_confirmed=is_confirmed,
            final_score=final_score,
            confirmation_count=confirmation_count,
            rejection_count=rejection_count,
            timeframe_results=timeframe_results,
            reasons=all_reasons,
            adjusted_strength=adjusted_strength
        )

    def _check_timeframe_confirmation(
        self,
        timeframe: str,
        signal_direction: SignalDirection,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float]
    ) -> TimeframeConfirmation:
        """
        检查单个周期的确认

        Args:
            timeframe: 周期名称
            signal_direction: 信号方向
            highs, lows, closes, volumes: OHLCV数据

        Returns:
            TimeframeConfirmation
        """
        rules = self.confirmation_rules.get(timeframe, {})
        reasons = []
        score = 0.5  # 基础分
        checks_passed = 0
        checks_total = 0

        indicator_values = {}

        # 检查1：趋势方向
        if rules.get("check_trend", True):
            checks_total += 1
            ema20 = self.ema_fast.calculate(closes)['ema']
            ema60 = self.ema_slow.calculate(closes)['ema']
            current_price = closes[-1]

            indicator_values['ema20'] = ema20
            indicator_values['ema60'] = ema60

            if ema20 is not None and ema60 is not None:
                if signal_direction == SignalDirection.BUY:
                    if current_price > ema20 > ema60:
                        checks_passed += 1
                        score += 0.15
                        reasons.append("趋势向上，价格在均线上方")
                    elif current_price > ema60:
                        score += 0.05
                        reasons.append("价格在慢均线上方")
                    else:
                        score -= 0.1
                        reasons.append("趋势不支持做多")
                else:  # SELL
                    if current_price < ema20 < ema60:
                        checks_passed += 1
                        score += 0.15
                        reasons.append("趋势向下，价格在均线下方")
                    elif current_price < ema60:
                        score += 0.05
                        reasons.append("价格在慢均线下方")
                    else:
                        score -= 0.1
                        reasons.append("趋势不支持做空")

        # 检查2：RSI极端值
        if rules.get("check_rsi_extreme", True):
            checks_total += 1
            rsi = self.rsi_indicator.calculate(closes)['rsi']
            indicator_values['rsi'] = rsi

            if rsi is not None:
                if signal_direction == SignalDirection.BUY:
                    if rsi > 75:
                        score -= 0.15
                        reasons.append(f"RSI过高({rsi:.1f})，不宜追多")
                    elif rsi < 30:
                        checks_passed += 1
                        score += 0.10
                        reasons.append(f"RSI超卖({rsi:.1f})，支持做多")
                    else:
                        checks_passed += 1
                        score += 0.05
                        reasons.append(f"RSI正常({rsi:.1f})")
                else:  # SELL
                    if rsi < 25:
                        score -= 0.15
                        reasons.append(f"RSI过低({rsi:.1f})，不宜追空")
                    elif rsi > 70:
                        checks_passed += 1
                        score += 0.10
                        reasons.append(f"RSI超买({rsi:.1f})，支持做空")
                    else:
                        checks_passed += 1
                        score += 0.05
                        reasons.append(f"RSI正常({rsi:.1f})")

        # 检查3：MACD方向
        if rules.get("check_macd", True):
            checks_total += 1
            macd_result = self.macd_indicator.calculate(closes)
            histogram = macd_result['histogram']
            indicator_values['macd_histogram'] = histogram

            if histogram is not None:
                if signal_direction == SignalDirection.BUY:
                    if histogram > 0:
                        checks_passed += 1
                        score += 0.10
                        reasons.append("MACD柱状图为正")
                    else:
                        score -= 0.05
                        reasons.append("MACD柱状图为负")
                else:  # SELL
                    if histogram < 0:
                        checks_passed += 1
                        score += 0.10
                        reasons.append("MACD柱状图为负")
                    else:
                        score -= 0.05
                        reasons.append("MACD柱状图为正")

        # 检查4：成交量趋势
        if rules.get("check_volume_trend", False) and volumes:
            checks_total += 1
            vol_result = self.volume_analyzer.analyze(volumes, closes)
            volume_trend = vol_result.get('volume_trend')
            indicator_values['volume_trend'] = str(volume_trend) if volume_trend else None

            # 成交量趋势分析（简化）
            if len(volumes) >= 5:
                recent_vol = sum(volumes[-3:]) / 3
                older_vol = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else recent_vol

                if recent_vol > older_vol * 1.2:
                    checks_passed += 1
                    score += 0.05
                    reasons.append("成交量放大")
                elif recent_vol < older_vol * 0.7:
                    reasons.append("成交量萎缩")

        # 确定确认结果
        if checks_total > 0:
            pass_rate = checks_passed / checks_total
        else:
            pass_rate = 0.5

        if score >= 0.65 and pass_rate >= 0.5:
            result = ConfirmationResult.CONFIRMED
        elif score < 0.4 or pass_rate < 0.3:
            result = ConfirmationResult.REJECTED
        else:
            result = ConfirmationResult.NEUTRAL

        return TimeframeConfirmation(
            timeframe=timeframe,
            result=result,
            score=min(max(score, 0.0), 1.0),
            reasons=reasons,
            indicator_values=indicator_values
        )

    def _calculate_final_score(
        self,
        primary_strength: float,
        timeframe_results: Dict[str, TimeframeConfirmation]
    ) -> float:
        """
        计算最终综合分数

        Args:
            primary_strength: 主周期信号强度
            timeframe_results: 各周期确认结果

        Returns:
            最终分数 0-1
        """
        # 主周期权重
        primary_weight = self.weights.get(self.primary_timeframe, 0.4)
        total_score = primary_strength * primary_weight

        # 各确认周期的分数
        for tf, confirmation in timeframe_results.items():
            weight = self.weights.get(tf, 0.25)
            total_score += confirmation.score * weight

        # 归一化
        total_weight = primary_weight + sum(
            self.weights.get(tf, 0.25) for tf in timeframe_results.keys()
        )

        if total_weight > 0:
            return total_score / total_weight

        return primary_strength

    def get_confirmation_summary(self, result: MultiTimeframeResult) -> str:
        """
        生成确认结果摘要

        Args:
            result: 多周期确认结果

        Returns:
            摘要字符串
        """
        status = "✓ 确认通过" if result.is_confirmed else "✗ 确认未通过"
        summary = [
            f"多周期确认结果: {status}",
            f"综合分数: {result.final_score:.2f}",
            f"确认周期: {result.confirmation_count}/{len(self.confirmation_timeframes)}",
            f"调整后强度: {result.adjusted_strength:.2f}",
            "",
            "各周期详情:"
        ]

        for tf, conf in result.timeframe_results.items():
            status_symbol = {
                ConfirmationResult.CONFIRMED: "✓",
                ConfirmationResult.REJECTED: "✗",
                ConfirmationResult.NEUTRAL: "○"
            }.get(conf.result, "?")

            summary.append(f"  {tf}: {status_symbol} (分数: {conf.score:.2f})")
            for reason in conf.reasons[:2]:  # 只显示前两个原因
                summary.append(f"    - {reason}")

        return "\n".join(summary)
