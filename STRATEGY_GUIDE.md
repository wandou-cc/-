# 加密货币量化交易系统 - 共振策略完整文档

## 📋 项目概览

这是一个基于多技术指标共振的实时加密货币量化交易系统,专门用于Binance永续合约市场。系统通过WebSocket实时获取K线数据,使用7个技术指标进行综合分析,当多个指标同时发出相同方向信号时(共振),生成高置信度的交易信号,并预测10分钟、30分钟、1小时后的价格走势。

### 核心特点

- ✅ **多指标共振机制**: 7个技术指标协同工作,避免单一指标误判
- ✅ **智能评分系统**: 总分100分制,多维度评估信号质量
- ✅ **趋势过滤**: 确保交易方向与主趋势一致,提高胜率
- ✅ **动量确认**: 确保价格动能支持交易方向
- ✅ **波动率过滤**: 避免在震荡市或暴涨暴跌时开单
- ✅ **实时验证**: 自动追踪信号预测准确性,持续优化策略
- ✅ **可视化Dashboard**: Rich终端界面实时显示指标和信号

---

## 🏗️ 项目结构

```
.
├── config.py                      # 配置文件(API、指标参数、策略配置)
├── live_trading_resonance.py      # 主程序(实时交易系统)
├── resonance_strategy.py          # 共振策略核心逻辑
├── dashboard.py                   # 控制台可视化界面
├── requirements.txt               # Python依赖包
├── indicators/                    # 技术指标库
│   ├── __init__.py
│   ├── macd_indicator.py         # MACD指标
│   ├── rsi_indicator.py          # RSI指标
│   ├── bollinger_bands.py        # 布林带指标
│   ├── kdj_indicator.py          # KDJ指标
│   ├── ema_cross.py              # EMA均线系统
│   ├── cci_indicator.py          # CCI指标
│   ├── atr_indicator.py          # ATR指标
│   └── vwap_indicator.py         # VWAP指标
└── tests/                         # 测试文件
```

---

## 📊 核心策略：多指标共振系统

### 指标体系架构(三层结构)

#### 1️⃣ 趋势层 - EMA四线系统
**作用**: 判断主趋势方向,过滤逆势交易

**组成**:
- 超快线(EMA5): 捕捉最新价格动向
- 快线(EMA10): 短期趋势
- 中线(EMA20): 中期趋势
- 慢线(EMA60): 长期趋势支撑/压力

**信号规则**:
- **多头趋势**: EMA5 > EMA10 > EMA20 > EMA60 (完美多头排列)
- **空头趋势**: EMA5 < EMA10 < EMA20 < EMA60 (完美空头排列)
- **震荡市**: 均线纠缠,无明确方向

**评分**: 最高25分
- 完美排列: 25分
- 部分排列: 按信号强度给分
- 震荡市: 0分

**配置参数**:
```python
EMA_PARAMS = {
    'ultra_fast': 5,
    'fast': 10,
    'medium': 20,
    'slow': 60
}
```

---

#### 2️⃣ 动量层 - RSI + KDJ + CCI
**作用**: 确认价格动能方向,捕捉超买超卖

##### RSI (相对强弱指标)
**参数**: 周期14

**信号规则**:
- RSI < 20: 极度超卖 → 强买入信号(100分)
- RSI < 30: 超卖区 → 买入信号(70-100分)
- RSI > 80: 极度超买 → 强卖出信号(100分)
- RSI > 70: 超买区 → 卖出信号(70-100分)
- 30-70: 中性区,看变化趋势

**评分**: 每个指标最高7分(强度/100 × 7)

**配置参数**:
```python
RSI_PARAMS = {
    'period': 14,
    'overbought': 70,
    'oversold': 30
}
```

##### KDJ (随机指标)
**参数**: K周期9, D周期3

