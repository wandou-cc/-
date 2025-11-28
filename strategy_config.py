# -*- coding: utf-8 -*-
"""
策略配置文件 - 状态机驱动的分层策略系统配置
所有指标和策略参数都可在此配置
"""

from typing import Dict, Any, List, Optional


# ==================== 策略总配置 ====================
STRATEGY_CONFIG: Dict[str, Any] = {

    # ==================== 指标配置 ====================
    # 每个指标都可以独立开关和配置参数
    "indicators": {
        # ADX - 趋势强度指标（核心，用于市场状态识别）
        "adx": {
            "enabled": True,
            "period": 14,
        },

        # EMA - 指数移动平均线系统
        "ema": {
            "enabled": True,
            "periods": [5, 20, 60],  # 快、中、慢三条均线
        },

        # MACD - 移动平均收敛背离
        "macd": {
            "enabled": True,
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
        },

        # RSI - 相对强弱指数
        "rsi": {
            "enabled": True,
            "period": 14,
            "overbought": 70,
            "oversold": 30,
        },

        # KDJ - 随机指标
        "kdj": {
            "enabled": True,
            "period": 9,
            "signal": 3,
        },

        # CCI - 顺势指标（可选）
        "cci": {
            "enabled": False,  # 默认关闭，与RSI/KDJ信号重叠
            "period": 20,
        },

        # 布林带
        "bollinger": {
            "enabled": True,
            "period": 20,
            "std_dev": 2.0,
        },

        # ATR - 平均真实波幅
        "atr": {
            "enabled": True,
            "period": 14,
        },

        # 成交量分析
        "volume": {
            "enabled": True,
            "ma_period": 20,
            "spike_threshold": 2.0,     # 异常放量阈值
            "high_threshold": 1.5,      # 放量阈值
            "low_threshold": 0.7,       # 缩量阈值
        },
    },

    # ==================== 市场状态阈值 ====================
    "market_state": {
        "adx_ranging_threshold": 20,        # ADX < 20 = 震荡市
        "adx_trending_threshold": 25,       # ADX 20-40 = 趋势市
        "adx_strong_trend_threshold": 40,   # ADX > 40 = 强趋势/突破
        "volume_spike_for_breakout": 1.5,   # 成交量放大倍数触发突破检测
        "atr_spike_for_breakout": 1.3,      # ATR放大倍数触发突破检测
    },

    # ==================== 子策略配置 ====================
    "strategies": {
        # 震荡策略配置
        "ranging": {
            "enabled": True,
            "bb_lower_threshold": 0.15,     # 布林带下轨阈值 (%B)
            "bb_upper_threshold": 0.85,     # 布林带上轨阈值 (%B)
            "rsi_oversold": 35,             # RSI超卖阈值
            "rsi_overbought": 65,           # RSI超买阈值
            "kdj_oversold": 25,             # KDJ超卖阈值
            "kdj_overbought": 75,           # KDJ超买阈值
            "j_extreme_low": 10,            # J值极低阈值
            "j_extreme_high": 90,           # J值极高阈值
        },

        # 趋势策略配置
        "trending": {
            "enabled": True,
            "ema_pullback_threshold": 0.015,  # 回调至EMA20的距离阈值 (1.5%)
            "rsi_healthy_low": 40,            # RSI健康区间下限
            "rsi_healthy_high": 70,           # RSI健康区间上限
            "macd_confirmation": True,        # 是否需要MACD确认
        },

        # 突破策略配置
        "breakout": {
            "enabled": True,
            "lookback_period": 20,            # 突破参考的K线数量
            "min_breakout_atr": 0.5,          # 最小突破幅度（ATR倍数）
            "volume_confirmation": True,       # 是否需要成交量确认
            "min_volume_ratio": 1.5,          # 最小成交量倍数
        },
    },

    # ==================== 多周期确认配置 ====================
    "multi_timeframe": {
        "enabled": True,
        "primary_timeframe": "5m",            # 主信号周期
        "confirmation_timeframes": ["15m", "1h"],  # 确认周期
        "min_confirmations": 1,               # 至少需要几个周期确认
        "weights": {                          # 各周期权重
            "5m": 0.4,
            "15m": 0.35,
            "1h": 0.25,
        },
        # 各周期确认规则
        "confirmation_rules": {
            "15m": {
                "check_trend": True,          # 检查趋势方向
                "check_rsi_extreme": True,    # 检查RSI是否极端
                "check_macd": True,           # 检查MACD方向
            },
            "1h": {
                "check_trend": True,          # 检查大趋势
                "check_support_resistance": False,  # 检查支撑阻力（可选）
                "check_volume_trend": True,   # 检查成交量趋势
            },
        },
    },

    # ==================== 预测目标配置 ====================
    "prediction": {
        "horizons": [10, 30, 60],              # 预测未来10/30/60分钟
        "min_confidence": 0.5,                 # 最低信心度
    },

    # ==================== 信号强度阈值 ====================
    "signal_thresholds": {
        "strong_signal": 0.75,                # >= 75% = A级强信号
        "standard_signal": 0.50,              # >= 50% = B级标准信号
        "weak_signal": 0.30,                  # >= 30% = C级弱信号（不开单）
    },

    # ==================== 风险管理配置 ====================
    "risk_management": {
        "default_stop_loss_atr": 2.0,         # 默认止损距离（ATR倍数）
        "default_take_profit_atr": 3.0,       # 默认止盈距离（ATR倍数）
        "max_position_size": 1.0,             # 最大仓位比例
        "position_size_by_grade": {           # 按信号等级调整仓位
            "A": 1.0,
            "B": 0.6,
            "C": 0.0,                         # C级不开仓
        },
    },
}


