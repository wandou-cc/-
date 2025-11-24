"""
EMA四线交叉系统实现（优化版）
基于TradingView标准，实现更完善的四条均线系统
常用周期：5, 10, 20, 60 或 7, 25, 99, 200
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class EMAIndicator:
    """
    EMA（指数移动平均线）计算类
    
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
        self.alpha = 2.0 / (period + 1)
        
        # 存储历史数据
        self.price_history = []
        self.ema = None
    
    def calculate(self, prices: List[float]) -> List[float]:
        """
        批量计算EMA

        Args:
            prices: 价格序列

        Returns:
            EMA值序列
        """
        if not prices or len(prices) < 1:
            return []

        # 验证数据类型
        if not all(isinstance(p, (int, float)) for p in prices):
            raise ValueError("价格数据必须是数值类型")

        ema_values = []
        ema = prices[0]  # 第一个值作为初始EMA

        for price in prices:
            ema = self.alpha * price + (1 - self.alpha) * ema
            ema_values.append(ema)

        return ema_values
    
    def update(self, new_price: float) -> float:
        """
        实时更新EMA

        Args:
            new_price: 新的价格值

        Returns:
            当前的EMA值
        """
        # 验证数据类型
        if not isinstance(new_price, (int, float)):
            raise ValueError("价格必须是数值类型")

        self.price_history.append(new_price)

        if self.ema is None:
            # 初始化
            self.ema = new_price
        else:
            # 增量更新
            self.ema = self.alpha * new_price + (1 - self.alpha) * self.ema

        return self.ema
    
    def get_current_value(self) -> float:
        """获取当前EMA值"""
        return self.ema
    
    def reset(self):
        """重置指标状态"""
        self.price_history = []
        self.ema = None


