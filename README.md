# 状态机驱动的分层交易策略系统

基于 ADX 市场状态识别的自动化交易信号生成系统，支持多周期确认和实时 WebSocket 数据接入。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         K线数据输入                                  │
│                    (5m / 15m / 1h 多周期)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      指标计算引擎                                    │
│   ADX | EMA | MACD | RSI | KDJ | Bollinger | ATR | Volume           │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ 市场状态识别  │ │  成交量分析   │ │  价格形态    │
      │  (ADX驱动)   │ │  (放量/缩量)  │ │  (突破/支撑) │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
             └────────────────┼────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │        策略自动选择            │
              ├───────────────────────────────┤
              │ ADX < 20  →  震荡策略         │
              │ ADX 20-40 →  趋势策略         │
              │ ADX > 40  →  突破策略         │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       多周期确认系统           │
              │   5m ✓  →  15m ✓  →  1h ✓    │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │        最终信号输出            │
              │  方向 | 强度 | 等级 | 预测     │
              └───────────────────────────────┘
```

## 目录结构

```
指标相关/
├── strategy_config.py          # 策略配置文件（所有参数可配置）
├── config.py                   # 基础配置（API、代理等）
├── live_trading_v2.py          # 实时交易系统 V2
│
├── indicators/                 # 技术指标库
│   ├── __init__.py
│   ├── adx_indicator.py       # ADX 平均趋向指数
│   ├── volume_indicator.py    # 成交量分析
│   ├── macd_indicator.py      # MACD 指标
│   ├── rsi_indicator.py       # RSI 相对强弱指数
│   ├── kdj_indicator.py       # KDJ 随机指标
│   ├── bollinger_bands.py     # 布林带
│   ├── atr_indicator.py       # ATR 平均真实波幅
│   ├── ema_cross.py           # EMA 均线系统
│   ├── cci_indicator.py       # CCI 顺势指标
│   └── streaming_buffer.py    # K线流式缓冲区
│
└── strategy/                   # 策略系统
    ├── __init__.py
    ├── market_state.py        # 市场状态识别
    ├── signal_generator.py    # 信号生成器（核心）
    ├── multi_timeframe.py     # 多周期确认
    └── strategies/            # 子策略
        ├── __init__.py
        ├── base_strategy.py       # 策略基类
        ├── ranging_strategy.py    # 震荡策略
        ├── trending_strategy.py   # 趋势策略
        └── breakout_strategy.py   # 突破策略
```

## 快速开始

### 安装依赖

```bash
pip install numpy websockets aiohttp aiohttp-socks
```

### 基本使用

```python
from strategy import SignalGenerator

# 创建信号生成器
generator = SignalGenerator(symbol='BTCUSDT')

# 生成信号（传入OHLCV数据）
signal = generator.generate(
    highs=highs,      # 最高价列表
    lows=lows,        # 最低价列表
    closes=closes,    # 收盘价列表
    volumes=volumes   # 成交量列表（可选）
)

# 输出信号摘要
print(generator.get_signal_summary(signal))
```

### 启动实时交易系统

```bash
# 默认配置
python live_trading_v2.py

# 自定义参数
python live_trading_v2.py --symbol ETHUSDT --interval 5m --confirm 15m 1h
```

## 核心模块说明

### 1. 市场状态识别 (MarketStateDetector)

基于 ADX 指标自动识别当前市场状态：

| ADX 范围 | 市场状态 | 推荐策略 |
|----------|----------|----------|
| < 20 | 震荡盘整 (RANGING) | 震荡策略 |
| 20-40 | 趋势市场 (TRENDING) | 趋势策略 |
| > 40 | 强趋势/突破 (BREAKOUT) | 突破策略 |

```python
from strategy import MarketStateDetector

detector = MarketStateDetector()
result = detector.detect(highs, lows, closes, volumes)

