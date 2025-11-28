# -*- coding: utf-8 -*-
"""
策略基类

定义所有子策略的公共接口和数据结构
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class SignalDirection(Enum):
    """信号方向"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategySignal:
    """策略信号结果"""
    direction: SignalDirection          # 信号方向
    strength: float                      # 信号强度 0-1
    strategy_name: str                   # 策略名称
    reasons: List[str] = field(default_factory=list)  # 信号原因
    entry_price: Optional[float] = None  # 建议入场价
    stop_loss: Optional[float] = None    # 建议止损价
    take_profit: Optional[float] = None  # 建议止盈价
    indicator_values: Dict[str, Any] = field(default_factory=dict)  # 指标值快照
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据

    def is_valid_signal(self, min_strength: float = 0.3) -> bool:
        """判断是否为有效信号"""
        return self.direction != SignalDirection.HOLD and self.strength >= min_strength


class BaseStrategy(ABC):
    """
    策略基类

    所有子策略必须继承此类并实现 analyze 方法
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        初始化策略

        Args:
            name: 策略名称
            config: 策略配置
        """
        self.name = name
        self.config = config or {}

    @abstractmethod
    def analyze(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None,
        indicators: Optional[Dict[str, Any]] = None
    ) -> StrategySignal:
        """
        分析市场并生成信号

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            volumes: 成交量序列（可选）
            indicators: 预计算的指标值（可选，避免重复计算）

        Returns:
            StrategySignal 信号结果
        """
        pass

    def _create_signal(
        self,
        direction: SignalDirection,
        strength: float,
        reasons: List[str],
        entry_price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        indicator_values: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> StrategySignal:
        """
        创建信号对象的便捷方法

        Args:
            direction: 信号方向
            strength: 信号强度
            reasons: 信号原因列表
            entry_price: 入场价
            stop_loss: 止损价
            take_profit: 止盈价
            indicator_values: 指标值
            metadata: 元数据

        Returns:
            StrategySignal
        """
        return StrategySignal(
            direction=direction,
            strength=min(max(strength, 0.0), 1.0),  # 确保在0-1范围内
            strategy_name=self.name,
            reasons=reasons,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicator_values=indicator_values or {},
            metadata=metadata or {}
        )

    def _no_signal(
        self,
        reason: str = "无明确信号",
        indicator_values: Dict[str, Any] = None
    ) -> StrategySignal:
        """创建无信号结果"""
        return self._create_signal(
            direction=SignalDirection.HOLD,
            strength=0.0,
            reasons=[reason],
            indicator_values=indicator_values
        )

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
