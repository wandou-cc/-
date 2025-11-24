"""
KDJ (随机指标) 实现
基于TradingView的Pine Script实现，使用bcwsma平滑方法
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class KDJIndicator:
    """
    KDJ指标计算类（TradingView标准实现）
    
    KDJ指标包含三条线：
    1. K线 = bcwsma(RSV, signal, 1)
    2. D线 = bcwsma(K, signal, 1)
    3. J线 = 3K - 2D
    
    其中：
    - RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) × 100
    - bcwsma是一种特殊的加权移动平均：bcwsma = (m×s + (l-m)×前值) / l
    """
    
    def __init__(self, period: int = 9, signal: int = 3):
        """
        初始化KDJ指标参数（TradingView标准）
        
        Args:
            period: RSV计算周期（ilong），默认9
            signal: 平滑周期（isig），默认3
        """
        self.period = period  # ilong
        self.signal = signal  # isig
        
        # 存储历史数据用于增量计算
        self.high_history = []
        self.low_history = []
        self.close_history = []
        
        self.k = None  # K值
        self.d = None  # D值
        self.j = None  # J值
    
    def _bcwsma(self, source_values: List[float], length: int, weight: int, initial_value: float = 50.0) -> List[float]:
        """
        计算bcwsma（TradingView使用的特殊加权移动平均）
        
        bcwsma = (weight × source + (length - weight) × 前一个bcwsma) / length
        
        Args:
            source_values: 源数据序列
            length: 长度参数（isig）
            weight: 权重参数（固定为1）
            initial_value: 初始值（默认50.0，符合TradingView标准）
            
        Returns:
            bcwsma值序列
        """
        if not source_values:
            return []
        
        bcwsma_values = []
        bcwsma = initial_value  # 使用指定的初始值
        
        for s in source_values:
            # bcwsma = (weight × s + (length - weight) × 前bcwsma) / length
            bcwsma = (weight * s + (length - weight) * bcwsma) / length
            bcwsma_values.append(bcwsma)
        
        return bcwsma_values
    
    def calculate(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, List[float]]:
        """
        批量计算KDJ指标（完全按照TradingView Pine Script实现）
        
        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            
        Returns:
            包含K、D、J值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")
        
        if len(closes) < self.period:
            raise ValueError(f"数据长度不足，至少需要{self.period}个数据点")
        
        # 第一步：计算RSV
        rsv_values = []
        for i in range(self.period - 1, len(closes)):
            # 获取period日内的最高价和最低价
            period_highs = highs[i - self.period + 1:i + 1]
            period_lows = lows[i - self.period + 1:i + 1]
            close = closes[i]
            
            # h = highest(high, ilong)
            # l = lowest(low, ilong)
            highest = max(period_highs)
            lowest = min(period_lows)
            
            # RSV = 100 * ((c - l) / (h - l))
            if highest != lowest:
                rsv = 100 * ((close - lowest) / (highest - lowest))
            else:
                rsv = 50.0
            
            rsv_values.append(rsv)
        
        # 第二步：pK = bcwsma(RSV, isig, 1)，初始值为50
        k_values = self._bcwsma(rsv_values, self.signal, 1, initial_value=50.0)
        
        # 第三步：pD = bcwsma(pK, isig, 1)，初始值为50
        d_values = self._bcwsma(k_values, self.signal, 1, initial_value=50.0)
        
        # 第四步：pJ = 3 * pK - 2 * pD
        j_values = [3 * k - 2 * d for k, d in zip(k_values, d_values)]
        
        return {
            'k': k_values,
            'd': d_values,
            'j': j_values
        }
    
    def update(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        实时更新KDJ指标（TradingView标准方法）
        
        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
            
        Returns:
            当前时刻的KDJ值
        """
        # 添加到历史数据
        self.high_history.append(high)
        self.low_history.append(low)
        self.close_history.append(close)
        
        # 如果数据不足，返回初始值
        if len(self.close_history) < self.period:
            return {
                'k': None,
                'd': None,
                'j': None
            }
        
        # 重新计算（使用所有历史数据以确保与TradingView一致）
        result = self.calculate(self.high_history, self.low_history, self.close_history)
        
        self.k = result['k'][-1]
        self.d = result['d'][-1]
        self.j = result['j'][-1]
        
        return {
            'k': self.k,
            'd': self.d,
            'j': self.j
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """获取当前的KDJ值"""
        return {
            'k': self.k,
            'd': self.d,
            'j': self.j
        }
    
    def reset(self):
        """重置指标状态"""
        self.high_history = []
        self.low_history = []
        self.close_history = []
        self.k = 50.0
        self.d = 50.0
        self.j = 50.0
    
    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'signal': self.signal
        }


class KDJAnalyzer:
    """
    KDJ分析器，提供买卖信号
    """
    
    def __init__(self, kdj_indicator: KDJIndicator):
        self.kdj = kdj_indicator
        self.previous_k = None
        self.previous_d = None
    
    def get_signal(self) -> str:
        """
        获取交易信号
        
        Returns:
            'BUY': 买入信号（金叉或超卖反弹）
            'SELL': 卖出信号（死叉或超买回调）
            'HOLD': 持有信号
        """
        current = self.kdj.get_current_values()
        k = current['k']
        d = current['d']
        j = current['j']
        
        if self.previous_k is None or self.previous_d is None:
            self.previous_k = k
            self.previous_d = d
            return 'HOLD'
        
        # 金叉：K线向上穿越D线
        if self.previous_k <= self.previous_d and k > d:
            # 如果在超卖区域金叉，信号更强
            if k < 20 or d < 20:
                self.previous_k = k
                self.previous_d = d
                return 'BUY'  # 强烈买入
            else:
                self.previous_k = k
                self.previous_d = d
                return 'BUY'
        
        # 死叉：K线向下穿越D线
        elif self.previous_k >= self.previous_d and k < d:
            # 如果在超买区域死叉，信号更强
            if k > 80 or d > 80:
                self.previous_k = k
                self.previous_d = d
                return 'SELL'  # 强烈卖出
            else:
                self.previous_k = k
                self.previous_d = d
                return 'SELL'
        
        self.previous_k = k
        self.previous_d = d
        return 'HOLD'
    
    def get_momentum_level(self) -> str:
        """
        获取动量水平
        
        Returns:
            'OVERBOUGHT': 超买
            'OVERSOLD': 超卖
            'NEUTRAL': 中性
        """
        current = self.kdj.get_current_values()
        k = current['k']
        d = current['d']
        
        # 超买区域
        if k > 80 and d > 80:
            return 'OVERBOUGHT'
        # 超卖区域
        elif k < 20 and d < 20:
            return 'OVERSOLD'
        else:
            return 'NEUTRAL'
    
    def get_trend_strength(self) -> str:
        """
        获取趋势强度
        
        Returns:
            'STRONG_BULLISH': 强烈看涨
            'BULLISH': 看涨
            'NEUTRAL': 中性
            'BEARISH': 看跌
            'STRONG_BEARISH': 强烈看跌
        """
        current = self.kdj.get_current_values()
        k = current['k']
        d = current['d']
        j = current['j']
        
        # K、D、J都在高位
        if k > 80 and d > 80 and j > 80:
            return 'STRONG_BULLISH'
        elif k > 50 and d > 50:
            return 'BULLISH'
        # K、D、J都在低位
        elif k < 20 and d < 20 and j < 20:
            return 'STRONG_BEARISH'
        elif k < 50 and d < 50:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