print(f"市场状态: {result.state.value}")
print(f"ADX: {result.adx}")
print(f"趋势方向: {result.trend_direction.value}")
print(f"置信度: {result.confidence:.0%}")
```

### 2. 三种子策略

#### 震荡策略 (RangingStrategy)

**适用场景**: ADX < 20 的横盘震荡市场

**做多条件**:
- 价格触及布林带下轨 (%B < 0.15)
- RSI < 35 (超卖)
- KDJ: K < 25 或 J < 10 或金叉
- 成交量萎缩（抛压减弱）

**做空条件**:
- 价格触及布林带上轨 (%B > 0.85)
- RSI > 65 (超买)
- KDJ: K > 75 或 J > 90 或死叉
- 成交量萎缩（买盘减弱）

#### 趋势策略 (TrendingStrategy)

**适用场景**: ADX 20-40 的趋势市场

**做多条件** (上升趋势中):
- EMA排列: EMA5 > EMA20 > EMA60
- 价格回调至 EMA20 附近 (距离 < 1.5%)
- MACD 柱状图 > 0 或即将金叉
- RSI 在 40-70 健康区间
- 回调时成交量萎缩

**做空条件** (下降趋势中):
- EMA排列: EMA5 < EMA20 < EMA60
- 价格反弹至 EMA20 附近 (距离 < 1.5%)
- MACD 柱状图 < 0 或即将死叉
- RSI 在 30-60 健康区间

#### 突破策略 (BreakoutStrategy)

**适用场景**: ADX > 40 或检测到突破信号

**做多条件**:
- 价格突破近20根K线最高点
- 成交量 > 均量 × 1.5 (放量确认)
- ATR 扩大 > 20%
- MACD > 0 且向上
- +DI > -DI

**做空条件**:
- 价格跌破近20根K线最低点
- 成交量放大确认
- ATR 扩大
- MACD < 0 且向下
- -DI > +DI

### 3. 多周期确认 (MultiTimeframeConfirmer)

主周期（5分钟）产生信号后，通过更高周期进行确认：

```
5分钟产生信号
      │
      ▼
┌─────────────────────────────┐
│      15分钟周期检查          │
│  • 趋势方向是否一致？        │
│  • RSI是否在极端区域？       │
│  • MACD方向是否一致？        │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│       1小时周期检查          │
│  • 大趋势方向？             │
│  • 成交量趋势？             │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│        综合评分              │
│  5m × 40% + 15m × 35%       │
│         + 1h × 25%          │
└─────────────────────────────┘
```

### 4. 信号输出结构

```python
@dataclass
class TradingSignal:
    signal_id: str              # 信号ID
    timestamp: datetime         # 时间戳
    symbol: str                 # 交易对

    direction: SignalDirection  # BUY / SELL / HOLD
    strength: float             # 原始强度 0-1
    adjusted_strength: float    # 调整后强度（多周期确认后）
    grade: SignalGrade          # A / B / C / NONE

    market_state: MarketState   # 市场状态
    strategy_used: str          # 使用的策略名

    is_confirmed: bool          # 是否通过多周期确认
    confirmation_count: int     # 确认的周期数

    entry_price: float          # 入场价
    stop_loss: float            # 止损价
    take_profit: float          # 止盈价

    predictions: List[Prediction]  # 10/30/60分钟预测
    reasons: List[str]          # 信号原因
    warnings: List[str]         # 警告信息
```

### 5. 信号等级

| 等级 | 条件 | 建议操作 |
|------|------|----------|
| **A级** | 强度 ≥ 75% + 多周期全部确认 | 标准仓位开仓 |
| **B级** | 强度 50%-75% + 至少2个周期确认 | 减半仓位开仓 |
| **C级** | 强度 30%-50% | 观望不开仓 |
| **NONE** | 强度 < 30% | 无信号 |

## 配置说明

### strategy_config.py

```python
STRATEGY_CONFIG = {
    # ==================== 指标配置 ====================
    "indicators": {
        "adx": {"enabled": True, "period": 14},
        "ema": {"enabled": True, "periods": [5, 20, 60]},
        "macd": {"enabled": True, "fast_period": 12, "slow_period": 26, "signal_period": 9},
        "rsi": {"enabled": True, "period": 14, "overbought": 70, "oversold": 30},
        "kdj": {"enabled": True, "period": 9, "signal": 3},
        "bollinger": {"enabled": True, "period": 20, "std_dev": 2.0},
        "atr": {"enabled": True, "period": 14},
        "volume": {"enabled": True, "ma_period": 20, "spike_threshold": 2.0},
    },

    # ==================== 市场状态阈值 ====================
    "market_state": {
        "adx_ranging_threshold": 20,
        "adx_trending_threshold": 25,
        "adx_strong_trend_threshold": 40,
    },

    # ==================== 多周期确认 ====================
    "multi_timeframe": {
        "enabled": True,
        "primary_timeframe": "5m",
        "confirmation_timeframes": ["15m", "1h"],
        "min_confirmations": 1,
        "weights": {"5m": 0.4, "15m": 0.35, "1h": 0.25},
    },

    # ==================== 预测目标 ====================
    "prediction": {
        "horizons": [10, 30, 60],  # 分钟
    },

    # ==================== 信号阈值 ====================
    "signal_thresholds": {
        "strong_signal": 0.75,
        "standard_signal": 0.50,
        "weak_signal": 0.30,
    },
}
```

### 动态修改配置

```python
from strategy_config import (
    enable_indicator, disable_indicator,
    enable_strategy, disable_strategy,
    update_indicator_config
)

