"""
CCI (Commodity Channel Index) 顺势指标实现
基于TradingView的标准实现，支持实时计算和参数配置
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class CCIIndicator:
    """
    CCI指标计算类（TradingView标准）
    
    CCI用于衡量价格偏离其统计平均值的程度。
    
    计算公式：
    1. 典型价格 TP = (高 + 低 + 收) / 3
    2. SMA = TP的简单移动平均
    3. 平均偏差 MD = |TP - SMA| 的平均值
    4. CCI = (TP - SMA) / (0.015 × MD)
    
    其中0.015是常数，确保70%-80%的CCI值在-100到+100之间
    """
    
    def __init__(self, period: int = 20):
        """
        初始化CCI指标参数
        
        Args:
            period: CCI计算周期，默认20
        """
        self.period = period
        
        # 存储历史数据用于增量计算
        self.high_history = []
        self.low_history = []
        self.close_history = []
        
        self.cci = None
        
        # CCI常数
        self.constant = 0.015
    
    def _calculate_typical_price(self, high: float, low: float, close: float) -> float:
        """
        计算典型价格
        
        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
            
        Returns:
            典型价格
        """
        return (high + low + close) / 3.0
    
    def _calculate_sma(self, values: List[float], period: int) -> List[float]:
        """
        计算简单移动平均线
        
        Args:
            values: 数值序列
            period: 周期
            
        Returns:
            SMA值序列
        """
        if len(values) < period:
            return []
        
        sma_values = []
        for i in range(period - 1, len(values)):
            sma = sum(values[i - period + 1:i + 1]) / period
            sma_values.append(sma)
        
        return sma_values
    
    def _calculate_mean_deviation(self, values: List[float], sma_values: List[float], period: int) -> List[float]:
        """
        计算平均偏差

        Args:
            values: 原始数值序列
            sma_values: SMA值序列
            period: 周期

        Returns:
            平均偏差序列
        """
        if len(values) < period or len(sma_values) == 0:
            return []

        md_values = []
        for i in range(len(sma_values)):
            # 获取当前窗口的值 - 窗口应该对应SMA计算时使用的相同数据窗口
            # sma_values[i] 对应的是 values[i:i+period] 的平均值
            window_values = values[i:i + period]
            current_sma = sma_values[i]

            # 计算平均偏差：|TP - SMA| 的平均值
            deviations = [abs(val - current_sma) for val in window_values]
            md = sum(deviations) / period
            md_values.append(md)

        return md_values
    
    def calculate(self, highs: List[float], lows: List[float], closes: List[float]) -> Dict[str, List[float]]:
        """
        批量计算CCI指标（符合TradingView标准）
        
        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            
        Returns:
            包含CCI值的字典
        """
        if len(highs) != len(lows) or len(highs) != len(closes):
            raise ValueError("最高价、最低价、收盘价数据长度必须一致")
        
        if len(closes) < self.period:
            raise ValueError(f"数据长度不足，至少需要{self.period}个数据点")
        
        # 第一步：计算典型价格
        typical_prices = []
        for i in range(len(closes)):
            tp = self._calculate_typical_price(highs[i], lows[i], closes[i])
            typical_prices.append(tp)
        
        # 第二步：计算典型价格的SMA
        sma_values = self._calculate_sma(typical_prices, self.period)
        
        # 第三步：计算平均偏差
        md_values = self._calculate_mean_deviation(typical_prices, sma_values, self.period)
        
        # 第四步：计算CCI
        cci_values = []
        for i in range(len(sma_values)):
            current_tp = typical_prices[i + self.period - 1]
            current_sma = sma_values[i]
            current_md = md_values[i]
            
            # CCI = (TP - SMA) / (0.015 × MD)
            if current_md != 0:
                cci = (current_tp - current_sma) / (self.constant * current_md)
            else:
                cci = 0.0
            
            cci_values.append(cci)
        
        return {
            'cci': cci_values,
            'typical_price': typical_prices[self.period - 1:],
            'sma': sma_values,
            'mean_deviation': md_values
        }
    
    def update(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        实时更新CCI指标
        
        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
            
        Returns:
            当前时刻的CCI值
        """
        # 添加到历史数据
        self.high_history.append(high)
        self.low_history.append(low)
        self.close_history.append(close)
        
        # 如果数据不足，返回None
        if len(self.close_history) < self.period:
            return {
                'cci': None,
                'typical_price': None,
                'sma': None,
                'mean_deviation': None
            }
        
        # 使用最近period个数据计算
        recent_highs = self.high_history[-self.period:]
        recent_lows = self.low_history[-self.period:]
        recent_closes = self.close_history[-self.period:]
        
        # 计算典型价格
        typical_prices = []
        for i in range(len(recent_closes)):
            tp = self._calculate_typical_price(recent_highs[i], recent_lows[i], recent_closes[i])
            typical_prices.append(tp)
        
        # 计算SMA
        current_sma = sum(typical_prices) / self.period
        
        # 计算平均偏差
        deviations = [abs(tp - current_sma) for tp in typical_prices]
        current_md = sum(deviations) / self.period
        
        # 计算CCI
        current_tp = typical_prices[-1]
        if current_md != 0:
            self.cci = (current_tp - current_sma) / (self.constant * current_md)
        else:
            self.cci = 0.0
        
        return {
            'cci': self.cci,
            'typical_price': current_tp,
            'sma': current_sma,
            'mean_deviation': current_md
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """获取当前的CCI值"""
        return {
            'cci': self.cci
        }
    
    def reset(self):
        """重置指标状态"""
        self.high_history = []
        self.low_history = []
        self.close_history = []
        self.cci = None
    
    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'constant': self.constant
        }
    
    def set_parameters(self, period: int = None):
        """
        更新参数设置（会重置指标状态）
        
        Args:
            period: CCI计算周期
        """
        if period is not None:
            self.period = period
        
        # 重置状态
        self.reset()


