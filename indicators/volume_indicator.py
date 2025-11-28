# -*- coding: utf-8 -*-
"""
成交量分析指标实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用

成交量分析关注点：
1. 放量突破 → 真突破概率高
2. 缩量回调 → 趋势健康，回调入场机会
3. 放量滞涨 → 顶部信号
4. 放量不跌 → 底部信号
5. 量价背离 → 趋势可能反转
"""

from typing import List, Dict, Any, Optional
from enum import Enum


class VolumeCondition(Enum):
    """成交量状态枚举"""
    SPIKE = "spike"              # 异常放量 (>= 2倍均量)
    HIGH = "high"                # 放量 (>= 1.5倍均量)
    NORMAL = "normal"            # 正常
    LOW = "low"                  # 缩量 (<= 0.7倍均量)
    VERY_LOW = "very_low"        # 极度缩量 (<= 0.5倍均量)


class VolumeTrend(Enum):
    """成交量趋势枚举"""
    INCREASING = "increasing"    # 连续放量
    DECREASING = "decreasing"    # 连续缩量
    STABLE = "stable"            # 稳定


class PriceVolumeDivergence(Enum):
    """量价背离类型"""
    BULLISH = "bullish"          # 看涨背离（价格下跌但成交量萎缩）
    BEARISH = "bearish"          # 看跌背离（价格上涨但成交量萎缩）
    NONE = "none"                # 无背离