# 禁用某个指标
disable_indicator("cci")

# 启用某个策略
enable_strategy("breakout")

# 修改指标参数
update_indicator_config("rsi", period=21, overbought=80)
```

## API 参考

### SignalGenerator

```python
class SignalGenerator:
    def __init__(self, symbol: str = "BTCUSDT", config: Dict = None):
        """初始化信号生成器"""

    def generate(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float] = None,
        timeframe_data: Dict[str, Dict] = None
    ) -> TradingSignal:
        """生成交易信号"""

    def get_signal_summary(self, signal: TradingSignal) -> str:
        """生成信号摘要文本"""
```

### MarketStateDetector

```python
class MarketStateDetector:
    def __init__(
        self,
        adx_period: int = 14,
        ranging_threshold: float = 20,
        trending_threshold: float = 25,
        strong_trend_threshold: float = 40
    ):
        """初始化市场状态检测器"""

    def detect(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float] = None
    ) -> MarketStateResult:
        """检测市场状态"""
```

### MultiTimeframeConfirmer

```python
class MultiTimeframeConfirmer:
    def __init__(self, config: Dict = None):
        """初始化多周期确认器"""

    def confirm(
        self,
        signal_direction: SignalDirection,
        primary_strength: float,
        timeframe_data: Dict[str, Dict[str, List[float]]]
    ) -> MultiTimeframeResult:
        """执行多周期确认"""
```

## 指标说明

### ADX (平均趋向指数)

用于衡量趋势的强度（不判断方向）：
- ADX < 20: 无趋势/震荡
- ADX 20-25: 趋势开始形成
- ADX 25-40: 趋势较强
- ADX > 40: 强趋势

+DI 和 -DI 用于判断趋势方向：
- +DI > -DI: 上升趋势
- -DI > +DI: 下降趋势

### 成交量分析

| 状态 | 条件 | 信号意义 |
|------|------|----------|
| SPIKE | ≥ 2倍均量 | 异常放量，需关注 |
| HIGH | ≥ 1.5倍均量 | 放量，趋势确认 |
| NORMAL | 0.7-1.5倍 | 正常 |
| LOW | ≤ 0.7倍 | 缩量 |
| VERY_LOW | ≤ 0.5倍 | 极度缩量 |

量价关系分析：
- 放量上涨 → 看涨
- 缩量上涨 → 量价背离警告
- 放量下跌 → 看跌
- 缩量下跌 → 抛压减弱

## 示例输出

```
==================================================
信号ID: a1b2c3d4
方向: 🟢 做多 [A级]
强度: 82% → 78% (调整后)
市场状态: trending_up
使用策略: trending
多周期确认: ✓ (2个周期)

入场价: 50480.77
止损价: 50367.55
止盈价: 50650.59

预测:
  10分钟: ↑ (置信度: 76%) → 50499.64
  30分钟: ↑ (置信度: 72%) → 50537.37
  60分钟: ↑ (置信度: 66%) → 50593.98

信号原因:
  • EMA完美多头排列 (EMA5 > EMA20 > EMA60)
  • 价格回调至EMA20附近 (距离0.8%)
  • RSI在健康区间 (58.4)
  • MACD柱状图为正
  • 成交量萎缩（健康回调）
==================================================
```

## 注意事项

1. **数据要求**: 至少需要60根K线数据才能生成有效信号
2. **多周期数据**: 多周期确认需要提供各周期的完整OHLCV数据
3. **信号延迟**: 信号在K线关闭时生成，存在一定延迟
4. **风险提示**: 本系统仅供参考，不构成投资建议

## 更新日志

### v2.0.0 (2024-XX-XX)
- 全新的状态机驱动架构
- 新增 ADX 指标和市场状态识别
- 新增成交量分析模块
- 实现三种子策略自动切换
- 新增多周期确认系统
- 重构配置系统，所有参数可配置
- 新增价格预测功能

### v1.0.0
- 初始版本，多指标共振策略





