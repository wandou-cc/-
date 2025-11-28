# -*- coding: utf-8 -*-
"""
EMA四线交叉系统实现 - 无状态版本
适用于实时 WebSocket 推送，可重复计算、无副作用
"""

from typing import List, Dict, Any, Optional
import numpy as np


def _ema(prices: List[float], period: int) -> List[float]:
    """
    计算EMA序列（内部函数）

    Args:
        prices: 价格序列
        period: EMA周期

    Returns:
        EMA值序列
    """
    if not prices or len(prices) < period:
        return []

    alpha = 2.0 / (period + 1)
    ema_values = []

    # 使用前period个数据的SMA作为初始EMA
    ema = sum(prices[:period]) / period

    for i in range(len(prices)):
        if i < period - 1:
            # 数据不足period时，使用累积均值
            ema_values.append(sum(prices[:i + 1]) / (i + 1))
        elif i == period - 1:
            ema_values.append(ema)
        else:
            ema = alpha * prices[i] + (1 - alpha) * ema
            ema_values.append(ema)

    return ema_values


def _ema_latest(prices: List[float], period: int) -> Optional[float]:
    """
    计算最新的EMA值（内部函数）

    Args:
        prices: 价格序列
        period: EMA周期

    Returns:
        最新的EMA值
    """
    if len(prices) < period:
        return None

    alpha = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period

    for i in range(period, len(prices)):
        ema = alpha * prices[i] + (1 - alpha) * ema

    return ema


