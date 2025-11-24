"""
MACD (Moving Average Convergence Divergence) 指标实现
基于TradingView的标准实现，支持实时计算和参数配置
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import pandas as pd


class MACDIndicator:
    """
    MACD指标计算类
    
    MACD指标包含三个主要组成部分：
    1. MACD线 = EMA(12) - EMA(26)
    2. 信号线 = EMA(9) of MACD线
    3. 柱状图 = MACD线 - 信号线
    """
    
    def __init__(self, 
                 fast_period: int = 12, 
                 slow_period: int = 26, 
                 signal_period: int = 9):
        """
        初始化MACD指标参数
        
        Args:
            fast_period: 快速EMA周期，默认12
            slow_period: 慢速EMA周期，默认26
            signal_period: 信号线EMA周期，默认9
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
        # 存储历史数据用于增量计算
        self.price_history = []
        self.ema_fast = None
        self.ema_slow = None
        self.macd_line = None
        self.signal_line = None
        self.histogram = None
        
        # 存储EMA的alpha值
        self.alpha_fast = 2.0 / (fast_period + 1)
        self.alpha_slow = 2.0 / (slow_period + 1)
        self.alpha_signal = 2.0 / (signal_period + 1)
    
    def _validate_price(self, price: float) -> bool:
        """
        验证价格有效性

        Args:
            price: 价格值

        Returns:
            是否有效
        """
        if price is None or not isinstance(price, (int, float)):
            return False
        if np.isnan(price) or np.isinf(price) or price <= 0:
            return False
        return True

    def _calculate_ema(self, prices: List[float], period: int, alpha: float) -> List[float]:
        """
        计算指数移动平均线(EMA) - 符合TradingView标准

        Args:
            prices: 价格序列
            period: EMA周期（用于计算初始SMA）
            alpha: EMA的平滑因子

        Returns:
            EMA值序列
        """
        if not prices:
            return []

        if len(prices) < period:
            return []

        ema_values = []
        # 使用前period个数据的SMA作为初始EMA（TradingView标准）
        ema = sum(prices[:period]) / period

        # 从第period个数据开始计算EMA
        for i in range(period - 1, len(prices)):
            if i == period - 1:
                ema_values.append(ema)
            else:
                ema = alpha * prices[i] + (1 - alpha) * ema
                ema_values.append(ema)

        return ema_values
    
    def _calculate_ema_incremental(self, new_price: float, current_ema: float, alpha: float) -> float:
        """
        增量计算EMA（用于实时更新）
        
        Args:
            new_price: 新的价格值
            current_ema: 当前的EMA值
            alpha: EMA的平滑因子
            
        Returns:
            更新后的EMA值
        """
        return alpha * new_price + (1 - alpha) * current_ema
    
    def calculate(self, prices: List[float]) -> Dict[str, List[float]]:
        """
        计算完整的MACD指标

        Args:
            prices: 价格序列（通常是收盘价）

        Returns:
            包含MACD线、信号线、柱状图的字典
        """
        # 验证输入数据
        for price in prices:
            if not self._validate_price(price):
                raise ValueError(f"无效的价格数据: {price}")

        if len(prices) < self.slow_period:
            raise ValueError(f"价格数据长度不足，至少需要{self.slow_period}个数据点")

        # 计算快速和慢速EMA（传入周期参数）
        ema_fast = self._calculate_ema(prices, self.fast_period, self.alpha_fast)
        ema_slow = self._calculate_ema(prices, self.slow_period, self.alpha_slow)

        # 对齐数据：ema_slow 比 ema_fast 晚开始
        # 需要补齐 ema_fast，使其与 ema_slow 长度一致
        offset = len(ema_fast) - len(ema_slow)
        if offset > 0:
            ema_fast = ema_fast[offset:]

        # 计算MACD线
        macd_line = [fast - slow for fast, slow in zip(ema_fast, ema_slow)]

        # 计算信号线（MACD线的EMA）
        signal_line = self._calculate_ema(macd_line, self.signal_period, self.alpha_signal)

        # 对齐MACD线和信号线
        offset = len(macd_line) - len(signal_line)
        if offset > 0:
            macd_line = macd_line[offset:]
            ema_fast = ema_fast[offset:]
            ema_slow = ema_slow[offset:]

        # 计算柱状图
        histogram = [macd - signal for macd, signal in zip(macd_line, signal_line)]

        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow
        }
    
    def update(self, new_price: float) -> Dict[str, float]:
        """
        实时更新MACD指标（增量计算）

        Args:
            new_price: 新的价格值

        Returns:
            当前时刻的MACD值
        """
        # 验证输入
        if not self._validate_price(new_price):
            raise ValueError(f"无效的价格数据: {new_price}")

        # 添加新价格到历史数据
        self.price_history.append(new_price)

        # 限制历史数据长度，防止内存泄漏
        # 保留 slow_period + 100 个数据点用于验证和调试
        max_history = self.slow_period + 100
        if len(self.price_history) > max_history:
            self.price_history.pop(0)

        # 如果数据不足，返回None
        if len(self.price_history) < self.slow_period:
            return {
                'macd_line': None,
                'signal_line': None,
                'histogram': None,
                'ema_fast': None,
                'ema_slow': None
            }

        # 更新EMA值
        if self.ema_fast is None:
            # 初始化：计算所有历史数据的EMA
            result = self.calculate(self.price_history)
            if not result['ema_fast'] or not result['macd_line']:
                # 数据仍然不足，返回 None
                return {
                    'macd_line': None,
                    'signal_line': None,
                    'histogram': None,
                    'ema_fast': None,
                    'ema_slow': None
                }
            self.ema_fast = result['ema_fast'][-1]
            self.ema_slow = result['ema_slow'][-1]
            self.macd_line = result['macd_line'][-1]
            self.signal_line = result['signal_line'][-1]
            self.histogram = result['histogram'][-1]
        else:
            # 增量更新
            self.ema_fast = self._calculate_ema_incremental(new_price, self.ema_fast, self.alpha_fast)
            self.ema_slow = self._calculate_ema_incremental(new_price, self.ema_slow, self.alpha_slow)
            self.macd_line = self.ema_fast - self.ema_slow
            self.signal_line = self._calculate_ema_incremental(self.macd_line, self.signal_line, self.alpha_signal)
            self.histogram = self.macd_line - self.signal_line

        return {
            'macd_line': self.macd_line,
            'signal_line': self.signal_line,
            'histogram': self.histogram,
            'ema_fast': self.ema_fast,
            'ema_slow': self.ema_slow
        }
    
    def get_current_values(self) -> Dict[str, float]:
        """
        获取当前的MACD值
        
        Returns:
            当前时刻的MACD值
        """
        return {
            'macd_line': self.macd_line,
            'signal_line': self.signal_line,
            'histogram': self.histogram,
            'ema_fast': self.ema_fast,
            'ema_slow': self.ema_slow
        }
    
    def reset(self):
        """重置指标状态"""
        self.price_history = []
        self.ema_fast = None
        self.ema_slow = None
        self.macd_line = None
        self.signal_line = None
        self.histogram = None
    
    def get_parameters(self) -> Dict[str, int]:
        """获取当前参数设置"""
        return {
            'fast_period': self.fast_period,
            'slow_period': self.slow_period,
            'signal_period': self.signal_period
        }
    
    def set_parameters(self, fast_period: int = None, slow_period: int = None, signal_period: int = None):
        """
        更新参数设置（会重置指标状态）
        
        Args:
            fast_period: 快速EMA周期
            slow_period: 慢速EMA周期
            signal_period: 信号线EMA周期
        """
        if fast_period is not None:
            self.fast_period = fast_period
            self.alpha_fast = 2.0 / (fast_period + 1)
        
        if slow_period is not None:
            self.slow_period = slow_period
            self.alpha_slow = 2.0 / (slow_period + 1)
        
        if signal_period is not None:
            self.signal_period = signal_period
            self.alpha_signal = 2.0 / (signal_period + 1)
        
        # 重置状态
        self.reset()