**信号规则**:
- K < 20 且 D < 20: KD双超卖 → 买入(80分)
- K > 80 且 D > 80: KD双超买 → 卖出(80分)
- J < 0: J极度超卖 → 强买入(90-100分)
- J > 100: J极度超买 → 强卖出(90-100分)
- K上穿D: 金叉 → 买入(85分)
- K下穿D: 死叉 → 卖出(85分)
- **低位金叉**(K<30金叉): 最强买入(100分)
- **高位死叉**(K>70死叉): 最强卖出(100分)

**评分**: 最高7分

**配置参数**:
```python
KDJ_PARAMS = {
    'period': 9,
    'signal': 3
}
```

##### CCI (顺势指标)
**参数**: 周期20

**信号规则**:
- CCI < -200: 极度超卖 → 强买入(100分)
- -200 < CCI < -100: 超卖区 → 买入(80-100分)
- CCI > 200: 极度超买 → 强卖出(100分)
- 100 < CCI < 200: 超买区 → 卖出(80-100分)
- CCI穿越零轴: 买卖信号(75分)
- 从超卖/超买区反弹: 强信号(85分)

**评分**: 最高6分(辅助指标)

**配置参数**:
```python
CCI_PARAMS = {
    'period': 20
}
```

---

#### 3️⃣ 时机层 - MACD + BOLL + ATR
**作用**: 确认进场时机和市场波动率

##### MACD (平滑异同移动平均线)
**参数**: 快线12, 慢线26, 信号线9

**信号规则**:
- **金叉**: MACD上穿信号线 → 买入
  - 零轴上方金叉: 强买入(100分)
  - 零轴下方金叉: 买入(85分)
- **死叉**: MACD下穿信号线 → 卖出
  - 零轴下方死叉: 强卖出(100分)
  - 零轴上方死叉: 卖出(85分)
- 柱状图方向: 辅助判断(60分)

**评分**: 最高7分

**配置参数**:
```python
MACD_PARAMS = {
    'fast_period': 12,
    'slow_period': 26,
    'signal_period': 9
}
```

##### BOLL (布林带)
**参数**: 周期20, 标准差2.0

**信号规则**:
- %B < 0: 跌破下轨 → 强买入(100分)
- %B < 0.1: 触及下轨 → 买入(90分)
- %B < 0.2: 接近下轨 → 买入(70分)
- %B > 1: 突破上轨 → 强卖出(100分)
- %B > 0.9: 触及上轨 → 卖出(90分)
- %B > 0.8: 接近上轨 → 卖出(70分)

**评分**: 最高7分

**配置参数**:
```python
BB_PARAMS = {
    'period': 20,
    'std_dev': 2.0
}
```

##### ATR (真实波动幅度)
**参数**: 周期14

**信号规则**:
- ATR扩大且收盘在上方: 多头趋势加速(70分)
- ATR扩大且收盘在下方: 空头趋势加速(70分)
- 大阳线突破(幅度>1.5倍ATR): 强买入(75分)
- 大阴线突破(幅度>1.5倍ATR): 强卖出(75分)
- 波动率收缩: 警惕突破(40分)

**评分**: 最高6分(辅助指标)

**配置参数**:
```python
ATR_PARAMS = {
    'period': 14
}
```

---

#### 4️⃣ 可选层 - VWAP (日内基准)
**作用**: 日内交易的价格基准,适合1m/5m短周期

**信号规则**:
- 价格上穿VWAP: 买入(90分)
- 价格下穿VWAP: 卖出(90分)
- 远高于VWAP(+2%): 可能回落,卖出(70分)
- 远低于VWAP(-2%): 可能反弹,买入(70分)
- 偏离±0.5%内: 中性

**评分**: 最高5分(可选指标)

**配置参数**:
```python
# VWAP无需参数,自动计算
```

---

## 🎯 共振策略评分系统

### 总分构成(100分制)

```
总分 = 趋势得分(25分) + 指标共振得分(50分) + 动量得分(15分) + 时机得分(10分)
```

