# 技术指标实现库

基于TradingView标准的技术指标实现，支持实时计算和参数配置。所有指标均已通过与TradingView的对比验证。

## 功能特性

- ✅ **MACD指标**：MACD线、信号线、柱状图
- ✅ **布林带指标**：上轨、中轨(SMA)、下轨、带宽、%B
- ✅ **RSI指标**：使用EMA方法，符合TradingView标准
- ✅ **KDJ指标**：K线、D线、J线，使用bcwsma平滑
- ✅ **CCI指标**：顺势指标，衡量价格偏离统计平均值的程度
- ✅ **ATR指标**：平均真实波幅
- ✅ **VWAP指标**：成交量加权平均价
- ✅ 支持实时增量计算
- ✅ 可配置的参数，支持外部传入
- ✅ 交易信号分析
- ✅ 趋势强度判断
- ✅ 批量计算和实时更新
- ✅ 完整的示例和文档
- ✅ **已通过TradingView验证**

## 安装依赖

```bash
pip install -r requirements.txt
```

## 项目结构

```
指标相关/
├── indicators/          # 技术指标实现
│   ├── atr_indicator.py
│   ├── bollinger_bands.py
│   ├── cci_indicator.py
│   ├── ema_cross.py
│   ├── kdj_indicator.py
│   ├── macd_indicator.py
│   ├── rsi_indicator.py
│   ├── vwap_indicator.py
│   └── __init__.py
├── tests/              # 测试文件
│   ├── test_cci_real_data.py
│   └── K.json
├── README.md
└── requirements.txt
```

## 快速开始

### MACD指标

```python
from indicators.macd_indicator import MACDIndicator, MACDAnalyzer

# 创建MACD指标实例（参数可外部传入：fast_period=12, slow_period=26, signal_period=9）
macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)

# 批量计算
prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
result = macd.calculate(prices)

print(f"MACD线: {result['macd_line']}")
print(f"信号线: {result['signal_line']}")
print(f"柱状图: {result['histogram']}")

# 实时更新 + 角度过滤
# min_cross_strength: 最小交叉强度阈值（默认5.0）
# 值越大，过滤越严格，只保留大角度的金叉死叉
analyzer = MACDAnalyzer(macd, min_cross_strength=5.0)

for price in prices:
    macd.update(price)
    
    # 方法1: 获取过滤后的信号
    signal = analyzer.get_signal()  # 默认启用角度过滤
    
    # 方法2: 获取详细信息
    signal_info = analyzer.get_signal_with_strength()
    print(f"信号: {signal_info['signal']}, 强度: {signal_info['strength']:.2f}")
```

### 布林带指标

```python
from indicators.bollinger_bands import BollingerBandsIndicator, BollingerBandsAnalyzer

# 创建布林带指标实例（参数可外部传入：period=20, std_dev=2.0）
# 使用SMA作为中轨线，符合TradingView标准
bb = BollingerBandsIndicator(period=20, std_dev=2.0)

# 批量计算
result = bb.calculate(prices)

print(f"上轨: {result['upper_band']}")
print(f"中轨(SMA): {result['middle_band']}")
print(f"下轨: {result['lower_band']}")
print(f"%B: {result['percent_b']}")

# 实时更新
for price in prices:
    current_values = bb.update(price)
    print(f"价格: {price}, 上轨: {current_values['upper_band']}")
```

### RSI指标

```python
from indicators.rsi_indicator import RSIIndicator, RSIAnalyzer

# 创建RSI指标实例（参数可外部传入：period=14, use_ema=True）
# 默认使用EMA方法，符合TradingView标准
rsi = RSIIndicator(period=14, use_ema=True)

# 批量计算
result = rsi.calculate(prices)

print(f"RSI: {result['rsi']}")

# 实时更新
for price in prices:
    current_values = rsi.update(price)
    print(f"价格: {price}, RSI: {current_values['rsi']}")
```

### KDJ指标