class EMAIndicator:
    """
    EMA（指数移动平均线）计算类（无状态版本）

    EMA计算公式：
    EMA = α × 当前价格 + (1-α) × 前一期EMA
    其中 α = 2 / (period + 1)
    """

    def __init__(self, period: int = 9):
        """
        初始化EMA指标参数

        Args:
            period: EMA周期
        """
        self.period = period

    def calculate(self, prices: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算EMA（无状态，每次完整重算）

        Args:
            prices: 价格序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含EMA值和完整序列的字典
        """
        if reverse:
            prices = list(reversed(prices))

        if len(prices) < self.period:
            return {
                'ema': None,
                'ema_series': []
            }

        ema_values = _ema(prices, self.period)

        if reverse:
            ema_values = list(reversed(ema_values))

        return {
            'ema': ema_values[-1] if ema_values else None,
            'ema_series': ema_values
        }

    def calculate_latest(self, prices: List[float]) -> Optional[float]:
        """
        快捷方法：只返回最新的EMA值

        Args:
            prices: 价格序列

        Returns:
            最新的EMA值
        """
        return _ema_latest(prices, self.period)

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {'period': self.period}

    def set_parameters(self, period: int = None):
        """更新参数设置"""
        if period is not None:
            self.period = period


class EMAFourLineSystem:
    """
    EMA四线交叉系统（无状态版本）

    使用四条EMA线构建完整的趋势判断体系：
    - 超快速EMA（ultra_fast）：最灵敏，适合短线
    - 快速EMA（fast）：捕捉短期趋势
    - 中速EMA（medium）：判断中期趋势
    - 慢速EMA（slow）：确定长期趋势

    经典配置：
    - 短线：5, 10, 20, 60
    - 中线：7, 25, 99, 200
    - 长线：10, 30, 60, 120
    """

    def __init__(self,
                 ultra_fast_period: int = 5,
                 fast_period: int = 10,
                 medium_period: int = 20,
                 slow_period: int = 60):
        """
        初始化EMA四线系统

        Args:
            ultra_fast_period: 超快速EMA周期，默认5
            fast_period: 快速EMA周期，默认10
            medium_period: 中速EMA周期，默认20
            slow_period: 慢速EMA周期，默认60
        """
        self.ultra_fast_period = ultra_fast_period
        self.fast_period = fast_period
        self.medium_period = medium_period
        self.slow_period = slow_period

    def calculate(self, prices: List[float], reverse: bool = False) -> Dict[str, Any]:
        """
        计算EMA四线系统（无状态，每次完整重算）

        Args:
            prices: 价格序列
            reverse: 是否为倒序数据（最新在前）

        Returns:
            包含四条EMA的字典
        """
        if reverse:
            prices = list(reversed(prices))

        if len(prices) < self.slow_period:
            return {
                'ema_ultra_fast': None,
                'ema_fast': None,
                'ema_medium': None,
                'ema_slow': None,
                'ema_ultra_fast_series': [],
                'ema_fast_series': [],
                'ema_medium_series': [],
                'ema_slow_series': []
            }

        ultra_fast_values = _ema(prices, self.ultra_fast_period)
        fast_values = _ema(prices, self.fast_period)
        medium_values = _ema(prices, self.medium_period)
        slow_values = _ema(prices, self.slow_period)

        if reverse:
            ultra_fast_values = list(reversed(ultra_fast_values))
            fast_values = list(reversed(fast_values))
            medium_values = list(reversed(medium_values))
            slow_values = list(reversed(slow_values))

        return {
            'ema_ultra_fast': ultra_fast_values[-1] if ultra_fast_values else None,
            'ema_fast': fast_values[-1] if fast_values else None,
            'ema_medium': medium_values[-1] if medium_values else None,
            'ema_slow': slow_values[-1] if slow_values else None,
            'ema_ultra_fast_series': ultra_fast_values,
            'ema_fast_series': fast_values,
            'ema_medium_series': medium_values,
            'ema_slow_series': slow_values
        }

    def calculate_latest(self, prices: List[float]) -> Dict[str, Optional[float]]:
        """
        快捷方法：只返回最新的四条EMA值

        Args:
            prices: 价格序列

        Returns:
            包含四条EMA最新值的字典
        """
        if len(prices) < self.slow_period:
            return {
                'ema_ultra_fast': None,
                'ema_fast': None,
                'ema_medium': None,
                'ema_slow': None
            }

        return {
            'ema_ultra_fast': _ema_latest(prices, self.ultra_fast_period),
            'ema_fast': _ema_latest(prices, self.fast_period),
            'ema_medium': _ema_latest(prices, self.medium_period),
            'ema_slow': _ema_latest(prices, self.slow_period)
        }

    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'ultra_fast_period': self.ultra_fast_period,
            'fast_period': self.fast_period,
            'medium_period': self.medium_period,
            'slow_period': self.slow_period
        }

    def set_parameters(self,
                       ultra_fast_period: int = None,
                       fast_period: int = None,
                       medium_period: int = None,
                       slow_period: int = None):
        """更新参数设置"""
        if ultra_fast_period is not None:
            self.ultra_fast_period = ultra_fast_period
        if fast_period is not None:
            self.fast_period = fast_period
        if medium_period is not None:
            self.medium_period = medium_period
        if slow_period is not None:
            self.slow_period = slow_period


class EMAFourLineAnalyzer:
    """
    EMA四线分析器（无状态版本）
    提供完整的趋势分析和交易信号
    """

    def __init__(self,
                 ultra_fast_period: int = 5,
                 fast_period: int = 10,
                 medium_period: int = 20,
                 slow_period: int = 60):
        """
        初始化EMA四线分析器

        Args:
            ultra_fast_period: 超快速EMA周期
            fast_period: 快速EMA周期
            medium_period: 中速EMA周期
            slow_period: 慢速EMA周期
        """
        self.system = EMAFourLineSystem(ultra_fast_period, fast_period, medium_period, slow_period)

    def analyze(self, prices: List[float]) -> Dict[str, Any]:
        """
        综合分析EMA四线系统（无状态，基于完整历史数据）

        Args:
            prices: 价格序列

        Returns:
            包含EMA值、趋势、信号等的综合分析字典
        """
        result = self.system.calculate(prices)

        uf = result['ema_ultra_fast']
        f = result['ema_fast']
        m = result['ema_medium']
        s = result['ema_slow']

        if uf is None or f is None or m is None or s is None:
            return {
                **result,
                'trend': 'UNKNOWN',
                'signal': 'HOLD',
                'trend_strength': {'strength': 'UNKNOWN', 'direction': 'NEUTRAL', 'score': 0}
            }

        # 判断趋势
        trend = self._get_trend(uf, f, m, s)

        # 检测信号（需要序列来判断交叉）
        signal = self._get_signal(result)

        # 计算趋势强度
        trend_strength = self._get_trend_strength(uf, f, m, s)

        return {
            **result,
            'trend': trend,
            'signal': signal,
            'trend_strength': trend_strength,
            'price': prices[-1] if prices else None
        }

    def _get_trend(self, uf: float, f: float, m: float, s: float) -> str:
        """判断趋势"""
        if uf > f > m > s:
            return 'PERFECT_BULL'
        elif (uf > f > m) or (f > m > s):
            return 'STRONG_BULL'
        elif uf > f or f > m:
            return 'BULL'
        elif uf < f < m < s:
            return 'PERFECT_BEAR'
        elif (uf < f < m) or (f < m < s):
            return 'STRONG_BEAR'
        elif uf < f or f < m:
            return 'BEAR'
        else:
            return 'SIDEWAYS'

    def _get_signal(self, result: Dict[str, Any]) -> str:
        """检测交易信号"""
        uf_series = result['ema_ultra_fast_series']
        f_series = result['ema_fast_series']

        if len(uf_series) < 2 or len(f_series) < 2:
            return 'HOLD'

        prev_uf = uf_series[-2]
        prev_f = f_series[-2]
        curr_uf = uf_series[-1]
        curr_f = f_series[-1]

        uf = result['ema_ultra_fast']
        f = result['ema_fast']
        m = result['ema_medium']
        s = result['ema_slow']

        # 金叉
        if prev_uf <= prev_f and curr_uf > curr_f:
            if uf > f > m > s:
                return 'STRONG_BUY'
            elif uf > f > m or f > m > s:
                return 'BUY'
            else:
                return 'WEAK_BUY'

        # 死叉
        elif prev_uf >= prev_f and curr_uf < curr_f:
            if uf < f < m < s:
                return 'STRONG_SELL'
            elif uf < f < m or f < m < s:
                return 'SELL'
            else:
                return 'WEAK_SELL'

        return 'HOLD'

    def _get_trend_strength(self, uf: float, f: float, m: float, s: float) -> Dict[str, Any]:
        """计算趋势强度"""
        score = 0

        # 均线排列（40分）
        if uf > f > m > s:
            score += 40
        elif uf < f < m < s:
            score -= 40
        elif (uf > f > m) or (f > m > s):
            score += 30
        elif (uf < f < m) or (f < m < s):
            score -= 30
        elif (uf > f and f > m) or (f > m and m > s):
            score += 20
        elif (uf < f and f < m) or (f < m and m < s):
            score -= 20

        # 均线间距（30分）
        if uf != 0 and s != 0:
            gap_percent = abs((uf - s) / s * 100)
            if gap_percent > 5:
                score += 30 if uf > s else -30
            elif gap_percent > 3:
                score += 20 if uf > s else -20
            elif gap_percent > 1:
                score += 10 if uf > s else -10

        # 均线斜率（30分）
        if uf > f:
            score += 15
        if f > m:
            score += 15
        if uf < f:
            score -= 15
        if f < m:
            score -= 15

        abs_score = abs(score)
        if abs_score >= 80:
            strength = 'VERY_STRONG'
        elif abs_score >= 60:
            strength = 'STRONG'
        elif abs_score >= 40:
            strength = 'MODERATE'
        elif abs_score >= 20:
            strength = 'WEAK'
        else:
            strength = 'VERY_WEAK'

        direction = 'BULL' if score > 0 else 'BEAR' if score < 0 else 'NEUTRAL'

        return {
            'strength': strength,
            'direction': direction,
            'score': score
        }

    def get_signal(self, prices: List[float]) -> str:
        """
        获取交易信号

        Args:
            prices: 价格序列

        Returns:
            信号字符串
        """
        return self.analyze(prices)['signal']

    def get_trend(self, prices: List[float]) -> str:
        """
        获取当前趋势

        Args:
            prices: 价格序列

        Returns:
            趋势字符串
        """
        return self.analyze(prices)['trend']

    def get_price_position(self, prices: List[float]) -> Dict[str, Any]:
        """
        获取价格相对于四条EMA的位置

        Args:
            prices: 价格序列

        Returns:
            包含位置信息和距离百分比的字典
        """
        result = self.system.calculate_latest(prices)
        current_price = prices[-1] if prices else 0

        uf = result['ema_ultra_fast']
        f = result['ema_fast']
        m = result['ema_medium']
        s = result['ema_slow']

        if uf is None or f is None or m is None or s is None:
            return {'position': 'UNKNOWN', 'distances': {}, 'above_count': 0}

        distances = {
            'ultra_fast': ((current_price - uf) / uf * 100) if uf != 0 else 0,
            'fast': ((current_price - f) / f * 100) if f != 0 else 0,
            'medium': ((current_price - m) / m * 100) if m != 0 else 0,
            'slow': ((current_price - s) / s * 100) if s != 0 else 0
        }

        ema_list = [uf, f, m, s]
        above_count = sum(1 for ema in ema_list if current_price > ema)

        if above_count == 4:
            position = 'ABOVE_ALL'
        elif above_count == 3:
            position = 'ABOVE_MOST'
        elif above_count == 2:
            position = 'MIDDLE'
        elif above_count == 1:
            position = 'BELOW_MOST'
        else:
            position = 'BELOW_ALL'

        return {
            'position': position,
            'distances': distances,
            'above_count': above_count
        }

    def get_support_resistance(self, prices: List[float]) -> Dict[str, Optional[float]]:
        """
        获取EMA作为支撑/阻力位

        Args:
            prices: 价格序列

        Returns:
            包含支撑或阻力位的字典
        """
        result = self.system.calculate_latest(prices)
        analysis = self.analyze(prices)
        trend = analysis['trend']

        if 'BULL' in trend:
            return {
                'support_1': result['ema_ultra_fast'],
                'support_2': result['ema_fast'],
                'support_3': result['ema_medium'],
                'support_4': result['ema_slow']
            }
        elif 'BEAR' in trend:
            return {
                'resistance_1': result['ema_ultra_fast'],
                'resistance_2': result['ema_fast'],
                'resistance_3': result['ema_medium'],
                'resistance_4': result['ema_slow']
            }
        else:
            return {
                'level_1': result['ema_ultra_fast'],
                'level_2': result['ema_fast'],
                'level_3': result['ema_medium'],
                'level_4': result['ema_slow']
            }


# 向后兼容
EMACrossSystem = EMAFourLineSystem
EMACrossAnalyzer = EMAFourLineAnalyzer
