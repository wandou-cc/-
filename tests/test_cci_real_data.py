"""
使用真实K线数据测试CCI指标
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from datetime import datetime
from indicators.cci_indicator import CCIIndicator, CCIAnalyzer

# 读取K线数据
with open(os.path.join(os.path.dirname(__file__), 'K.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

# 解析数据
# 数据格式: [时间戳, 开盘价, 最高价, 最低价, 收盘价, 其他]
klines = data['data']

# 数据是倒序的（最新的在前），需要反转
klines.reverse()

# 提取价格数据
timestamps = []
opens = []
highs = []
lows = []
closes = []

for kline in klines:
    timestamps.append(int(kline[0]))
    opens.append(float(kline[1]))
    highs.append(float(kline[2]))
    lows.append(float(kline[3]))
    closes.append(float(kline[4]))

print("="*120)
print("CCI指标测试 - 使用真实BTC K线数据")
print("="*120)
print(f"数据总数: {len(closes)} 根K线")
print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"价格范围: ${min(lows):,.2f} - ${max(highs):,.2f}")
print("="*120)

# 计算CCI
cci = CCIIndicator(period=20)
result = cci.calculate(highs, lows, closes)

print(f"\nCCI计算周期: 20")
print(f"CCI值数量: {len(result['cci'])} (前19根K线数据不足)")
print("="*120)

# 显示最近30个CCI值
print("\n【最近30根K线的CCI值】\n")
print(f"{'序号':<6} {'时间':<20} {'开盘价':>12} {'最高价':>12} {'最低价':>12} {'收盘价':>12} {'典型价':>12} {'CCI':>10} {'状态':<15}")
print("-"*130)

# 计算要显示的范围
start_idx = max(0, len(result['cci']) - 30)
for i in range(start_idx, len(result['cci'])):
    data_idx = i + 19  # 对应原始数据的索引
    timestamp = timestamps[data_idx]
    time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

    open_price = opens[data_idx]
    high_price = highs[data_idx]
    low_price = lows[data_idx]
    close_price = closes[data_idx]
    typical_price = result['typical_price'][i]
    cci_val = result['cci'][i]

    # 判断状态
    if cci_val > 200:
        status = "强烈超买"
    elif cci_val > 100:
        status = "超买"
    elif cci_val > 0:
        status = "看涨"
    elif cci_val < -200:
        status = "强烈超卖"
    elif cci_val < -100:
        status = "超卖"
    elif cci_val < 0:
        status = "看跌"
    else:
        status = "中性"

    print(f"{data_idx+1:<6} {time_str:<20} ${open_price:>11,.2f} ${high_price:>11,.2f} ${low_price:>11,.2f} ${close_price:>11,.2f} ${typical_price:>11,.2f} {cci_val:>9.2f} {status:<15}")

print("\n" + "="*120)

# 显示详细计算过程（最后5根K线）
print("\n【详细计算过程 - 最后5根K线】\n")
for i in range(max(0, len(result['cci']) - 5), len(result['cci'])):
    data_idx = i + 19
    timestamp = timestamps[data_idx]
    time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

    print(f"K线 #{data_idx+1} ({time_str})")
    print(f"  价格数据: 高={highs[data_idx]:,.2f}, 低={lows[data_idx]:,.2f}, 收={closes[data_idx]:,.2f}")
    print(f"  典型价格 TP = (高 + 低 + 收) / 3 = {result['typical_price'][i]:,.2f}")
    print(f"  20周期SMA = {result['sma'][i]:,.2f}")
    print(f"  平均偏差 MD = {result['mean_deviation'][i]:,.4f}")
    print(f"  CCI = (TP - SMA) / (0.015 × MD)")
    print(f"      = ({result['typical_price'][i]:,.2f} - {result['sma'][i]:,.2f}) / (0.015 × {result['mean_deviation'][i]:,.4f})")
    print(f"      = {result['cci'][i]:.2f}")

    # 判断超买超卖
    if result['cci'][i] > 100:
        print(f"  状态: 超买区域 (CCI > 100)")
    elif result['cci'][i] < -100:
        print(f"  状态: 超卖区域 (CCI < -100)")
    else:
        print(f"  状态: 正常区域 (-100 <= CCI <= 100)")
    print()

print("="*120)

# 统计信息
print("\n【CCI统计信息】\n")
cci_values = result['cci']
print(f"CCI值数量: {len(cci_values)}")
print(f"最大CCI: {max(cci_values):.2f}")
print(f"最小CCI: {min(cci_values):.2f}")
print(f"平均CCI: {sum(cci_values)/len(cci_values):.2f}")
print(f"最新CCI: {cci_values[-1]:.2f}")

# 价格统计
latest_price = closes[-1]
print(f"\n最新价格: ${latest_price:,.2f}")
print(f"最高价: ${max(closes):,.2f}")
print(f"最低价: ${min(closes):,.2f}")
print(f"平均价: ${sum(closes)/len(closes):,.2f}")

# 超买超卖统计
overbought_200 = sum(1 for v in cci_values if v > 200)
overbought_100 = sum(1 for v in cci_values if v > 100)
oversold_100 = sum(1 for v in cci_values if v < -100)
oversold_200 = sum(1 for v in cci_values if v < -200)
neutral = len(cci_values) - overbought_100 - oversold_100

print(f"\n【CCI分布统计】")
print(f"强烈超买 (>200): {overbought_200} 次 ({overbought_200/len(cci_values)*100:.1f}%)")
print(f"超买 (>100): {overbought_100} 次 ({overbought_100/len(cci_values)*100:.1f}%)")
print(f"中性 (-100~100): {neutral} 次 ({neutral/len(cci_values)*100:.1f}%)")
print(f"超卖 (<-100): {oversold_100} 次 ({oversold_100/len(cci_values)*100:.1f}%)")
print(f"强烈超卖 (<-200): {oversold_200} 次 ({oversold_200/len(cci_values)*100:.1f}%)")

# 使用分析器检测交易信号
print("\n" + "="*120)
print("\n【使用CCI分析器检测交易信号】\n")

cci2 = CCIIndicator(period=20)
analyzer = CCIAnalyzer(cci2)

buy_signals = []
sell_signals = []

for i in range(len(closes)):
    cci2.update(highs[i], lows[i], closes[i])
    signal = analyzer.get_signal(overbought=100, oversold=-100)
    
    if signal == 'BUY':
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        current = cci2.get_current_values()
        buy_signals.append((i, time_str, closes[i], current['cci']))
    elif signal == 'SELL':
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        current = cci2.get_current_values()
        sell_signals.append((i, time_str, closes[i], current['cci']))

print(f"检测到 {len(buy_signals)} 个买入信号，{len(sell_signals)} 个卖出信号\n")

if buy_signals:
    print("买入信号:")
    for idx, time_str, price, cci_val in buy_signals[-10:]:  # 最近10个
        print(f"  {time_str} - 价格: ${price:,.2f}, CCI: {cci_val:.2f}")

if sell_signals:
    print("\n卖出信号:")
    for idx, time_str, price, cci_val in sell_signals[-10:]:  # 最近10个
        print(f"  {time_str} - 价格: ${price:,.2f}, CCI: {cci_val:.2f}")

# 当前状态分析
print("\n" + "="*120)
print("\n【当前市场状态】\n")

current = cci2.get_current_values()
momentum = analyzer.get_momentum_level()
trend = analyzer.get_trend_direction()

print(f"当前时间: {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"当前价格: ${closes[-1]:,.2f}")
print(f"当前CCI: {current['cci']:.2f}")
print(f"动量水平: {momentum}")
print(f"趋势方向: {trend}")

if current['cci'] > 100:
    print(f"\n⚠️  警告: CCI处于超买区域，价格可能过高，注意回调风险")
elif current['cci'] < -100:
    print(f"\n💡 提示: CCI处于超卖区域，价格可能被低估，可能是买入机会")
elif current['cci'] > 0:
    print(f"\n📈 市场处于看涨区域，价格在平均水平之上")
else:
    print(f"\n📉 市场处于看跌区域，价格在平均水平之下")

print("\n" + "="*120)
print("测试完成！")
print("="*120)