```python
from indicators.kdj_indicator import KDJIndicator, KDJAnalyzer

# 创建KDJ指标实例（参数可外部传入：period=9, signal=3）
kdj = KDJIndicator(period=9, signal=3)

# 批量计算（需要最高价、最低价、收盘价）
result = kdj.calculate(highs, lows, closes)

print(f"K值: {result['k']}")
print(f"D值: {result['d']}")
print(f"J值: {result['j']}")

# 实时更新
for high, low, close in zip(highs, lows, closes):
    current_values = kdj.update(high, low, close)
    print(f"K: {current_values['k']}, D: {current_values['d']}, J: {current_values['j']}")
```

### CCI指标

```python
from indicators.cci_indicator import CCIIndicator, CCIAnalyzer

# 创建CCI指标实例（参数可外部传入：period=20）
cci = CCIIndicator(period=20)

# 批量计算（需要最高价、最低价、收盘价）
result = cci.calculate(highs, lows, closes)

print(f"CCI值: {result['cci']}")
print(f"典型价格: {result['typical_price']}")
print(f"SMA: {result['sma']}")

# 实时更新
for high, low, close in zip(highs, lows, closes):
    current_values = cci.update(high, low, close)
    print(f"CCI: {current_values['cci']}")

# 使用分析器
analyzer = CCIAnalyzer(cci)
signal = analyzer.get_signal()  # BUY/SELL/HOLD
momentum = analyzer.get_momentum_level()  # OVERBOUGHT/OVERSOLD等
```

### 批量导入

```python
# 方法1: 从indicators导入
from indicators import CCIIndicator, KDJIndicator, RSIIndicator

# 方法2: 直接导入具体模块
from indicators.cci_indicator import CCIIndicator
from indicators.kdj_indicator import KDJIndicator
from indicators.rsi_indicator import RSIIndicator
```

### 运行测试

```bash
# 运行CCI真实数据测试
python tests/test_cci_real_data.py

# 或进入tests目录运行
cd tests
python test_cci_real_data.py
```

## API文档

### MACD指标 (MACDIndicator)

#### 初始化参数

- `fast_period` (int): 快速EMA周期，默认12
- `slow_period` (int): 慢速EMA周期，默认26  
- `signal_period` (int): 信号线EMA周期，默认9

#### 主要方法

- `calculate(prices)`: 批量计算MACD指标
- `update(new_price)`: 实时更新MACD指标
- `get_current_values()`: 获取当前的MACD值
- `set_parameters(fast_period, slow_period, signal_period)`: 更新参数
- `reset()`: 重置指标状态

#### MACDAnalyzer

**初始化参数**：
- `macd_indicator`: MACD指标实例
- `min_cross_strength` (float): 最小交叉强度阈值，默认5.0，用于过滤小角度金叉死叉

**主要方法**：
- `get_signal(check_angle=True)`: 获取交易信号 (BUY/SELL/HOLD)，支持角度过滤
- `get_signal_with_strength(check_angle=True)`: 获取信号及强度信息
- `get_trend_strength()`: 获取趋势强度

**角度过滤功能**（新增⭐）：
- 过滤掉小角度的金叉死叉，减少假信号
- 强度值越大，交叉角度越大，信号越可靠
- 推荐阈值：3-5（标准），8-10（严格），15+（极严）

### 布林带指标 (BollingerBandsIndicator)

#### 初始化参数

- `period` (int): SMA周期，默认20
- `std_dev` (float): 标准差倍数，默认2.0

#### 主要方法

- `calculate(prices)`: 批量计算布林带指标
- `update(new_price)`: 实时更新布林带指标
- `get_current_values()`: 获取当前的布林带值
- `set_parameters(period, std_dev)`: 更新参数
- `reset()`: 重置指标状态

#### BollingerBandsAnalyzer