#### 1. 趋势一致性得分 (25分)
- 完美趋势排列: 25分
- 部分趋势排列: 按信号强度给分
- 趋势不明: 0分
- **惩罚**: 逆趋势交易,总分减半

#### 2. 指标共振得分 (50分)
```
核心指标(每个7分): RSI + KDJ + MACD + BOLL = 28分
辅助指标(每个6分): CCI + ATR = 12分
可选指标(5分): VWAP = 5分
总计: 最高45-50分
```

**计算公式**:
```python
指标得分 = (指标强度 / 100) × 指标满分
```

#### 3. 动量确认得分 (15分)
- 价格变化 > 0.1%: +8分
- 价格偏离均线 > 0.2%: +7分
- 价格偏离均线 > 0.5%: 再+3分
- **惩罚**: 动量未确认,总分打8折

#### 4. 时机把握得分 (10分)
- 4个以上指标共振: 10分(时机完美)
- 3个指标共振: 7分(时机良好)
- 少于3个: 0分

### 信号生成条件

要生成有效的交易信号,必须同时满足:

1. **共振要求**: 至少N个指标同向(N由配置决定,默认5/7)
2. **最低评分**: 总分 ≥ 70分(可配置)
3. **波动率检查**: 0.0005 < 波动率 < 0.05
4. **K线状态**: 必须在K线关闭时才生成信号

### 信号过滤器

#### 趋势过滤器
```python
if use_trend_filter and 趋势不一致:
    总分 *= 0.5  # 减半
```

#### 动量过滤器
```python
if use_momentum_filter and 动量未确认:
    总分 *= 0.8  # 打8折
```

#### 波动率过滤器
```python
if 波动率 < 0.0005 or 波动率 > 0.05:
    放弃信号  # 直接放弃
```

---

## ⚙️ 配置说明

### 指标开关配置
```python
INDICATOR_SWITCHES = {
    'use_macd': True,    # 启用MACD(动量层)
    'use_rsi': True,     # 启用RSI(动量层)
    'use_kdj': True,     # 启用KDJ(动量层)
    'use_boll': False,   # 启用布林带(时机层)
    'use_ema': False,    # 启用EMA四线系统(趋势层)
    'use_cci': True,     # 启用CCI(动量层)
    'use_atr': True,     # 启用ATR(波动率层)
    'use_vwap': False    # 启用VWAP(日内交易基准,适合短周期如1m/5m)
}
```

**注意事项**:
- 至少启用3个指标,否则共振机制无法有效工作
- `use_ema`控制趋势过滤,关闭后不进行趋势一致性检查
- `use_vwap`仅建议在1m/5m等短周期使用

### 共振策略配置
```python
RESONANCE_PARAMS = {
    'min_resonance': None,  # 最少共振指标数量
                            # None=自动计算(启用指标数*0.7,向上取整)
                            # 或手动指定如5

    'min_score': 70.0,      # 最低评分(0-100)
                            # 推荐60-80之间
                            # 越高越严格,信号越少但质量越高
}
```

#### min_resonance自动计算逻辑
```python
def get_min_resonance():
    enabled_count = sum(INDICATOR_SWITCHES.values())
    min_resonance = math.ceil(enabled_count * 0.7)
    return max(2, min_resonance)  # 至少要2个指标
```

**示例**:
- 启用7个指标 → min_resonance = 5 (70%向上取整)
- 启用5个指标 → min_resonance = 4
- 启用3个指标 → min_resonance = 3

### 交易对配置
```python
DEFAULT_SYMBOL = "BTCUSDT"       # 交易对
DEFAULT_INTERVAL = "5m"          # K线周期(1m/3m/5m/15m/30m/1h/4h/1d)
DEFAULT_CONTRACT_TYPE = "perpetual"  # 合约类型
MIN_SIGNALS = 3                  # 已弃用,使用RESONANCE_PARAMS
```