class VolumeIndicator:
    """
    成交量指标计算类（无状态版本）

    计算指标：
    1. 成交量移动平均线 (Volume MA)
    2. 成交量比率 (Volume Ratio = 当前成交量 / MA)
    3. 成交量变化率
    """

    def __init__(self, ma_period: int = 20):
        """
        初始化成交量指标参数

        Args:
            ma_period: 成交量均线周期，默认20
        """
        self.ma_period = ma_period

    def _calculate_sma(self, values: List[float], period: int) -> List[Optional[float]]:
        """
        计算简单移动平均

        Args:
            values: 数据序列
            period: 周期

        Returns:
            SMA序列
        """
        n = len(values)
        result = [None] * n

        if n < period:
            return result

        for i in range(period - 1, n):
            window = values[i - period + 1:i + 1]
            result[i] = sum(window) / period

        return result

    def calculate(self, volumes: List[float]) -> Dict[str, Any]:
        """
        计算成交量指标（无状态，每次完整重算）

        Args:
            volumes: 成交量序列

        Returns:
            包含成交量MA、成交量比率等的字典
        """
        n = len(volumes)
        if n == 0:
            return {
                'volume': None,
                'volume_ma': None,
                'volume_ratio': None,
                'volume_change': None,
                'volume_series': [],
                'volume_ma_series': [],
                'volume_ratio_series': []
            }

        # 计算成交量MA
        volume_ma_series = self._calculate_sma(volumes, self.ma_period)

        # 计算成交量比率 (当前成交量 / MA)
        volume_ratio_series = [None] * n
        for i in range(n):
            if volume_ma_series[i] is not None and volume_ma_series[i] > 0:
                volume_ratio_series[i] = volumes[i] / volume_ma_series[i]

        # 计算成交量变化率
        volume_change = None
        if n >= 2 and volumes[-2] > 0:
            volume_change = (volumes[-1] - volumes[-2]) / volumes[-2]

        return {
            'volume': volumes[-1] if volumes else None,
            'volume_ma': volume_ma_series[-1] if volume_ma_series else None,
            'volume_ratio': volume_ratio_series[-1] if volume_ratio_series else None,
            'volume_change': volume_change,
            'volume_series': volumes,
            'volume_ma_series': volume_ma_series,
            'volume_ratio_series': volume_ratio_series
        }

    def calculate_latest(self, volumes: List[float]) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的成交量指标值

        Args:
            volumes: 成交量序列

        Returns:
            包含最新成交量指标的字典
        """
        result = self.calculate(volumes)
        return {
            'volume': result['volume'],
            'volume_ma': result['volume_ma'],
            'volume_ratio': result['volume_ratio'],
            'volume_change': result['volume_change']
        }

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {'ma_period': self.ma_period}

    def set_parameters(self, ma_period: int = None):
        """更新参数设置"""
        if ma_period is not None:
            self.ma_period = ma_period


class VolumeAnalyzer:
    """
    成交量分析器（无状态版本），提供量价关系分析
    """

    def __init__(
        self,
        ma_period: int = 20,
        spike_threshold: float = 2.0,
        high_threshold: float = 1.5,
        low_threshold: float = 0.7,
        very_low_threshold: float = 0.5,
        trend_lookback: int = 3
    ):
        """
        初始化成交量分析器

        Args:
            ma_period: 成交量均线周期
            spike_threshold: 异常放量阈值（倍数）
            high_threshold: 放量阈值
            low_threshold: 缩量阈值
            very_low_threshold: 极度缩量阈值
            trend_lookback: 成交量趋势回看周期
        """
        self.indicator = VolumeIndicator(ma_period)
        self.spike_threshold = spike_threshold
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.very_low_threshold = very_low_threshold
        self.trend_lookback = trend_lookback

    def analyze(
        self,
        volumes: List[float],
        closes: Optional[List[float]] = None,
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        综合分析成交量

        Args:
            volumes: 成交量序列
            closes: 收盘价序列（用于量价背离分析）
            highs: 最高价序列（可选）
            lows: 最低价序列（可选）

        Returns:
            包含成交量状态、趋势、量价背离等的综合分析字典
        """
        result = self.indicator.calculate(volumes)

        volume_ratio = result['volume_ratio']
        volume_ratio_series = result['volume_ratio_series']

        # 判断成交量状态
        volume_condition = self._get_volume_condition(volume_ratio)

        # 判断成交量趋势
        volume_trend = self._get_volume_trend(volume_ratio_series)

        # 检测异常放量
        is_volume_spike = volume_ratio is not None and volume_ratio >= self.spike_threshold

        # 量价背离分析
        divergence = PriceVolumeDivergence.NONE
        if closes is not None and len(closes) >= 5:
            divergence = self._detect_divergence(closes, volumes)

        # 量价关系判断
        price_volume_relation = None
        if closes is not None and len(closes) >= 2:
            price_volume_relation = self._analyze_price_volume_relation(
                closes[-2], closes[-1],
                volumes[-2], volumes[-1],
                volume_ratio
            )

        return {
            'volume': result['volume'],
            'volume_ma': result['volume_ma'],
            'volume_ratio': volume_ratio,
            'volume_change': result['volume_change'],
            'volume_condition': volume_condition,
            'volume_trend': volume_trend,
            'is_volume_spike': is_volume_spike,
            'divergence': divergence,
            'price_volume_relation': price_volume_relation,
            'volume_ma_series': result['volume_ma_series'],
            'volume_ratio_series': volume_ratio_series
        }

    def _get_volume_condition(self, volume_ratio: Optional[float]) -> VolumeCondition:
        """根据成交量比率判断成交量状态"""
        if volume_ratio is None:
            return VolumeCondition.NORMAL

        if volume_ratio >= self.spike_threshold:
            return VolumeCondition.SPIKE
        elif volume_ratio >= self.high_threshold:
            return VolumeCondition.HIGH
        elif volume_ratio <= self.very_low_threshold:
            return VolumeCondition.VERY_LOW
        elif volume_ratio <= self.low_threshold:
            return VolumeCondition.LOW
        else:
            return VolumeCondition.NORMAL

    def _get_volume_trend(self, volume_ratio_series: List[Optional[float]]) -> VolumeTrend:
        """判断成交量趋势"""
        # 获取最近N个有效的成交量比率
        valid_ratios = [r for r in volume_ratio_series[-self.trend_lookback:] if r is not None]

        if len(valid_ratios) < 2:
            return VolumeTrend.STABLE

        # 判断是否连续增加或减少
        increasing = all(valid_ratios[i] < valid_ratios[i + 1] for i in range(len(valid_ratios) - 1))
        decreasing = all(valid_ratios[i] > valid_ratios[i + 1] for i in range(len(valid_ratios) - 1))

        if increasing:
            return VolumeTrend.INCREASING
        elif decreasing:
            return VolumeTrend.DECREASING
        else:
            return VolumeTrend.STABLE

    def _detect_divergence(
        self,
        closes: List[float],
        volumes: List[float]
    ) -> PriceVolumeDivergence:
        """
        检测量价背离

        看涨背离：价格创新低，但成交量萎缩（抛压减弱）
        看跌背离：价格创新高，但成交量萎缩（买盘不足）
        """
        if len(closes) < 5 or len(volumes) < 5:
            return PriceVolumeDivergence.NONE

        # 比较最近的价格和成交量趋势
        recent_closes = closes[-5:]
        recent_volumes = volumes[-5:]

        price_change = (recent_closes[-1] - recent_closes[0]) / recent_closes[0]
        volume_change = (sum(recent_volumes[-2:]) / 2) / (sum(recent_volumes[:2]) / 2) - 1

        # 看跌背离：价格上涨但成交量萎缩
        if price_change > 0.01 and volume_change < -0.2:
            return PriceVolumeDivergence.BEARISH

        # 看涨背离：价格下跌但成交量萎缩
        if price_change < -0.01 and volume_change < -0.2:
            return PriceVolumeDivergence.BULLISH

        return PriceVolumeDivergence.NONE

    def _analyze_price_volume_relation(
        self,
        prev_close: float,
        current_close: float,
        prev_volume: float,
        current_volume: float,
        volume_ratio: Optional[float]
    ) -> Dict[str, Any]:
        """
        分析量价关系

        Returns:
            包含量价关系描述和信号的字典
        """
        price_up = current_close > prev_close
        price_down = current_close < prev_close
        volume_up = current_volume > prev_volume
        is_high_volume = volume_ratio is not None and volume_ratio >= self.high_threshold
        is_low_volume = volume_ratio is not None and volume_ratio <= self.low_threshold

        relation = {
            'description': '',
            'signal': 'neutral',
            'signal_strength': 0.0
        }

        if price_up and volume_up and is_high_volume:
            relation['description'] = '放量上涨'
            relation['signal'] = 'bullish'
            relation['signal_strength'] = 0.8
        elif price_up and is_low_volume:
            relation['description'] = '缩量上涨（量价背离警告）'
            relation['signal'] = 'bearish_warning'
            relation['signal_strength'] = 0.3
        elif price_down and volume_up and is_high_volume:
            relation['description'] = '放量下跌'
            relation['signal'] = 'bearish'
            relation['signal_strength'] = 0.8
        elif price_down and is_low_volume:
            relation['description'] = '缩量下跌（抛压减弱）'
            relation['signal'] = 'bullish_hint'
            relation['signal_strength'] = 0.3
        elif not price_up and not price_down and is_high_volume:
            relation['description'] = '放量滞涨/滞跌'
            relation['signal'] = 'reversal_warning'
            relation['signal_strength'] = 0.5
        else:
            relation['description'] = '量价正常'
            relation['signal'] = 'neutral'
            relation['signal_strength'] = 0.0

        return relation

    def get_volume_condition(self, volumes: List[float]) -> VolumeCondition:
        """快捷方法：获取成交量状态"""
        return self.analyze(volumes)['volume_condition']

    def is_volume_spike(self, volumes: List[float]) -> bool:
        """快捷方法：判断是否异常放量"""
        return self.analyze(volumes)['is_volume_spike']

    def supports_breakout(
        self,
        volumes: List[float],
        closes: List[float],
        breakout_direction: str = 'up'
    ) -> bool:
        """
        判断成交量是否支持突破

        Args:
            volumes: 成交量序列
            closes: 收盘价序列
            breakout_direction: 突破方向 ('up' 或 'down')

        Returns:
            True: 成交量支持突破, False: 不支持
        """
        analysis = self.analyze(volumes, closes)

        # 突破需要放量确认
        if analysis['volume_condition'] not in [VolumeCondition.HIGH, VolumeCondition.SPIKE]:
            return False

        # 检查量价关系
        pv_relation = analysis['price_volume_relation']
        if pv_relation is None:
            return False

        if breakout_direction == 'up':
            return pv_relation['signal'] == 'bullish'
        else:
            return pv_relation['signal'] == 'bearish'

    def supports_pullback_entry(
        self,
        volumes: List[float],
        closes: List[float],
        trend_direction: str = 'up'
    ) -> bool:
        """
        判断成交量是否支持回调入场

        Args:
            volumes: 成交量序列
            closes: 收盘价序列
            trend_direction: 主趋势方向 ('up' 或 'down')

        Returns:
            True: 成交量支持回调入场, False: 不支持
        """
        analysis = self.analyze(volumes, closes)

        # 回调入场需要缩量
        if analysis['volume_condition'] not in [VolumeCondition.LOW, VolumeCondition.VERY_LOW]:
            return False

        # 上升趋势中，缩量回调是健康的
        if trend_direction == 'up':
            return analysis['price_volume_relation']['signal'] in ['bullish_hint', 'neutral']

        # 下降趋势中，缩量反弹也是健康的（可以做空）
        return analysis['price_volume_relation']['signal'] in ['bearish_warning', 'neutral']