class EMAFourLineSystem:
    """
    EMA四线交叉系统（优化版）
    
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
        
        self.ema_ultra_fast = EMAIndicator(ultra_fast_period)
        self.ema_fast = EMAIndicator(fast_period)
        self.ema_medium = EMAIndicator(medium_period)
        self.ema_slow = EMAIndicator(slow_period)
        
        # 存储前一个值，用于检测交叉
        self.previous_values = {}
    
    def calculate(self, prices: List[float]) -> Dict[str, List[float]]:
        """
        批量计算EMA四线系统
        
        Args:
            prices: 价格序列
            
        Returns:
            包含四条EMA的字典
        """
        if len(prices) < self.slow_period:
            raise ValueError(f"数据长度不足，至少需要{self.slow_period}个数据点")
        
        ultra_fast_values = self.ema_ultra_fast.calculate(prices)
        fast_values = self.ema_fast.calculate(prices)
        medium_values = self.ema_medium.calculate(prices)
        slow_values = self.ema_slow.calculate(prices)
        
        return {
            'ema_ultra_fast': ultra_fast_values,
            'ema_fast': fast_values,
            'ema_medium': medium_values,
            'ema_slow': slow_values
        }
    
    def update(self, new_price: float) -> Dict[str, float]:
        """
        实时更新EMA四线系统
        
        Args:
            new_price: 新的价格值
            
        Returns:
            当前的EMA值
        """
        ultra_fast = self.ema_ultra_fast.update(new_price)
        fast = self.ema_fast.update(new_price)
        medium = self.ema_medium.update(new_price)
        slow = self.ema_slow.update(new_price)
        
        return {
            'ema_ultra_fast': ultra_fast,
            'ema_fast': fast,
            'ema_medium': medium,
            'ema_slow': slow,
            'price': new_price
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """获取当前的EMA值"""
        return {
            'ema_ultra_fast': self.ema_ultra_fast.get_current_value(),
            'ema_fast': self.ema_fast.get_current_value(),
            'ema_medium': self.ema_medium.get_current_value(),
            'ema_slow': self.ema_slow.get_current_value()
        }
    
    def reset(self):
        """重置系统状态"""
        self.ema_ultra_fast.reset()
        self.ema_fast.reset()
        self.ema_medium.reset()
        self.ema_slow.reset()
        self.previous_values = {}
    
    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'ultra_fast_period': self.ultra_fast_period,
            'fast_period': self.fast_period,
            'medium_period': self.medium_period,
            'slow_period': self.slow_period
        }


class EMAFourLineAnalyzer:
    """
    EMA四线分析器（优化版）
    
    提供完整的趋势分析和交易信号
    """
    
    def __init__(self, ema_system: EMAFourLineSystem):
        self.ema_system = ema_system
        self.previous_values = {
            'ultra_fast': None,
            'fast': None,
            'medium': None,
            'slow': None
        }
    
    def get_signal(self) -> str:
        """
        获取交易信号（基于多均线交叉）
        
        Returns:
            'STRONG_BUY': 强烈买入（完美多头排列）
            'BUY': 买入（短期金叉）
            'WEAK_BUY': 弱买入（部分多头）
            'STRONG_SELL': 强烈卖出（完美空头排列）
            'SELL': 卖出（短期死叉）
            'WEAK_SELL': 弱卖出（部分空头）
            'HOLD': 持有
        """
        current = self.ema_system.get_current_values()
        uf = current['ema_ultra_fast']  # 超快线
        f = current['ema_fast']          # 快线
        m = current['ema_medium']        # 中线
        s = current['ema_slow']          # 慢线
        
        if uf is None or f is None or m is None or s is None:
            return 'HOLD'
        
        prev_uf = self.previous_values['ultra_fast']
        prev_f = self.previous_values['fast']
        
        # 检测交叉信号
        if prev_uf is not None and prev_f is not None:
            # 超快线上穿快线（金叉）
            if prev_uf <= prev_f and uf > f:
                # 判断整体趋势
                if uf > f > m > s:  # 完美多头排列
                    signal = 'STRONG_BUY'
                elif uf > f > m or f > m > s:  # 较强多头
                    signal = 'BUY'
                else:
                    signal = 'WEAK_BUY'
                
                self._update_previous(uf, f, m, s)
                return signal
            
            # 超快线下穿快线（死叉）
            elif prev_uf >= prev_f and uf < f:
                # 判断整体趋势
                if uf < f < m < s:  # 完美空头排列
                    signal = 'STRONG_SELL'
                elif uf < f < m or f < m < s:  # 较强空头
                    signal = 'SELL'
                else:
                    signal = 'WEAK_SELL'
                
                self._update_previous(uf, f, m, s)
                return signal
        
        self._update_previous(uf, f, m, s)
        return 'HOLD'
    
    def get_trend(self) -> str:
        """
        获取当前趋势（基于四线排列）

        Returns:
            'PERFECT_BULL': 完美多头（超快>快>中>慢）
            'STRONG_BULL': 强势多头
            'BULL': 多头趋势
            'PERFECT_BEAR': 完美空头（超快<快<中<慢）
            'STRONG_BEAR': 强势空头
            'BEAR': 空头趋势
            'SIDEWAYS': 震荡整理
        """
        current = self.ema_system.get_current_values()
        uf = current['ema_ultra_fast']
        f = current['ema_fast']
        m = current['ema_medium']
        s = current['ema_slow']

        if uf is None or f is None or m is None or s is None:
            return 'SIDEWAYS'

        # 完美多头排列
        if uf > f > m > s:
            return 'PERFECT_BULL'
        # 强势多头（3条线多头排列）
        elif (uf > f > m) or (f > m > s):
            return 'STRONG_BULL'
        # 多头趋势（部分多头排列）
        elif uf > f or f > m:
            return 'BULL'
        # 完美空头排列
        elif uf < f < m < s:
            return 'PERFECT_BEAR'
        # 强势空头（3条线空头排列）
        elif (uf < f < m) or (f < m < s):
            return 'STRONG_BEAR'
        # 空头趋势（部分空头排列）
        elif uf < f or f < m:
            return 'BEAR'
        # 震荡
        else:
            return 'SIDEWAYS'
    
    def get_price_position(self, current_price: float) -> Dict[str, Any]:
        """
        获取价格相对于四条EMA的位置
        
        Args:
            current_price: 当前价格
            
        Returns:
            包含位置信息和距离百分比的字典
        """
        current = self.ema_system.get_current_values()
        uf = current['ema_ultra_fast']
        f = current['ema_fast']
        m = current['ema_medium']
        s = current['ema_slow']
        
        if uf is None or f is None or m is None or s is None:
            return {'position': 'UNKNOWN', 'distances': {}}
        
        # 计算距离百分比
        distances = {
            'ultra_fast': ((current_price - uf) / uf * 100) if uf != 0 else 0,
            'fast': ((current_price - f) / f * 100) if f != 0 else 0,
            'medium': ((current_price - m) / m * 100) if m != 0 else 0,
            'slow': ((current_price - s) / s * 100) if s != 0 else 0
        }
        
        # 判断位置
        ema_list = [uf, f, m, s]
        above_count = sum(1 for ema in ema_list if current_price > ema)
        
        if above_count == 4:
            position = 'ABOVE_ALL'  # 价格在所有均线之上（非常强势）
        elif above_count == 3:
            position = 'ABOVE_MOST'  # 价格在大部分均线之上（强势）
        elif above_count == 2:
            position = 'MIDDLE'  # 价格在均线中间（中性）
        elif above_count == 1:
            position = 'BELOW_MOST'  # 价格在大部分均线之下（弱势）
        else:
            position = 'BELOW_ALL'  # 价格在所有均线之下（非常弱势）
        
        return {
            'position': position,
            'distances': distances,
            'above_count': above_count
        }
    
    def get_support_resistance(self) -> Dict[str, float]:
        """
        获取EMA作为支撑/阻力位
        
        Returns:
            包含支撑和阻力位的字典
        """
        current = self.ema_system.get_current_values()
        
        # EMA可以作为动态支撑/阻力
        # 在上升趋势中，EMA是支撑
        # 在下降趋势中，EMA是阻力
        trend = self.get_trend()
        
        if 'BULL' in trend:
            # 多头趋势，EMA作为支撑
            return {
                'support_1': current['ema_ultra_fast'],  # 第一支撑
                'support_2': current['ema_fast'],        # 第二支撑
                'support_3': current['ema_medium'],      # 第三支撑
                'support_4': current['ema_slow'],        # 第四支撑
            }
        elif 'BEAR' in trend:
            # 空头趋势，EMA作为阻力
            return {
                'resistance_1': current['ema_ultra_fast'],  # 第一阻力
                'resistance_2': current['ema_fast'],        # 第二阻力
                'resistance_3': current['ema_medium'],      # 第三阻力
                'resistance_4': current['ema_slow'],        # 第四阻力
            }
        else:
            # 震荡，既是支撑也是阻力
            return {
                'level_1': current['ema_ultra_fast'],
                'level_2': current['ema_fast'],
                'level_3': current['ema_medium'],
                'level_4': current['ema_slow'],
            }
    
    def get_trend_strength(self) -> Dict[str, Any]:
        """
        获取趋势强度
        
        Returns:
            包含趋势强度和分数的字典
        """
        current = self.ema_system.get_current_values()
        uf = current['ema_ultra_fast']
        f = current['ema_fast']
        m = current['ema_medium']
        s = current['ema_slow']
        
        if uf is None or f is None or m is None or s is None:
            return {'strength': 'UNKNOWN', 'score': 0}
        
        # 计算趋势强度分数（0-100）
        score = 0
        
        # 1. 均线排列（40分）
        if uf > f > m > s:  # 完美多头
            score += 40
        elif uf < f < m < s:  # 完美空头
            score -= 40
        elif (uf > f > m) or (f > m > s):  # 3条多头
            score += 30
        elif (uf < f < m) or (f < m < s):  # 3条空头
            score -= 30
        elif (uf > f and f > m) or (f > m and m > s):  # 2条多头
            score += 20
        elif (uf < f and f < m) or (f < m and m < s):  # 2条空头
            score -= 20
        
        # 2. 均线间距（30分）- 间距越大，趋势越强
        if uf != 0 and s != 0:
            gap_percent = abs((uf - s) / s * 100)
            if gap_percent > 5:
                score += 30 if uf > s else -30
            elif gap_percent > 3:
                score += 20 if uf > s else -20
            elif gap_percent > 1:
                score += 10 if uf > s else -10
        
        # 3. 均线斜率（30分）- 斜率越陡，趋势越强
        # 这里简化处理，实际应该计算斜率
        if uf > f:
            score += 15
        if f > m:
            score += 15
        if uf < f:
            score -= 15
        if f < m:
            score -= 15
        
        # 判断强度等级
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
    
    def _update_previous(self, uf, f, m, s):
        """更新前一个值"""
        self.previous_values['ultra_fast'] = uf
        self.previous_values['fast'] = f
        self.previous_values['medium'] = m
        self.previous_values['slow'] = s


# 向后兼容：保留旧的三线系统类名
EMACrossSystem = EMAFourLineSystem
EMACrossAnalyzer = EMAFourLineAnalyzer