### WebSocket配置
```python
# Binance API域名
BINANCE_API_URL = "https://fapi.binance.com"
BINANCE_WS_URL = "wss://fstream.binance.com"

# 代理配置(如果无法访问Binance)
USE_PROXY = True
PROXY_URL = 'socks5://127.0.0.1:7897'

# WebSocket重连配置
WS_PING_INTERVAL = 20   # ping间隔(秒)
WS_PING_TIMEOUT = 10    # ping超时(秒)
WS_CLOSE_TIMEOUT = 5    # 关闭超时(秒)
MAX_RETRIES = 10        # 最大重试次数
HEARTBEAT_INTERVAL = 10 # 心跳日志输出间隔(秒)
```

---

## 📈 信号验证机制

系统会自动追踪每个生成的信号,并在3个时间点验证预测准确性:

### 验证时间点
- **10分钟后**: 短期预测
- **30分钟后**: 中期预测
- **1小时后**: 长期预测

### 验证逻辑
```python
if 当前价格 > 开仓价格:
    实际结果 = "HIGHER"
elif 当前价格 < 开仓价格:
    实际结果 = "LOWER"
else:
    实际结果 = "EQUAL"

是否正确 = (预测方向 == 实际结果)
```

### 准确率统计
系统实时计算并显示:
- 10分钟准确率 = 正确次数 / 验证次数
- 30分钟准确率 = 正确次数 / 验证次数
- 1小时准确率 = 正确次数 / 验证次数

---

## 🚀 使用指南

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基本运行
```bash
python live_trading_resonance.py
```

### 自定义配置运行

#### 方式1: 修改config.py
直接编辑[config.py](config.py)文件,修改参数后运行

#### 方式2: 代码中覆盖配置
```python
# 创建策略时覆盖参数
strategy = ResonanceMultiIndicatorStrategy(
    # 覆盖指标参数
    rsi_period=10,
    macd_fast=8,
    # 覆盖指标开关
    use_boll=True,
    use_ema=True,
    # 覆盖共振参数
    min_resonance=4,
    min_score=75.0
)

# 创建交易系统时覆盖参数
system = BinanceResonanceLiveTradingSystem(
    symbol="ETHUSDT",
    interval="1m",
    strategy=strategy
)
```

---

## 📊 Dashboard界面说明

系统运行时会显示Rich控制台界面,分为5个区域:

### 1. 系统状态区(Header)
- 交易对和周期
- WebSocket连接状态
- 消息数和心跳时间
- 最小联动指标数

### 2. 行情 & 建议区(Market)
- 最新K线数据(开高低收量)
- 实时交易建议(做多/做空/观望)
- 置信度进度条
- 指标投票统计(多少个指标看涨/看跌)

### 3. 核心指标区(Indicators)
显示所有启用的指标及其信号:
- **MACD**: MACD线、信号线、柱状图
- **RSI**: RSI值、超买超卖状态
- **BOLL**: 上中下轨、%B位置
- **KDJ**: K、D、J值、金叉死叉状态
- **EMA**: 四条均线值、趋势方向
- **CCI**: CCI值、超买超卖状态
- **ATR**: 波动率值、波动强度
- **VWAP**: VWAP值(如果启用)

### 4. 信号跟踪区(Signals)
- 最新信号详情
- 活跃信号列表(待验证)
- 验证进度(10分钟/30分钟/1小时)

### 5. 统计 & 事件区(Footer)
- 准确率统计表
- 总信号数、待验证数、已完成数
- 实时事件推送(连接、信号、验证等)

---

## 📝 日志文件

### trade_signals_resonance.log
记录所有交易信号和验证结果

**日志内容**:
- 新信号生成时的详细信息
- 各指标详情和评分
- 预测方向(10分钟/30分钟/1小时)
- 验证结果和价格变化
- 信号总结(完成所有验证后)

