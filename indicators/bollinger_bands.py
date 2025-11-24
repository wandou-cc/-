"""
布林带(Bollinger Bands)指标实现
基于TradingView的标准实现，支持实时计算和参数配置

布林带是一个非常实用的技术分析指标，由三条线组成：
- 中轨线：简单移动平均线(SMA)
- 上轨线：中轨线 + (标准差 × 倍数)
- 下轨线：中轨线 - (标准差 × 倍数)

使用场景：
1. 价格触及上轨 → 可能超买，考虑卖出
2. 价格触及下轨 → 可能超卖，考虑买入
3. 布林带收窄(Squeeze) → 波动率降低，可能即将突破
4. 布林带扩张 → 波动率增加，趋势可能加强

注意：K线数据如果是倒序的（最新的在前），使用前需要先反转：klines.reverse()
"""

import numpy as np
from typing import List, Dict, Any


class BollingerBandsIndicator:
    """
    布林带指标计算类（TradingView标准）

    布林带包含三条线：
    1. 中轨线 = SMA(20) - 简单移动平均线（符合TradingView标准）
    2. 上轨线 = 中轨线 + (标准差 × 2)
    3. 下轨线 = 中轨线 - (标准差 × 2)

    附加指标：
    - %B：价格在布林带中的位置，范围0-1（可能超出）
    - BandWidth：带宽，衡量波动率大小
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        """
        初始化布林带指标参数

        Args:
            period: SMA周期，默认20
            std_dev: 标准差倍数，默认2.0
        """
        if period <= 0:
            raise ValueError("period必须大于0")
        if std_dev <= 0:
            raise ValueError("std_dev必须大于0")

        self.period = period
        self.std_dev = std_dev

        # 存储历史数据用于增量计算（限制长度防止内存泄漏）
        self.price_history = []
        self.max_history_length = period + 100  # 保留额外100个数据点用于分析

        # 当前指标值
        self.sma = None
        self.upper_band = None
        self.lower_band = None
        self.bandwidth = None
        self.percent_b = None
        self.current_std = None  # 当前标准差
    
    def _validate_prices(self, prices: List[float]) -> None:
        """
        验证价格数据的有效性

        Args:
            prices: 价格序列

        Raises:
            ValueError: 如果价格数据无效
        """
        if not prices:
            raise ValueError("价格数据不能为空")

        if len(prices) < self.period:
            raise ValueError(f"价格数据长度不足，至少需要{self.period}个数据点，当前只有{len(prices)}个")

        # 检查是否有无效数据
        for i, price in enumerate(prices):
            if price is None or np.isnan(price) or np.isinf(price):
                raise ValueError(f"价格数据包含无效值，索引{i}的值为{price}")
            if price < 0:
                raise ValueError(f"价格不能为负数，索引{i}的值为{price}")

    def calculate(self, prices: List[float]) -> Dict[str, List[float]]:
        """
        计算完整的布林带指标（使用SMA，符合TradingView标准）

        Args:
            prices: 价格序列（通常是收盘价）
                   注意：如果K线是倒序的，需要先反转再传入

        Returns:
            包含上轨、中轨、下轨、带宽、%B、标准差的字典
            {
                'upper_band': 上轨线列表,
                'middle_band': 中轨线(SMA)列表,
                'lower_band': 下轨线列表,
                'bandwidth': 带宽列表（衡量波动率），
                'percent_b': %B列表（价格在布林带中的相对位置），
                'std_dev': 标准差列表
            }

        Raises:
            ValueError: 如果价格数据无效或长度不足
        """
        # 验证输入数据
        self._validate_prices(prices)

        # 初始化结果列表
        upper_band = []
        middle_band = []
        lower_band = []
        percent_b = []
        bandwidth = []
        std_dev_list = []

        # 从第period个数据点开始计算
        for i in range(self.period - 1, len(prices)):
            # 获取当前窗口的价格
            window_prices = prices[i - self.period + 1:i + 1]

            # 计算SMA（中轨线）- TradingView标准
            current_sma = sum(window_prices) / self.period

            # 计算当前窗口的标准差（总体标准差，除以N而非N-1）
            variance = sum((price - current_sma) ** 2 for price in window_prices) / self.period
            std = np.sqrt(variance)

            # 计算上下轨
            upper = current_sma + self.std_dev * std
            lower = current_sma - self.std_dev * std

            # 计算%B（价格在布林带中的相对位置）
            current_price = prices[i]
            if upper != lower:
                pb = (current_price - lower) / (upper - lower)
            else:
                pb = 0.5  # 如果上下轨相同，%B为0.5

            # 计算带宽（相对于中轨的百分比）
            if current_sma != 0:
                bw = (upper - lower) / current_sma
            else:
                bw = 0

            # 添加到结果列表
            upper_band.append(upper)
            middle_band.append(current_sma)
            lower_band.append(lower)
            percent_b.append(pb)
            bandwidth.append(bw)
            std_dev_list.append(std)

        return {
            'upper_band': upper_band,
            'middle_band': middle_band,
            'lower_band': lower_band,
            'bandwidth': bandwidth,
            'percent_b': percent_b,
            'std_dev': std_dev_list
        }
    
    def update(self, new_price: float) -> Dict[str, float]:
        """
        实时更新布林带指标（使用SMA，符合TradingView标准）
        适用于逐根K线更新的场景

        Args:
            new_price: 新的价格值

        Returns:
            当前时刻的布林带值，如果数据不足返回None值
            {
                'upper_band': 上轨线,
                'middle_band': 中轨线(SMA),
                'lower_band': 下轨线,
                'bandwidth': 带宽,
                'percent_b': %B值,
                'std_dev': 标准差
            }

        Raises:
            ValueError: 如果价格无效
        """
        # 验证新价格
        if new_price is None or np.isnan(new_price) or np.isinf(new_price):
            raise ValueError(f"价格数据无效: {new_price}")
        if new_price < 0:
            raise ValueError(f"价格不能为负数: {new_price}")

        # 添加新价格到历史数据
        self.price_history.append(new_price)

        # 限制历史数据长度，防止内存泄漏
        if len(self.price_history) > self.max_history_length:
            self.price_history = self.price_history[-self.max_history_length:]

        # 如果数据不足，返回None
        if len(self.price_history) < self.period:
            return {
                'upper_band': None,
                'middle_band': None,
                'lower_band': None,
                'bandwidth': None,
                'percent_b': None,
                'std_dev': None
            }

        # 计算当前窗口的数据
        current_prices = self.price_history[-self.period:]

        # 计算SMA（中轨线）- TradingView标准
        self.sma = sum(current_prices) / self.period

        # 计算标准差（总体标准差，除以N而非N-1）
        variance = sum((price - self.sma) ** 2 for price in current_prices) / self.period
        self.current_std = np.sqrt(variance)

        # 计算上下轨
        self.upper_band = self.sma + self.std_dev * self.current_std
        self.lower_band = self.sma - self.std_dev * self.current_std

        # 计算%B
        if self.upper_band != self.lower_band:
            self.percent_b = (new_price - self.lower_band) / (self.upper_band - self.lower_band)
        else:
            self.percent_b = 0.5

        # 计算带宽
        if self.sma != 0:
            self.bandwidth = (self.upper_band - self.lower_band) / self.sma
        else:
            self.bandwidth = 0

        return {
            'upper_band': self.upper_band,
            'middle_band': self.sma,
            'lower_band': self.lower_band,
            'bandwidth': self.bandwidth,
            'percent_b': self.percent_b,
            'std_dev': self.current_std
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """
        获取当前的布林带值

        Returns:
            当前时刻的布林带值
        """
        return {
            'upper_band': self.upper_band,
            'middle_band': self.sma,
            'lower_band': self.lower_band,
            'bandwidth': self.bandwidth,
            'percent_b': self.percent_b,
            'std_dev': self.current_std
        }
    
    def reset(self):
        """重置指标状态，清空所有历史数据"""
        self.price_history = []
        self.sma = None
        self.upper_band = None
        self.lower_band = None
        self.bandwidth = None
        self.percent_b = None
        self.current_std = None
    
    def get_parameters(self) -> Dict[str, Any]:
        """获取当前参数设置"""
        return {
            'period': self.period,
            'std_dev': self.std_dev
        }
    
    def set_parameters(self, period: int = None, std_dev: float = None):
        """
        更新参数设置（会重置指标状态）
        
        Args:
            period: 移动平均线周期
            std_dev: 标准差倍数
        """
        if period is not None:
            self.period = period
        
        if std_dev is not None:
            self.std_dev = std_dev
        
        # 重置状态
        self.reset()


class BollingerBandsAnalyzer:
    """
    布林带分析器，提供买卖信号和趋势分析

    功能：
    1. 买卖信号识别（触及上下轨）
    2. 波动率分析（带宽）
    3. 价格位置分析（%B）
    4. 布林带挤压检测（Bollinger Squeeze）
    """

    def __init__(self, bb_indicator: BollingerBandsIndicator, squeeze_threshold: float = 0.05):
        """
        初始化分析器

        Args:
            bb_indicator: 布林带指标实例
            squeeze_threshold: 挤压阈值，当带宽小于此值时认为是挤压状态，默认0.05
        """
        self.bb = bb_indicator
        self.previous_values = None
        self.squeeze_threshold = squeeze_threshold
        self.bandwidth_history = []  # 用于检测挤压突破
    
    def update(self, new_price: float) -> None:
        """
        更新分析器状态

        Args:
            new_price: 新的价格数据
        """
        # 保存之前的值
        self.previous_values = self.bb.get_current_values()

        # 更新布林带
        current = self.bb.update(new_price)

        # 更新带宽历史（用于挤压检测）
        if current['bandwidth'] is not None:
            self.bandwidth_history.append(current['bandwidth'])
            # 限制历史长度
            if len(self.bandwidth_history) > 50:
                self.bandwidth_history = self.bandwidth_history[-50:]

    def get_signal(self) -> str:
        """
        获取交易信号

        Returns:
            'BUY': 买入信号（价格触及或突破下轨）
            'SELL': 卖出信号（价格触及或突破上轨）
            'HOLD': 持有信号
        """
        current = self.bb.get_current_values()

        if current['upper_band'] is None or current['lower_band'] is None:
            return 'HOLD'

        if not self.bb.price_history:
            return 'HOLD'

        current_price = self.bb.price_history[-1]

        # 价格触及或突破下轨 - 买入信号（允许1%误差）
        if current_price <= current['lower_band'] * 1.01:
            return 'BUY'

        # 价格触及或突破上轨 - 卖出信号（允许1%误差）
        elif current_price >= current['upper_band'] * 0.99:
            return 'SELL'

        return 'HOLD'
    
    def get_volatility_level(self) -> str:
        """
        获取波动率水平

        Returns:
            'HIGH': 高波动率（带宽较大）
            'MEDIUM': 中等波动率
            'LOW': 低波动率（带宽较小）
            'UNKNOWN': 数据不足
        """
        current = self.bb.get_current_values()

        if current['bandwidth'] is None:
            return 'UNKNOWN'

        bandwidth = current['bandwidth']

        # 根据带宽判断波动率（这些阈值可以根据实际情况调整）
        if bandwidth > 0.1:
            return 'HIGH'
        elif bandwidth > 0.05:
            return 'MEDIUM'
        else:
            return 'LOW'

    def is_squeeze(self) -> bool:
        """
        检测是否处于布林带挤压状态（Bollinger Squeeze）

        布林带挤压表示波动率极低，通常预示着即将发生大的价格波动。
        这是一个非常重要的交易信号。

        Returns:
            True: 当前处于挤压状态
            False: 不处于挤压状态
        """
        current = self.bb.get_current_values()

        if current['bandwidth'] is None:
            return False

        # 当带宽小于阈值时，认为是挤压状态
        return current['bandwidth'] < self.squeeze_threshold

    def detect_squeeze_breakout(self) -> str:
        """
        检测布林带挤压突破

        Returns:
            'BREAKOUT_UP': 向上突破挤压
            'BREAKOUT_DOWN': 向下突破挤压
            'SQUEEZE': 处于挤压中
            'NORMAL': 正常状态
        """
        if len(self.bandwidth_history) < 3:
            return 'NORMAL'

        current = self.bb.get_current_values()
        if current['bandwidth'] is None or current['percent_b'] is None:
            return 'NORMAL'

        # 检查是否刚从挤压状态突破
        was_squeeze = self.bandwidth_history[-2] < self.squeeze_threshold
        is_squeeze = current['bandwidth'] < self.squeeze_threshold

        # 如果当前还在挤压中
        if is_squeeze:
            return 'SQUEEZE'

        # 如果刚刚突破挤压
        if was_squeeze and not is_squeeze:
            # 根据%B判断突破方向
            if current['percent_b'] > 0.8:
                return 'BREAKOUT_UP'
            elif current['percent_b'] < 0.2:
                return 'BREAKOUT_DOWN'

        return 'NORMAL'
    
    def get_price_position(self) -> str:
        """
        获取价格在布林带中的位置
        
        Returns:
            'ABOVE_UPPER': 价格在上轨之上
            'UPPER_ZONE': 价格在上轨附近
            'MIDDLE_ZONE': 价格在中轨附近
            'LOWER_ZONE': 价格在下轨附近
            'BELOW_LOWER': 价格在下轨之下
        """
        current = self.bb.get_current_values()
        
        if current['percent_b'] is None:
            return 'UNKNOWN'
        
        percent_b = current['percent_b']
        
        if percent_b > 1.0:
            return 'ABOVE_UPPER'
        elif percent_b > 0.8:
            return 'UPPER_ZONE'
        elif percent_b < 0.0:
            return 'BELOW_LOWER'
        elif percent_b < 0.2:
            return 'LOWER_ZONE'
        else:
            return 'MIDDLE_ZONE'