# ==================== 便捷函数 ====================

def get_indicator_config(indicator_name: str) -> Optional[Dict[str, Any]]:
    """获取指定指标的配置"""
    return STRATEGY_CONFIG["indicators"].get(indicator_name)


def is_indicator_enabled(indicator_name: str) -> bool:
    """检查指标是否启用"""
    config = get_indicator_config(indicator_name)
    return config is not None and config.get("enabled", False)


def get_enabled_indicators() -> List[str]:
    """获取所有启用的指标名称"""
    return [
        name for name, config in STRATEGY_CONFIG["indicators"].items()
        if config.get("enabled", False)
    ]


def get_strategy_config(strategy_name: str) -> Optional[Dict[str, Any]]:
    """获取指定策略的配置"""
    return STRATEGY_CONFIG["strategies"].get(strategy_name)


def is_strategy_enabled(strategy_name: str) -> bool:
    """检查策略是否启用"""
    config = get_strategy_config(strategy_name)
    return config is not None and config.get("enabled", False)


def get_market_state_thresholds() -> Dict[str, float]:
    """获取市场状态阈值"""
    return STRATEGY_CONFIG["market_state"]


def get_signal_thresholds() -> Dict[str, float]:
    """获取信号强度阈值"""
    return STRATEGY_CONFIG["signal_thresholds"]


def get_multi_timeframe_config() -> Dict[str, Any]:
    """获取多周期确认配置"""
    return STRATEGY_CONFIG["multi_timeframe"]


def get_prediction_horizons() -> List[int]:
    """获取预测时间周期"""
    return STRATEGY_CONFIG["prediction"]["horizons"]


def get_risk_config() -> Dict[str, Any]:
    """获取风险管理配置"""
    return STRATEGY_CONFIG["risk_management"]


# ==================== 配置验证 ====================

def validate_config() -> List[str]:
    """
    验证配置有效性

    Returns:
        错误信息列表，空列表表示配置有效
    """
    errors = []

    # 检查至少有一个指标启用
    if not get_enabled_indicators():
        errors.append("至少需要启用一个指标")

    # 检查ADX必须启用（用于市场状态识别）
    if not is_indicator_enabled("adx"):
        errors.append("ADX指标必须启用（用于市场状态识别）")

    # 检查至少有一个策略启用
    enabled_strategies = [
        name for name in ["ranging", "trending", "breakout"]
        if is_strategy_enabled(name)
    ]
    if not enabled_strategies:
        errors.append("至少需要启用一个交易策略")

    # 检查多周期配置
    mtf_config = get_multi_timeframe_config()
    if mtf_config["enabled"]:
        if not mtf_config["confirmation_timeframes"]:
            errors.append("多周期确认启用但未配置确认周期")

        total_weight = sum(mtf_config["weights"].values())
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"多周期权重之和应为1.0，当前为{total_weight}")

    # 检查信号阈值
    thresholds = get_signal_thresholds()
    if thresholds["strong_signal"] <= thresholds["standard_signal"]:
        errors.append("强信号阈值应大于标准信号阈值")
    if thresholds["standard_signal"] <= thresholds["weak_signal"]:
        errors.append("标准信号阈值应大于弱信号阈值")

    return errors


# ==================== 动态配置更新 ====================

def update_indicator_config(indicator_name: str, **kwargs) -> bool:
    """
    动态更新指标配置

    Args:
        indicator_name: 指标名称
        **kwargs: 要更新的参数

    Returns:
        是否更新成功
    """
    if indicator_name not in STRATEGY_CONFIG["indicators"]:
        return False

    STRATEGY_CONFIG["indicators"][indicator_name].update(kwargs)
    return True


def update_strategy_config(strategy_name: str, **kwargs) -> bool:
    """
    动态更新策略配置

    Args:
        strategy_name: 策略名称
        **kwargs: 要更新的参数

    Returns:
        是否更新成功
    """
    if strategy_name not in STRATEGY_CONFIG["strategies"]:
        return False

    STRATEGY_CONFIG["strategies"][strategy_name].update(kwargs)
    return True


def enable_indicator(indicator_name: str) -> bool:
    """启用指标"""
    return update_indicator_config(indicator_name, enabled=True)


def disable_indicator(indicator_name: str) -> bool:
    """禁用指标"""
    return update_indicator_config(indicator_name, enabled=False)


def enable_strategy(strategy_name: str) -> bool:
    """启用策略"""
    return update_strategy_config(strategy_name, enabled=True)


def disable_strategy(strategy_name: str) -> bool:
    """禁用策略"""
    return update_strategy_config(strategy_name, enabled=False)