**示例**:
```
================================================================================
[新信号] ID: BUY_1764249000000
时间: 2024-01-15 21:30:00
类型: BUY
开仓价格: 90790.00
评分: 总分78.5/100, 信心度78.5%
共振: 5/7个指标, 趋势一致: ✓

各指标详情:
  [RSI] 超卖区(RSI=28.3)
           得分: 6.85
  [KDJ] KDJ: K<20 且 D<20 双超卖
           得分: 6.72
  [MACD] MACD: 零轴下方金叉（强势）
           得分: 5.95
  [CCI] CCI: 从超卖区反弹(-105.2->-82.3)
           得分: 5.10
  [ATR] ATR: 波动率扩大且收高(ATR+12.3%)
           得分: 4.20

预测:
  - 10分钟: HIGHER
  - 30分钟: HIGHER
  - 1小时: HIGHER

信号原因:
  - 总评分: 78.5/100, 信心度: 78.5%
  - 共振指标数: 5/7
  - 趋势: 趋势BULLISH, 得分23.2
  - [RSI] 超卖区(RSI=28.3) (强度75, 得分6.85)
  - ...
================================================================================

[10分钟验证] ID: BUY_1764249000000
验证时间: 2024-01-15 21:40:15
预测方向: HIGHER | 实际结果: HIGHER | ✓ 正确
开仓价格: 90790.00
当前价格: 90950.30
价格变化: +160.30 (+0.18%)
```

---

## 🔧 常见问题

### Q1: 为什么调整INDICATOR_SWITCHES后总是报错?
**A**: 这是因为原代码在计算总指标数时没有动态根据启用的指标数量来计算。已修复,现在会根据实际启用的指标数量自动计算。