class MACDAnalyzer:
    """
    MACD分析器，提供买卖信号和趋势分析（优化版，支持多维度过滤）
    """
    
    def __init__(self,
                 macd_indicator: MACDIndicator,
                 angle_multiplier: float = 0.5,
                 min_hist_threshold: float = 0.0005,
                 lookback_period: int = 50,
                 min_zero_distance: float = 0.0):
        """
        初始化MACD分析器

        Args:
            macd_indicator: MACD指标实例
            angle_multiplier: 角度阈值乘数（默认0.5）
            min_hist_threshold: 最小柱状图阈值（默认0.0005）
            lookback_period: 计算标准差的回溯周期（默认50）
            min_zero_distance: 距离0轴的最小距离（默认0.0，即不过滤）
                              例如设置为5.0，则MACD线和信号线必须距离0轴至少5.0才有效
                              只需配置正数，代码会自动处理正负值
        """
        self.macd = macd_indicator
        self.previous_values = None
        self.angle_multiplier = angle_multiplier
        self.min_hist_threshold = min_hist_threshold
        self.lookback_period = lookback_period
        self.min_zero_distance = abs(min_zero_distance)  # 确保是正数

        # 存储历史值用于计算斜率和标准差
        self.macd_history = []
        self.signal_history = []
        self.histogram_history = []
    
    def update_history(self, current_values: Dict[str, float]):
        """
        更新历史记录

        Args:
            current_values: 当前的MACD值
        """
        if current_values['macd_line'] is not None:
            self.macd_history.append(current_values['macd_line'])
            self.signal_history.append(current_values['signal_line'])
            self.histogram_history.append(current_values['histogram'])

            # 只保留需要的历史长度
            max_length = max(self.lookback_period, 10)
            if len(self.macd_history) > max_length:
                self.macd_history.pop(0)
                self.signal_history.pop(0)
                self.histogram_history.pop(0)

    def _detect_cross(self, current_values: Dict[str, float]) -> Optional[str]:
        """
        检测交叉类型（公共方法，避免重复代码）

        Args:
            current_values: 当前的MACD值

        Returns:
            'golden': 金叉
            'dead': 死叉
            None: 无交叉
        """
        if current_values['macd_line'] is None or current_values['signal_line'] is None:
            return None

        if self.previous_values is None:
            return None

        prev_macd = self.previous_values['macd_line']
        prev_signal = self.previous_values['signal_line']

        # 检查前一个值是否有效
        if prev_macd is None or prev_signal is None:
            return None

        curr_macd = current_values['macd_line']
        curr_signal = current_values['signal_line']

        # 检测金叉
        if prev_macd < prev_signal and curr_macd > curr_signal:
            return 'golden'
        # 检测死叉
        elif prev_macd > prev_signal and curr_macd < curr_signal:
            return 'dead'

        return None
    
    def _check_angle_condition(self) -> Tuple[bool, float]:
        """
        检查交叉角度条件（使用线性回归计算斜率，更稳健）

        Returns:
            (是否满足条件, 实际角度值)
        """
        lookback = 5  # 使用更多数据点减少噪音
        if len(self.macd_history) < lookback or len(self.signal_history) < lookback:
            return False, 0.0

        # 使用线性回归计算斜率（更稳健）
        x = np.arange(lookback)
        macd_recent = self.macd_history[-lookback:]
        signal_recent = self.signal_history[-lookback:]

        # 计算斜率：使用 numpy polyfit
        macd_slope = np.polyfit(x, macd_recent, 1)[0]
        signal_slope = np.polyfit(x, signal_recent, 1)[0]

        # 斜率差的绝对值
        angle = abs(macd_slope - signal_slope)

        # 计算动态阈值：使用MACD变化率的标准差
        if len(self.macd_history) >= self.lookback_period:
            # 计算差分的标准差（更合理）
            macd_diffs = np.diff(self.macd_history[-self.lookback_period:])
            std_dev = np.std(macd_diffs)
            threshold = std_dev * self.angle_multiplier
        else:
            # 数据不足时使用全部历史数据
            if len(self.macd_history) > 1:
                macd_diffs = np.diff(self.macd_history)
                std_dev = np.std(macd_diffs)
            else:
                std_dev = 1.0
            threshold = std_dev * self.angle_multiplier

        return angle > threshold, angle
    
    def _check_histogram_momentum(self, cross_type: str) -> bool:
        """
        检查柱状图动能条件（改进版，允许小幅波动）

        Args:
            cross_type: 'golden' 或 'dead'

        Returns:
            是否满足动能条件
        """
        lookback = 5
        if len(self.histogram_history) < lookback:
            return False

        hist = self.histogram_history[-lookback:]

        if cross_type == 'golden':
            # 金叉：总体趋势向上，允许个别回调
            # 计算递增次数
            increasing_count = sum(1 for i in range(len(hist)-1) if hist[i+1] > hist[i])
            # 5个数据点中至少3次递增即可
            return increasing_count >= 3
        elif cross_type == 'dead':
            # 死叉：总体趋势向下，允许个别反弹
            decreasing_count = sum(1 for i in range(len(hist)-1) if hist[i+1] < hist[i])
            # 5个数据点中至少3次递减即可
            return decreasing_count >= 3

        return False
    
    def _check_histogram_threshold(self) -> bool:
        """
        检查柱状图绝对值阈值（避免横盘噪音）

        Returns:
            是否满足阈值条件
        """
        if len(self.histogram_history) < 1:
            return False

        return abs(self.histogram_history[-1]) > self.min_hist_threshold

    def _check_zero_distance(self, current_values: Dict[str, float]) -> bool:
        """
        检查MACD线和信号线是否距离0轴足够远（过滤太靠近0轴的金叉死叉）

        Args:
            current_values: 当前的MACD值

        Returns:
            是否满足距离条件（True表示距离足够远，信号有效）
        """
        if self.min_zero_distance <= 0:
            # 如果阈值为0或负数，则不进行过滤
            return True

        macd = current_values['macd_line']
        signal = current_values['signal_line']

        if macd is None or signal is None:
            return False

        # 检查MACD线和信号线是否都距离0轴足够远
        # 只需要配置正数，这里自动处理正负值
        # 金叉：两条线都应该在零轴上方且大于阈值，或都在零轴下方且小于-阈值
        # 死叉：同理

        # 方法1：检查两条线中较接近0轴的那条是否满足距离要求
        # 这样可以确保交叉点不会太靠近0轴
        min_abs_value = min(abs(macd), abs(signal))

        return min_abs_value >= self.min_zero_distance
    
    def get_filtered_signal(self) -> Dict[str, Any]:
        """
        获取过滤后的交易信号（新版，支持多维度过滤和详细分类）

        Returns:
            包含详细信号信息的字典：
            {
                'signal': 信号类型 ('strong_golden', 'weak_golden', 'strong_dead', 'weak_dead', 'none'),
                'cross_detected': 是否检测到交叉,
                'conditions': {
                    'angle_check': 角度检查是否通过,
                    'momentum_check': 动能检查是否通过,
                    'threshold_check': 阈值检查是否通过,
                    'zero_distance_check': 0轴距离检查是否通过
                },
                'metrics': {
                    'angle': 实际角度值,
                    'histogram': 当前柱状图值,
                    'macd': 当前MACD值,
                    'signal': 当前信号线值,
                    'zero_distance': 距离0轴的最小距离
                }
            }
        """
        current = self.macd.get_current_values()

        # 更新历史记录
        self.update_history(current)

        # 计算距离0轴的最小距离
        macd_val = current['macd_line'] if current['macd_line'] is not None else 0.0
        signal_val = current['signal_line'] if current['signal_line'] is not None else 0.0
        zero_dist = min(abs(macd_val), abs(signal_val))

        # 默认返回值
        result = {
            'signal': 'none',
            'cross_detected': False,
            'conditions': {
                'angle_check': False,
                'momentum_check': False,
                'threshold_check': False,
                'zero_distance_check': False
            },
            'metrics': {
                'angle': 0.0,
                'histogram': current['histogram'] if current['histogram'] is not None else 0.0,
                'macd': macd_val,
                'signal': signal_val,
                'zero_distance': zero_dist
            }
        }

        # 使用公共方法检测交叉
        cross_type = self._detect_cross(current)

        if cross_type is None:
            if self.previous_values is None:
                self.previous_values = current
            else:
                self.previous_values = current
            return result

        # 检测到交叉
        result['cross_detected'] = True

        # 检查各项过滤条件
        angle_pass, angle_value = self._check_angle_condition()
        momentum_pass = self._check_histogram_momentum(cross_type)
        threshold_pass = self._check_histogram_threshold()
        zero_distance_pass = self._check_zero_distance(current)

        result['conditions']['angle_check'] = angle_pass
        result['conditions']['momentum_check'] = momentum_pass
        result['conditions']['threshold_check'] = threshold_pass
        result['conditions']['zero_distance_check'] = zero_distance_pass
        result['metrics']['angle'] = angle_value

        # 判断信号强度（现在有4个条件）
        conditions_met = sum([angle_pass, momentum_pass, threshold_pass, zero_distance_pass])
        if conditions_met == 4:
            result['signal'] = f'strong_{cross_type}'
        elif conditions_met >= 2:
            result['signal'] = f'weak_{cross_type}'
        else:
            result['signal'] = 'none'

        self.previous_values = current
        return result
    
    def get_signal(self, check_angle: bool = True) -> str:
        """
        获取交易信号（支持角度过滤，向后兼容的简化版本）

        Args:
            check_angle: 是否启用角度过滤，默认True（参数保留用于向后兼容，但不再使用）

        Returns:
            'BUY': 买入信号
            'SELL': 卖出信号
            'HOLD': 持有信号
        """
        current = self.macd.get_current_values()

        # 更新历史记录
        self.update_history(current)

        # 使用公共方法检测交叉
        cross_type = self._detect_cross(current)

        if cross_type is None:
            if self.previous_values is None:
                self.previous_values = current
            else:
                self.previous_values = current
            return 'HOLD'

        self.previous_values = current

        # 返回对应信号
        if cross_type == 'golden':
            return 'BUY'
        elif cross_type == 'dead':
            return 'SELL'

        return 'HOLD'
    
    def get_signal_with_strength(self, check_angle: bool = True) -> Dict[str, Any]:
        """
        获取交易信号及其强度信息（向后兼容版本）
        注意：min_cross_strength 已移除，此方法现在仅检测交叉，不再计算强度

        Args:
            check_angle: 是否启用角度过滤（参数保留用于向后兼容，但不再使用）

        Returns:
            包含信号和强度的字典
        """
        current = self.macd.get_current_values()

        # 更新历史记录
        self.update_history(current)

        # 使用公共方法检测交叉
        cross_type = self._detect_cross(current)

        if cross_type is None:
            if self.previous_values is None:
                self.previous_values = current
            return {'signal': 'HOLD', 'strength': 0, 'valid': True}

        self.previous_values = current

        # 根据交叉类型返回信号
        signal_map = {
            'golden': 'BUY',
            'dead': 'SELL'
        }

        signal = signal_map.get(cross_type, 'HOLD')

        return {
            'signal': signal,
            'strength': 0,  # 不再计算强度
            'valid': True
        }
    
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
        current = self.macd.get_current_values()

        if current['macd_line'] is None or current['signal_line'] is None:
            return 'NEUTRAL'

        macd = current['macd_line']
        signal = current['signal_line']
        histogram = current['histogram']

        # 使用历史柱状图的百分位数判断强度
        if len(self.histogram_history) >= 20:
            # 计算绝对值的75分位数作为"强"的阈值
            hist_abs = [abs(h) for h in self.histogram_history[-50:] if h is not None]
            if hist_abs:
                hist_75th = np.percentile(hist_abs, 75)
            else:
                hist_75th = abs(histogram) * 0.5
        else:
            # 数据不足时使用简单倍数
            hist_abs = [abs(h) for h in self.histogram_history if h is not None]
            if hist_abs:
                hist_75th = np.percentile(hist_abs, 75)
            else:
                hist_75th = abs(histogram) * 0.5

        if macd > signal and histogram > 0:
            if abs(histogram) > hist_75th:
                return 'STRONG_BULLISH'
            else:
                return 'BULLISH'
        elif macd < signal and histogram < 0:
            if abs(histogram) > hist_75th:
                return 'STRONG_BEARISH'
            else:
                return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def reset(self):
        """重置分析器状态"""
        self.previous_values = None
        self.macd_history = []
        self.signal_history = []
        self.histogram_history = []
    
    def get_filter_parameters(self) -> Dict[str, Any]:
        """
        获取当前的过滤参数

        Returns:
            包含所有过滤参数的字典
        """
        return {
            'angle_multiplier': self.angle_multiplier,
            'min_hist_threshold': self.min_hist_threshold,
            'lookback_period': self.lookback_period,
            'min_zero_distance': self.min_zero_distance
        }

    def set_filter_parameters(self,
                             angle_multiplier: float = None,
                             min_hist_threshold: float = None,
                             lookback_period: int = None,
                             min_zero_distance: float = None):
        """
        更新过滤参数（不会重置历史记录）

        Args:
            angle_multiplier: 角度阈值乘数
            min_hist_threshold: 最小柱状图阈值
            lookback_period: 计算标准差的回溯周期
            min_zero_distance: 距离0轴的最小距离（只需配置正数）
        """
        if angle_multiplier is not None:
            self.angle_multiplier = angle_multiplier
        if min_hist_threshold is not None:
            self.min_hist_threshold = min_hist_threshold
        if lookback_period is not None:
            self.lookback_period = lookback_period
        if min_zero_distance is not None:
            self.min_zero_distance = abs(min_zero_distance)  # 确保是正数
