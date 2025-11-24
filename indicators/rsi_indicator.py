"""
RSI (Relative Strength Index) 指标实现
基于TradingView的标准实现，支持实时计算和参数配置
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any


class RSIIndicator:
    """
    RSI指标计算类（使用EMA方法，符合TradingView标准）
    
    RSI计算公式：
    RSI = 100 - (100 / (1 + RS))
    其中 RS = 平均涨幅 / 平均跌幅
    
    默认使用EMA（指数移动平均）方法计算平均涨跌幅：
    - 初始值：使用前N期的SMA
    - 后续值：EMA = α × 当前值 + (1-α) × 前一期EMA
    - α = 1 / period
    """
    
    def __init__(self, period: int = 14, use_ema: bool = True):
        """
        初始化RSI指标参数
        
        Args:
            period: RSI计算周期，默认14
            use_ema: 是否使用EMA方法（默认True，符合TradingView标准）
        """
        self.period = period
        self.use_ema = use_ema
        
        # 存储历史数据用于增量计算
        self.price_history = []
        self.gains = []
        self.losses = []
        self.avg_gain = None
        self.avg_loss = None
        self.rsi = None
        
        # 存储前一个价格用于计算涨跌幅
        self.previous_price = None
        
        # EMA的alpha值
        self.alpha = 1.0 / period if use_ema else None
    
    def _calculate_price_changes(self, prices: List[float]) -> Tuple[List[float], List[float]]:
        """
        计算价格变化（涨幅和跌幅）
        
        Args:
            prices: 价格序列
            
        Returns:
            (涨幅列表, 跌幅列表)
        """
        if len(prices) < 2:
            return [], []
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        return gains, losses
    
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
    
    def _calculate_ema(self, values: List[float], alpha: float) -> List[float]:
        """
        计算指数移动平均线（用于平滑RSI）
        
        Args:
            values: 数值序列
            alpha: EMA的平滑因子
            
        Returns:
            EMA值序列
        """
        if not values:
            return []
        
        ema_values = []
        ema = values[0]  # 第一个值作为初始EMA
        
        for value in values:
            ema = alpha * value + (1 - alpha) * ema
            ema_values.append(ema)
        
        return ema_values
    
    def calculate(self, prices: List[float]) -> Dict[str, List[float]]:
        """
        计算完整的RSI指标
        
        Args:
            prices: 价格序列（通常是收盘价）
            
        Returns:
            包含RSI值的字典
        """
        if len(prices) < self.period + 1:
            raise ValueError(f"价格数据长度不足，至少需要{self.period + 1}个数据点")
        
        # 计算价格变化
        gains, losses = self._calculate_price_changes(prices)
        
        if len(gains) < self.period:
            raise ValueError(f"价格变化数据不足，至少需要{self.period}个数据点")
        
        if self.use_ema:
            # 使用EMA方法（TradingView标准）
            alpha = 1.0 / self.period
            
            # 计算初始平均涨幅和跌幅（使用SMA）
            initial_avg_gain = sum(gains[:self.period]) / self.period
            initial_avg_loss = sum(losses[:self.period]) / self.period
            
            # 使用EMA计算后续的平均涨幅和跌幅
            avg_gains = [initial_avg_gain]
            avg_losses = [initial_avg_loss]
            
            for i in range(self.period, len(gains)):
                avg_gain = alpha * gains[i] + (1 - alpha) * avg_gains[-1]
                avg_loss = alpha * losses[i] + (1 - alpha) * avg_losses[-1]
                avg_gains.append(avg_gain)
                avg_losses.append(avg_loss)
            
            # 计算RSI
            rsi_values = []
            for avg_gain, avg_loss in zip(avg_gains, avg_losses):
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)
        
        else:
            # 使用SMA方法
            avg_gains = self._calculate_sma(gains, self.period)
            avg_losses = self._calculate_sma(losses, self.period)
            
            # 计算RSI
            rsi_values = []
            for avg_gain, avg_loss in zip(avg_gains, avg_losses):
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)
        
        return {
            'rsi': rsi_values,
            'avg_gain': avg_gains,
            'avg_loss': avg_losses
        }
    
    def update(self, new_price: float) -> Dict[str, float]:
        """
        实时更新RSI指标
        
        Args:
            new_price: 新的价格值
            
        Returns:
            当前时刻的RSI值
        """
        # 添加新价格到历史数据
        self.price_history.append(new_price)
        
        # 如果数据不足，返回None
        if len(self.price_history) < self.period + 1:
            return {
                'rsi': None,
                'avg_gain': None,
                'avg_loss': None
            }
        
        # 计算价格变化
        if self.previous_price is not None:
            change = new_price - self.previous_price
            
            if change > 0:
                gain = change
                loss = 0
            else:
                gain = 0
                loss = abs(change)
            
            self.gains.append(gain)
            self.losses.append(loss)
        
        self.previous_price = new_price
        
        # 如果数据不足，返回None
        if len(self.gains) < self.period:
            return {
                'rsi': None,
                'avg_gain': None,
                'avg_loss': None
            }
        
        # 计算平均涨幅和跌幅
        if self.avg_gain is None:
            # 初始化：计算前period个数据的平均值（使用SMA）
            self.avg_gain = sum(self.gains[:self.period]) / self.period
            self.avg_loss = sum(self.losses[:self.period]) / self.period
        else:
            # 增量更新
            if self.use_ema:
                # 使用EMA方法（TradingView标准）
                self.avg_gain = self.alpha * self.gains[-1] + (1 - self.alpha) * self.avg_gain
                self.avg_loss = self.alpha * self.losses[-1] + (1 - self.alpha) * self.avg_loss
            else:
                # 使用SMA方法
                recent_gains = self.gains[-self.period:]
                recent_losses = self.losses[-self.period:]
                self.avg_gain = sum(recent_gains) / self.period
                self.avg_loss = sum(recent_losses) / self.period
        
        # 计算RSI
        if self.avg_loss == 0:
            self.rsi = 100
        else:
            rs = self.avg_gain / self.avg_loss
            self.rsi = 100 - (100 / (1 + rs))
        
        return {
            'rsi': self.rsi,
            'avg_gain': self.avg_gain,
            'avg_loss': self.avg_loss
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """
        获取当前的RSI值
        
        Returns:
            当前时刻的RSI值
        """
        return {
            'rsi': self.rsi,
            'avg_gain': self.avg_gain,
            'avg_loss': self.avg_loss
        }
    
    def reset(self):
        """重置指标状态"""
        self.price_history = []
        self.gains = []
        self.losses = []
        self.avg_gain = None
        self.avg_loss = None
        self.rsi = None
        self.previous_price = None
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'use_ema': self.use_ema
        }
    
    def set_parameters(self, period: int = None, use_ema: bool = None):
        """
        更新参数设置（会重置指标状态）
        
        Args:
            period: RSI计算周期
            use_ema: 是否使用EMA方法
        """
        if period is not None:
            self.period = period
            if self.use_ema:
                self.alpha = 1.0 / period
        
        if use_ema is not None:
            self.use_ema = use_ema
            self.alpha = 1.0 / self.period if use_ema else None
        
        # 重置状态
        self.reset()


class RSIAnalyzer:
    """
    RSI分析器，提供买卖信号和趋势分析
    """

    def __init__(self, rsi_indicator: RSIIndicator, overbought: float = 70, oversold: float = 30):
        """
        初始化RSI分析器

        Args:
            rsi_indicator: RSI指标实例
            overbought: 超买阈值，默认70
            oversold: 超卖阈值，默认30
        """
        self.rsi = rsi_indicator
        self.previous_rsi = None
        self.overbought = overbought
        self.oversold = oversold
    
    def get_signal(self) -> str:
        """
        获取交易信号

        Returns:
            'BUY': 买入信号（RSI从超卖区域反弹）
            'SELL': 卖出信号（RSI从超买区域回落）
            'HOLD': 持有信号
        """
        current = self.rsi.get_current_values()

        if current['rsi'] is None:
            return 'HOLD'

        current_rsi = current['rsi']

        if self.previous_rsi is None:
            self.previous_rsi = current_rsi
            return 'HOLD'

        # RSI从超卖区域反弹 - 买入信号
        if self.previous_rsi <= self.oversold and current_rsi > self.oversold:
            self.previous_rsi = current_rsi
            return 'BUY'

        # RSI从超买区域回落 - 卖出信号
        elif self.previous_rsi >= self.overbought and current_rsi < self.overbought:
            self.previous_rsi = current_rsi
            return 'SELL'

        self.previous_rsi = current_rsi
        return 'HOLD'
    
    def get_momentum_level(self) -> str:
        """
        获取动量水平

        Returns:
            'OVERBOUGHT': 超买（RSI > 超买阈值）
            'BULLISH': 看涨（RSI > 50）
            'NEUTRAL': 中性（RSI在超卖和超买阈值之间）
            'BEARISH': 看跌（RSI < 50）
            'OVERSOLD': 超卖（RSI < 超卖阈值）
        """
        current = self.rsi.get_current_values()

        if current['rsi'] is None:
            return 'UNKNOWN'

        rsi_value = current['rsi']

        if rsi_value > self.overbought:
            return 'OVERBOUGHT'
        elif rsi_value > 50:
            return 'BULLISH'
        elif rsi_value < self.oversold:
            return 'OVERSOLD'
        elif rsi_value < 50:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def get_divergence_signal(self, prices: List[float], lookback: int = 5) -> str:
        """
        检测RSI背离信号
        
        Args:
            prices: 价格序列（需要包含足够的历史数据）
            lookback: 回看周期
            
        Returns:
            'BULLISH_DIVERGENCE': 看涨背离
            'BEARISH_DIVERGENCE': 看跌背离
            'NO_DIVERGENCE': 无背离
        """
        # 需要足够的数据来计算RSI
        min_required = self.rsi.period + lookback + 1
        if len(prices) < min_required:
            return 'NO_DIVERGENCE'
        
        # 重新计算RSI以获取历史值
        try:
            temp_rsi = RSIIndicator(self.rsi.period, self.rsi.use_ema)
            temp_result = temp_rsi.calculate(prices)
            
            if len(temp_result['rsi']) < lookback:
                return 'NO_DIVERGENCE'
            
            # 获取最近的价格和RSI值
            recent_prices = prices[-lookback:]
            recent_rsi_values = temp_result['rsi'][-lookback:]
            
            # 检测背离
            price_trend = recent_prices[-1] - recent_prices[0]
            rsi_trend = recent_rsi_values[-1] - recent_rsi_values[0]
            
            # 看涨背离：价格下跌但RSI上升
            if price_trend < 0 and rsi_trend > 0:
                return 'BULLISH_DIVERGENCE'
            
            # 看跌背离：价格上涨但RSI下降
            elif price_trend > 0 and rsi_trend < 0:
                return 'BEARISH_DIVERGENCE'
            
        except Exception:
            return 'NO_DIVERGENCE'

        return 'NO_DIVERGENCE'

    def get_comprehensive_analysis(self) -> Dict[str, Any]:
        """
        获取综合分析结果

        Returns:
            包含RSI值、动量水平、交易信号等的综合分析字典
        """
        current = self.rsi.get_current_values()

        return {
            'rsi': current['rsi'],
            'avg_gain': current['avg_gain'],
            'avg_loss': current['avg_loss'],
            'momentum_level': self.get_momentum_level(),
            'signal': self.get_signal(),
            'is_overbought': current['rsi'] > self.overbought if current['rsi'] is not None else False,
            'is_oversold': current['rsi'] < self.oversold if current['rsi'] is not None else False,
            'overbought_threshold': self.overbought,
            'oversold_threshold': self.oversold
        }

    def set_thresholds(self, overbought: float = None, oversold: float = None):
        """
        设置超买超卖阈值

        Args:
            overbought: 超买阈值
            oversold: 超卖阈值
        """
        if overbought is not None:
            self.overbought = overbought
        if oversold is not None:
            self.oversold = oversold
