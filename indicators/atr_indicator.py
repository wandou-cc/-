"""
ATR (Average True Range) 平均真实波动幅度指标实现
用于判断市场波动率和设置止损位
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class ATRIndicator:
    """
    ATR指标计算类
    
    ATR用于衡量市场波动率：
    1. TR (True Range) = max(H-L, |H-PC|, |L-PC|)
       其中 H=最高价, L=最低价, PC=前收盘价
    2. ATR = TR的移动平均（使用EMA）
    """
    
    def __init__(self, period: int = 14):
        """
        初始化ATR指标参数
        
        Args:
            period: ATR计算周期，默认14
        """
        self.period = period
        
        # 存储历史数据
        self.high_history = []
        self.low_history = []
        self.close_history = []
        
        self.atr = None
        self.previous_close = None
        
        # EMA的alpha值
        self.alpha = 1.0 / period
    
    def _calculate_true_range(self, high: float, low: float, previous_close: Optional[float]) -> float:
        """
        计算真实波动幅度(TR)
        
        Args:
            high: 当前最高价
            low: 当前最低价
            previous_close: 前一日收盘价
            
        Returns:
            TR值
        """
        if previous_close is None:
            # 第一个数据点，TR = H - L
            return high - low
        
        # TR = max(H-L, |H-PC|, |L-PC|)
        tr1 = high - low
        tr2 = abs(high - previous_close)
        tr3 = abs(low - previous_close)
        
        return max(tr1, tr2, tr3)
    
    def calculate(self, highs: List[float], lows: List[float], closes: List[float],
                  reverse: bool = False) -> Dict[str, List[float]]:
        """
        批量计算ATR指标

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            reverse: 是否为倒序数据（从新到旧），默认False

        Returns:
            包含ATR和TR值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")

        if len(closes) < self.period:
            raise ValueError(f"数据长度不足，至少需要{self.period}个数据点")

        # 如果数据是倒序的，先反转
        if reverse:
            highs = list(reversed(highs))
            lows = list(reversed(lows))
            closes = list(reversed(closes))

        # 计算所有TR值
        tr_values = []
        for i in range(len(closes)):
            if i == 0:
                tr = highs[i] - lows[i]
            else:
                tr = self._calculate_true_range(highs[i], lows[i], closes[i-1])
            tr_values.append(tr)

        # 计算ATR（使用Wilder平滑法，更标准的方法）
        atr_values = []

        # 初始ATR = 前N个TR的平均值（SMA）
        initial_atr = sum(tr_values[:self.period]) / self.period
        atr = initial_atr

        # 前period-1个位置填充None或不输出
        # 第period个位置开始有ATR值
        atr_values.append(atr)

        # 后续ATR使用Wilder平滑法: ATR = (前ATR * (period-1) + 当前TR) / period
        # 这等价于 EMA with alpha = 1/period
        for i in range(self.period, len(tr_values)):
            atr = (atr * (self.period - 1) + tr_values[i]) / self.period
            atr_values.append(atr)

        # 如果输入是倒序的，结果也要反转回去
        if reverse:
            atr_values = list(reversed(atr_values))
            tr_values = list(reversed(tr_values))
            return {
                'atr': atr_values,
                'tr': tr_values[:len(atr_values)]  # TR对齐ATR长度
            }

        return {
            'atr': atr_values,
            'tr': tr_values[self.period - 1:]  # TR从第period个开始对齐
        }
    
    def update(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        实时更新ATR指标
        
        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
            
        Returns:
            当前时刻的ATR值
        """
        # 添加到历史数据
        self.high_history.append(high)
        self.low_history.append(low)
        self.close_history.append(close)
        
        # 计算TR
        tr = self._calculate_true_range(high, low, self.previous_close)
        
        # 更新ATR
        if self.atr is None:
            # 初始化：需要period个数据点
            if len(self.close_history) >= self.period:
                # 计算初始ATR
                result = self.calculate(self.high_history, self.low_history, self.close_history)
                self.atr = result['atr'][-1]
        else:
            # 增量更新：使用EMA
            self.atr = self.alpha * tr + (1 - self.alpha) * self.atr
        
        self.previous_close = close
        
        return {
            'atr': self.atr,
            'tr': tr
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """获取当前的ATR值"""
        return {
            'atr': self.atr,
            'tr': None  # TR需要每次重新计算
        }
    
    def reset(self):
        """重置指标状态"""
        self.high_history = []
        self.low_history = []
        self.close_history = []
        self.atr = None
        self.previous_close = None
    
    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'period': self.period
        }


class ATRAnalyzer:
    """
    ATR分析器，提供波动率分析和止损建议
    """
    
    def __init__(self, atr_indicator: ATRIndicator):
        self.atr = atr_indicator
        self.atr_history = []
    
    def get_volatility_level(self) -> str:
        """
        获取波动率水平
        
        Returns:
            'VERY_HIGH': 极高波动
            'HIGH': 高波动
            'MEDIUM': 中等波动
            'LOW': 低波动
        """
        current = self.atr.get_current_values()
        
        if current['atr'] is None:
            return 'UNKNOWN'
        
        # 记录ATR历史
        self.atr_history.append(current['atr'])
        
        # 如果历史数据不足，返回MEDIUM
        if len(self.atr_history) < 20:
            return 'MEDIUM'
        
        # 计算最近20期ATR的平均值
        recent_atr = self.atr_history[-20:]
        avg_atr = sum(recent_atr) / len(recent_atr)
        current_atr = current['atr']
        
        # 根据当前ATR与平均ATR的比值判断
        ratio = current_atr / avg_atr if avg_atr != 0 else 1
        
        if ratio > 1.5:
            return 'VERY_HIGH'
        elif ratio > 1.2:
            return 'HIGH'
        elif ratio > 0.8:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_stop_loss_distance(self, multiplier: float = 2.0) -> float:
        """
        获取建议的止损距离
        
        Args:
            multiplier: ATR倍数，默认2.0
            
        Returns:
            建议的止损距离
        """
        current = self.atr.get_current_values()
        
        if current['atr'] is None:
            return 0
        
        return current['atr'] * multiplier
    
    def is_breakout_valid(self, price_move: float, threshold: float = 1.0) -> bool:
        """
        判断突破是否有效（价格移动是否超过ATR的一定倍数）
        
        Args:
            price_move: 价格移动幅度
            threshold: ATR倍数阈值，默认1.0
            
        Returns:
            True: 突破有效, False: 突破无效
        """
        current = self.atr.get_current_values()
        
        if current['atr'] is None:
            return False
        
        return abs(price_move) > (current['atr'] * threshold)

