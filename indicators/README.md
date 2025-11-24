# 技术指标库

本文件夹包含所有技术指标的实现，基于TradingView标准。

## 可用指标

### 1. MACD指标 (`macd_indicator.py`) ⭐ 最新优化
- 移动平均收敛背离指标
- 默认参数: (12, 26, 9)
- **新增**: 多维度信号过滤系统
  - 角度过滤: 动态计算交叉角度，过滤小角度假信号
  - 动能过滤: 检查柱状图连续性，确保趋势延续
  - 阈值过滤: 避免横盘震荡噪音
- **信号分级**: strong_golden, weak_golden, strong_dead, weak_dead, none
- 📖 详细文档: [MACD_FILTER_GUIDE.md](./MACD_FILTER_GUIDE.md)

### 2. 布林带 (`bollinger_bands.py`)
- 使用SMA作为中轨（TradingView标准）
- 默认参数: (20, 2.0)

### 3. RSI指标 (`rsi_indicator.py`)
- 相对强弱指数
- 使用EMA方法（Wilder's Smoothing）
- 默认参数: (14)

### 4. KDJ指标 (`kdj_indicator.py`)
- 随机指标
- 使用bcwsma平滑，K和D初始值为50
- 默认参数: (9, 3)

### 5. CCI指标 (`cci_indicator.py`)
- 顺势指标
- 衡量价格偏离统计平均值的程度
- 默认参数: (20)

### 6. ATR指标 (`atr_indicator.py`)
- 平均真实波幅
- 衡量市场波动性

### 7. VWAP指标 (`vwap_indicator.py`)
- 成交量加权平均价
- 用于评估交易价格质量

### 8. EMA交叉 (`ema_cross.py`)
- EMA均线交叉策略
- 支持多种EMA周期组合

## 使用方法

### 单独导入
```python
from indicators.cci_indicator import CCIIndicator, CCIAnalyzer
from indicators.kdj_indicator import KDJIndicator, KDJAnalyzer
from indicators.rsi_indicator import RSIIndicator, RSIAnalyzer
```

### 批量导入
```python
from indicators import (
    CCIIndicator,
    KDJIndicator,
    RSIIndicator,
    MACDIndicator,
    BollingerBandsIndicator
)
```

## 特性

- ✅ 符合TradingView标准
- ✅ 支持批量计算
- ✅ 支持实时增量更新
- ✅ 提供交易信号分析
- ✅ 完整的参数配置
- ✅ 详细的文档说明