- `get_signal()`: 获取交易信号 (BUY/SELL/HOLD)
- `get_volatility_level()`: 获取波动率水平 (HIGH/MEDIUM/LOW)
- `get_price_position()`: 获取价格在布林带中的位置

**注意**: 使用SMA作为中轨线，符合TradingView标准

### RSI指标 (RSIIndicator)

#### 初始化参数

- `period` (int): RSI计算周期，默认14
- `use_ema` (bool): 是否使用EMA方法，默认True（符合TradingView标准）

#### 主要方法

- `calculate(prices)`: 批量计算RSI指标
- `update(new_price)`: 实时更新RSI指标
- `get_current_values()`: 获取当前的RSI值
- `set_parameters(period, use_ema)`: 更新参数
- `reset()`: 重置指标状态

#### RSIAnalyzer

- `get_signal(overbought=70, oversold=30)`: 获取交易信号 (BUY/SELL/HOLD)
- `get_momentum_level()`: 获取动量水平 (OVERBOUGHT/BULLISH/NEUTRAL/BEARISH/OVERSOLD)
- `get_divergence_signal(prices, lookback=5)`: 检测RSI背离信号

### KDJ指标 (KDJIndicator)

#### 初始化参数

- `period` (int): RSV计算周期，默认9
- `signal` (int): K和D的平滑周期，默认3

#### 主要方法

- `calculate(highs, lows, closes)`: 批量计算KDJ指标
- `update(high, low, close)`: 实时更新KDJ指标
- `get_current_values()`: 获取当前的KDJ值
- `get_parameters()`: 获取当前参数设置
- `reset()`: 重置指标状态

#### KDJAnalyzer

- `get_signal()`: 获取交易信号 (BUY/SELL/HOLD)
- `get_momentum_level()`: 获取动量水平 (OVERBOUGHT/OVERSOLD/NEUTRAL)
- `get_trend_strength()`: 获取趋势强度

**注意**: 
- KDJ指标需要最高价、最低价、收盘价三个价格序列
- K和D的初始值为50，符合TradingView标准

### CCI指标 (CCIIndicator)

#### 初始化参数

- `period` (int): CCI计算周期，默认20

#### 主要方法

- `calculate(highs, lows, closes)`: 批量计算CCI指标
- `update(high, low, close)`: 实时更新CCI指标
- `get_current_values()`: 获取当前的CCI值
- `get_parameters()`: 获取当前参数设置
- `set_parameters(period)`: 更新参数
- `reset()`: 重置指标状态

#### CCIAnalyzer

- `get_signal(overbought=100, oversold=-100)`: 获取交易信号 (BUY/SELL/HOLD)
- `get_momentum_level()`: 获取动量水平 (STRONG_OVERBOUGHT/OVERBOUGHT/BULLISH/NEUTRAL/BEARISH/OVERSOLD/STRONG_OVERSOLD)
- `get_trend_direction()`: 获取趋势方向 (UPTREND/DOWNTREND/NEUTRAL)
- `detect_divergence(prices, cci_values, lookback=5)`: 检测CCI背离信号

**注意**: 
- CCI指标需要最高价、最低价、收盘价三个价格序列
- CCI使用0.015作为常数，确保70%-80%的值在-100到+100之间
- CCI > 100表示超买，CCI < -100表示超卖

## 验证报告

所有指标已通过与TradingView的对比验证，详见：
- `INDICATOR_VERIFICATION_SUMMARY.md` - 完整验证总结
- `verify_all_indicators.py` - 综合验证脚本
- `quick_test.py` - 快速测试脚本

## 使用示例

### 运行示例

```bash
# MACD指标示例
python example_usage.py

# 布林带和RSI指标示例
python indicators_examples.py

# 使用比特币数据测试MACD
python macd_test.py

# 使用比特币数据测试RSI
python rsi_test.py

# 综合测试所有指标
python bitcoin_test.py
```

## 技术实现

### MACD计算公式