class CCIAnalyzer:
    """
    CCI分析器，提供买卖信号和趋势分析
    """
    
    def __init__(self, cci_indicator: CCIIndicator):
        self.cci = cci_indicator
        self.previous_cci = None
    
    def get_signal(self, overbought: float = 100, oversold: float = -100) -> str:
        """
        获取交易信号
        
        Args:
            overbought: 超买阈值，默认100
            oversold: 超卖阈值，默认-100
            
        Returns:
            'BUY': 买入信号（CCI从超卖区域反弹）
            'SELL': 卖出信号（CCI从超买区域回落）
            'HOLD': 持有信号
        """
        current = self.cci.get_current_values()
        
        if current['cci'] is None:
            return 'HOLD'
        
        current_cci = current['cci']
        
        if self.previous_cci is None:
            self.previous_cci = current_cci
            return 'HOLD'
        
        # CCI从超卖区域向上穿越超卖线 - 买入信号
        if self.previous_cci <= oversold and current_cci > oversold:
            self.previous_cci = current_cci
            return 'BUY'
        
        # CCI从超买区域向下穿越超买线 - 卖出信号
        elif self.previous_cci >= overbought and current_cci < overbought:
            self.previous_cci = current_cci
            return 'SELL'
        
        self.previous_cci = current_cci
        return 'HOLD'
    
    def get_momentum_level(self) -> str:
        """
        获取动量水平
        
        Returns:
            'STRONG_OVERBOUGHT': 强烈超买（CCI > 200）
            'OVERBOUGHT': 超买（CCI > 100）
            'BULLISH': 看涨（CCI > 0）
            'NEUTRAL': 中性（CCI在-100到100之间）
            'BEARISH': 看跌（CCI < 0）
            'OVERSOLD': 超卖（CCI < -100）
            'STRONG_OVERSOLD': 强烈超卖（CCI < -200）
        """
        current = self.cci.get_current_values()
        
        if current['cci'] is None:
            return 'UNKNOWN'
        
        cci_value = current['cci']
        
        if cci_value > 200:
            return 'STRONG_OVERBOUGHT'
        elif cci_value > 100:
            return 'OVERBOUGHT'
        elif cci_value > 0:
            return 'BULLISH'
        elif cci_value < -200:
            return 'STRONG_OVERSOLD'
        elif cci_value < -100:
            return 'OVERSOLD'
        elif cci_value < 0:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def get_trend_direction(self) -> str:
        """
        获取趋势方向
        
        Returns:
            'UPTREND': 上升趋势（CCI > 0且上升）
            'DOWNTREND': 下降趋势（CCI < 0且下降）
            'NEUTRAL': 中性
        """
        current = self.cci.get_current_values()
        
        if current['cci'] is None or self.previous_cci is None:
            return 'NEUTRAL'
        
        current_cci = current['cci']
        
        # CCI在零轴上方且上升
        if current_cci > 0 and current_cci > self.previous_cci:
            return 'UPTREND'
        # CCI在零轴下方且下降
        elif current_cci < 0 and current_cci < self.previous_cci:
            return 'DOWNTREND'
        else:
            return 'NEUTRAL'
    
    def detect_divergence(self, prices: List[float], cci_values: List[float], lookback: int = 5) -> str:
        """
        检测CCI背离信号
        
        Args:
            prices: 价格序列
            cci_values: CCI值序列
            lookback: 回看周期
            
        Returns:
            'BULLISH_DIVERGENCE': 看涨背离（价格下跌但CCI上升）
            'BEARISH_DIVERGENCE': 看跌背离（价格上涨但CCI下降）
            'NO_DIVERGENCE': 无背离
        """
        if len(prices) < lookback or len(cci_values) < lookback:
            return 'NO_DIVERGENCE'
        
        # 获取最近的数据
        recent_prices = prices[-lookback:]
        recent_cci = cci_values[-lookback:]
        
        # 计算趋势
        price_trend = recent_prices[-1] - recent_prices[0]
        cci_trend = recent_cci[-1] - recent_cci[0]
        
        # 看涨背离：价格下跌但CCI上升
        if price_trend < 0 and cci_trend > 0:
            return 'BULLISH_DIVERGENCE'
        
        # 看跌背离：价格上涨但CCI下降
        elif price_trend > 0 and cci_trend < 0:
            return 'BEARISH_DIVERGENCE'
        
        return 'NO_DIVERGENCE'

