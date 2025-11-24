"""
VWAP (Volume Weighted Average Price) 成交量加权平均价实现
日内交易最重要的指标之一
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class VWAPIndicator:
    """
    VWAP指标计算类
    
    VWAP = Σ(价格 × 成交量) / Σ(成交量)
    
    特点：
    - 日内交易的基准价格
    - 机构交易员广泛使用
    - 价格在VWAP上方=强势，下方=弱势
    """
    
    def __init__(self):
        """初始化VWAP指标"""
        # 存储历史数据
        self.price_history = []
        self.volume_history = []
        
        self.cumulative_pv = 0  # 累计价格×成交量
        self.cumulative_volume = 0  # 累计成交量
        self.vwap = None
    
    def calculate(self, prices: List[float], volumes: List[float]) -> List[float]:
        """
        批量计算VWAP
        
        Args:
            prices: 价格序列（通常使用典型价格: (H+L+C)/3）
            volumes: 成交量序列
            
        Returns:
            VWAP值序列
        """
        if len(prices) != len(volumes):
            raise ValueError("价格和成交量数据长度必须一致")
        
        if len(prices) < 1:
            return []
        
        vwap_values = []
        cumulative_pv = 0
        cumulative_volume = 0
        
        for price, volume in zip(prices, volumes):
            cumulative_pv += price * volume
            cumulative_volume += volume
            
            if cumulative_volume > 0:
                vwap = cumulative_pv / cumulative_volume
            else:
                vwap = price
            
            vwap_values.append(vwap)
        
        return vwap_values
    
    def update(self, price: float, volume: float) -> float:
        """
        实时更新VWAP
        
        Args:
            price: 价格（建议使用典型价格: (H+L+C)/3）
            volume: 成交量
            
        Returns:
            当前的VWAP值
        """
        self.price_history.append(price)
        self.volume_history.append(volume)
        
        # 累加
        self.cumulative_pv += price * volume
        self.cumulative_volume += volume
        
        # 计算VWAP
        if self.cumulative_volume > 0:
            self.vwap = self.cumulative_pv / self.cumulative_volume
        else:
            self.vwap = price
        
        return self.vwap
    
    def get_current_value(self) -> float:
        """获取当前VWAP值"""
        return self.vwap
    
    def reset(self):
        """重置指标状态（通常在每个交易日开始时重置）"""
        self.price_history = []
        self.volume_history = []
        self.cumulative_pv = 0
        self.cumulative_volume = 0
        self.vwap = None
    
    def calculate_typical_price(self, high: float, low: float, close: float) -> float:
        """
        计算典型价格 (Typical Price)
        
        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
            
        Returns:
            典型价格 = (H + L + C) / 3
        """
        return (high + low + close) / 3


class VWAPAnalyzer:
    """
    VWAP分析器，提供交易信号
    """
    
    def __init__(self, vwap_indicator: VWAPIndicator):
        self.vwap = vwap_indicator
        self.previous_price = None
    
    def get_signal(self, current_price: float) -> str:
        """
        获取交易信号
        
        Args:
            current_price: 当前价格
            
        Returns:
            'BUY': 买入信号（价格突破VWAP向上）
            'SELL': 卖出信号（价格跌破VWAP向下）
            'HOLD': 持有信号
        """
        vwap_value = self.vwap.get_current_value()
        
        if vwap_value is None or self.previous_price is None:
            self.previous_price = current_price
            return 'HOLD'
        
        # 价格向上突破VWAP
        if self.previous_price <= vwap_value and current_price > vwap_value:
            self.previous_price = current_price
            return 'BUY'
        
        # 价格向下跌破VWAP
        elif self.previous_price >= vwap_value and current_price < vwap_value:
            self.previous_price = current_price
            return 'SELL'
        
        self.previous_price = current_price
        return 'HOLD'
    
    def get_price_position(self, current_price: float) -> str:
        """
        获取价格相对于VWAP的位置
        
        Args:
            current_price: 当前价格
            
        Returns:
            'STRONG_ABOVE': 远高于VWAP（>2%）
            'ABOVE': 高于VWAP
            'AT_VWAP': 接近VWAP（±0.1%）
            'BELOW': 低于VWAP
            'STRONG_BELOW': 远低于VWAP（<-2%）
        """
        vwap_value = self.vwap.get_current_value()
        
        if vwap_value is None or vwap_value == 0:
            return 'UNKNOWN'
        
        deviation = (current_price - vwap_value) / vwap_value * 100
        
        if deviation > 2.0:
            return 'STRONG_ABOVE'
        elif deviation > 0.1:
            return 'ABOVE'
        elif deviation < -2.0:
            return 'STRONG_BELOW'
        elif deviation < -0.1:
            return 'BELOW'
        else:
            return 'AT_VWAP'
    
    def get_strength(self, current_price: float) -> str:
        """
        获取市场强弱
        
        Args:
            current_price: 当前价格
            
        Returns:
            'BULLISH': 看涨（价格在VWAP上方）
            'BEARISH': 看跌（价格在VWAP下方）
            'NEUTRAL': 中性
        """
        vwap_value = self.vwap.get_current_value()
        
        if vwap_value is None:
            return 'NEUTRAL'
        
        if current_price > vwap_value:
            return 'BULLISH'
        elif current_price < vwap_value:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