1. **快速EMA**: EMA(12) = α₁ × 价格 + (1-α₁) × 前一日EMA
2. **慢速EMA**: EMA(26) = α₂ × 价格 + (1-α₂) × 前一日EMA
3. **MACD线**: MACD = 快速EMA - 慢速EMA
4. **信号线**: 信号线 = EMA(9) of MACD线
5. **柱状图**: 柱状图 = MACD线 - 信号线

其中：α = 2/(period+1)

### 布林带计算公式（TradingView标准）

1. **中轨线**: SMA(20) - 使用简单移动平均
2. **标准差**: STDEV(价格, 20)
3. **上轨线**: 中轨线 + (标准差 × 2)
4. **下轨线**: 中轨线 - (标准差 × 2)
5. **%B**: (价格 - 下轨) / (上轨 - 下轨)
6. **带宽**: (上轨 - 下轨) / 中轨

**注意**: TradingView的标准布林带使用SMA而非EMA作为中轨

### RSI计算公式（EMA方法）

1. **价格变化**: 计算每日涨跌幅
2. **平均涨幅**: 使用EMA平滑（α = 1/period）
   - 初始值：前N期涨幅的SMA
   - 后续值：EMA = α × 当前涨幅 + (1-α) × 前一期EMA
3. **平均跌幅**: 同上
4. **RS**: RS = 平均涨幅 / 平均跌幅
5. **RSI**: RSI = 100 - (100 / (1 + RS))

### KDJ计算公式（TradingView标准）

1. **RSV**: RSV = 100 × (收盘价 - N日最低价) / (N日最高价 - N日最低价)
2. **K值**: K = bcwsma(RSV, 3, 1)
   - bcwsma = (1 × RSV + 2 × K前) / 3
   - 初始值: K = 50
3. **D值**: D = bcwsma(K, 3, 1)
   - bcwsma = (1 × K + 2 × D前) / 3
   - 初始值: D = 50
4. **J值**: J = 3K - 2D

**注意**: 
- bcwsma是一种特殊的加权移动平均，等价于EMA但权重计算方式不同
- K和D的初始值为50是TradingView的标准设置

### CCI计算公式（TradingView标准）

1. **典型价格**: TP = (最高价 + 最低价 + 收盘价) / 3
2. **简单移动平均**: SMA = SMA(TP, 20)
3. **平均偏差**: MD = SMA(|TP - SMA|, 20)
4. **CCI**: CCI = (TP - SMA) / (0.015 × MD)

**注意**: 
- 常数0.015确保大约70%-80%的CCI值落在-100到+100之间
- CCI没有上下限，可以达到很大的正值或负值
- 典型的超买超卖阈值：+100和-100

### 性能优化

- 使用增量计算进行实时更新，避免重复计算
- 支持批量计算和实时计算两种模式
- 内存效率优化，只存储必要的状态信息
- 参数可外部传入，灵活配置

## 注意事项

1. **数据长度要求**：
   - MACD：至少需要slow_period个数据点（默认26）
   - 布林带：至少需要period个数据点（默认20）
   - RSI：至少需要period+1个数据点（默认15）
   - KDJ：至少需要period个数据点（默认9）
   - CCI：至少需要period个数据点（默认20）

2. **参数调整**：修改参数会重置指标状态，需要重新计算

3. **实时更新**：使用`update()`方法进行增量计算，适合实时数据流

4. **批量计算**：使用`calculate()`方法进行批量计算，适合历史数据分析

5. **TradingView兼容性**（已验证✅）：
   - RSI使用EMA方法（Wilder's Smoothing），与TradingView完全一致
   - 布林带使用SMA作为中轨线，符合TradingView标准
   - MACD使用标准EMA计算方法
   - KDJ使用bcwsma平滑，K和D初始值为50，完全符合TradingView标准

## 依赖包

- numpy >= 1.21.0
- pandas >= 1.3.0
- matplotlib >= 3.5.0
- openpyxl >= 3.0.0

## 许可证

MIT License