**修复代码** ([resonance_strategy.py:901-909](resonance_strategy.py#L901-L909)):
```python
# 计算总指标数（根据启用的指标）
total_indicators = sum([
    self.use_rsi,
    self.use_kdj,
    self.use_macd,
    self.use_boll,
    self.use_cci,
    self.use_atr,
    self.use_vwap
])
```

### Q2: 为什么没有信号生成?
**可能原因**:
1. 共振指标数不足: 启用的指标太少,或min_resonance设置过高
2. 评分不达标: min_score设置过高(如90),很难达到
3. 波动率不合适: 市场过于平静或暴涨暴跌
4. 趋势过滤: 所有指标都看多,但主趋势是空头(或相反)

**解决方法**:
- 降低min_score到60-70
- 确保至少启用5个指标
- 检查波动率过滤参数
- 暂时关闭趋势过滤(use_ema=False)

### Q3: 如何提高信号准确率?
**建议**:
1. 提高min_score: 从70提高到75-80
2. 提高min_resonance: 要求更多指标共振
3. 启用所有过滤器: 趋势、动量、波动率
4. 选择合适的K线周期: 5m-15m较为稳定
5. 避免重大新闻时段: 基本面冲击会导致技术分析失效

### Q4: 为什么显示"处理消息错误"?
**A**: 已修复,现在会显示具体的错误信息([live_trading_resonance.py:1209-1213](live_trading_resonance.py#L1209-L1213)):
```python
except Exception as e:
    if self.use_dashboard:
        self.dashboard.push_alert(f"处理消息错误: {str(e)}", level="error")
    print(f"[错误] 处理K线消息时出错: {e}")
    import traceback
    traceback.print_exc()
```

### Q5: 代理配置无效?
**检查**:
1. USE_PROXY是否设置为True
2. PROXY_URL格式是否正确(socks5://或http://)
3. 代理服务是否运行
4. 是否安装了aiohttp-socks: `pip install aiohttp-socks`

### Q6: 如何导出结果?
```python
# 按Ctrl+C停止系统时,会自动导出到:
# live_trading_resonance_results.json

# 或手动调用:
system.export_results("my_results.json")
```

---

## 📚 策略优化建议

### 初学者配置(保守型)
```python
INDICATOR_SWITCHES = {
    'use_macd': True,
    'use_rsi': True,
    'use_kdj': True,
    'use_boll': True,
    'use_ema': True,    # 启用趋势过滤
    'use_cci': True,
    'use_atr': True,
    'use_vwap': False
}

RESONANCE_PARAMS = {
    'min_resonance': 5,   # 7个指标中要5个共振
    'min_score': 75.0,    # 较高评分要求
}
```

### 进阶配置(平衡型)
```python
INDICATOR_SWITCHES = {
    'use_macd': True,
    'use_rsi': True,
    'use_kdj': True,
    'use_boll': False,   # 关闭布林带
    'use_ema': False,    # 关闭趋势过滤
    'use_cci': True,
    'use_atr': True,
    'use_vwap': False
}

RESONANCE_PARAMS = {
    'min_resonance': None,  # 自动计算(5个指标*0.7=4)
    'min_score': 70.0,
}
```

### 激进配置(高频型)
```python
INDICATOR_SWITCHES = {
    'use_macd': True,
    'use_rsi': True,
    'use_kdj': True,
    'use_boll': False,
    'use_ema': False,
    'use_cci': False,
    'use_atr': False,
    'use_vwap': False
}

RESONANCE_PARAMS = {
    'min_resonance': 2,   # 仅需2个指标共振
    'min_score': 60.0,    # 较低评分要求
}
```

### 日内交易配置
```python
DEFAULT_INTERVAL = "1m"  # 1分钟K线

INDICATOR_SWITCHES = {
    'use_macd': True,
    'use_rsi': True,
    'use_kdj': True,
    'use_boll': True,
    'use_ema': True,
    'use_cci': True,
    'use_atr': True,
    'use_vwap': True,    # 启用VWAP
}

RESONANCE_PARAMS = {
    'min_resonance': 6,   # 8个指标中要6个
    'min_score': 70.0,
}
```

---

## ⚠️ 风险提示

1. **本系统仅供学习研究**: 不构成投资建议
2. **历史表现不代表未来**: 回测优秀不等于实盘盈利
3. **杠杆风险**: 永续合约有高杠杆,请谨慎使用
4. **技术分析局限**: 无法预测黑天鹅事件和基本面冲击
5. **网络风险**: WebSocket断线可能导致错过信号
6. **API限制**: 注意Binance API请求频率限制

**建议**:
- 小资金测试
- 设置止损止盈
- 不要全仓一个信号
- 关注市场重大新闻
- 定期检查系统运行状态

---

## 📞 技术支持

如遇问题,请检查:
1. 配置文件是否正确
2. 网络连接是否正常
3. 依赖包是否安装完整
4. 日志文件中的错误信息

---

## 📄 更新日志

### v1.1.0 (2025-01-27)
- ✅ 修复INDICATOR_SWITCHES配置调整后报错问题
- ✅ 修复错误信息不显示问题
- ✅ 优化total_indicators计算逻辑
- ✅ 改进错误处理和日志输出

### v1.0.0 (2025-01-XX)
- ✅ 首次发布
- ✅ 7指标共振系统
- ✅ 实时交易信号生成
- ✅ 自动验证和统计
- ✅ Rich Dashboard界面

---

## 🎓 学习资源

### 技术指标学习
- MACD: 趋势跟踪指标,捕捉动能变化
- RSI: 超买超卖指标,判断市场情绪
- KDJ: 随机指标,短期买卖点
- 布林带: 波动率通道,支撑压力
- EMA: 指数移动平均,趋势判断
- CCI: 顺势指标,极端值信号
- ATR: 真实波动幅度,风险管理
- VWAP: 成交量加权均价,日内基准

### 推荐阅读
- 《技术分析精解》
- 《量化交易:如何建立自己的算法交易》
- TradingView技术指标文档

---

## 📜 许可证

MIT License

---

**祝交易顺利!** 🚀📈
