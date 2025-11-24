"""
测试0轴距离过滤功能 - 对比不同阈值的效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from datetime import datetime
from indicators.macd_indicator import MACDIndicator, MACDAnalyzer

# 读取K线数据
with open(os.path.join(os.path.dirname(__file__), 'K.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

# 解析数据
klines = data['data']
klines.reverse()

# 提取价格数据
timestamps = []
closes = []

for kline in klines:
    timestamps.append(int(kline[0]))
    closes.append(float(kline[4]))

print("="*100)
print("0轴距离过滤功能测试 - 对比不同阈值的效果")
print("="*100)
print(f"数据总数: {len(closes)} 根K线")
print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print("="*100)

# 测试不同的0轴距离阈值
test_thresholds = [0.0, 5.0, 10.0, 20.0, 50.0, 100.0]

print(f"\n{'阈值':<10} {'总信号':<10} {'强金叉':<10} {'弱金叉':<10} {'强死叉':<10} {'弱死叉':<10} {'过滤率':<10}")
print("-"*100)

for threshold in test_thresholds:
    macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
    analyzer = MACDAnalyzer(
        macd,
        min_cross_strength=100.0,
        angle_multiplier=0.5,
        min_hist_threshold=0.0005,
        lookback_period=50,
        min_zero_distance=threshold
    )

    strong_golden = 0
    weak_golden = 0
    strong_dead = 0
    weak_dead = 0
    total_crosses = 0  # 检测到的所有交叉

    for price in closes:
        macd.update(price)
        result = analyzer.get_filtered_signal()

        if result['cross_detected']:
            total_crosses += 1

        if result['signal'] == 'strong_golden':
            strong_golden += 1
        elif result['signal'] == 'weak_golden':
            weak_golden += 1
        elif result['signal'] == 'strong_dead':
            strong_dead += 1
        elif result['signal'] == 'weak_dead':
            weak_dead += 1

    total_signals = strong_golden + weak_golden + strong_dead + weak_dead
    filter_rate = (1 - total_signals / total_crosses) * 100 if total_crosses > 0 else 0

    print(f"{threshold:<10.1f} {total_signals:<10} {strong_golden:<10} {weak_golden:<10} {strong_dead:<10} {weak_dead:<10} {filter_rate:<10.1f}%")

print("\n" + "="*100)
print("详细分析 - 阈值为10.0时的信号详情")
print("="*100)

# 使用阈值10.0重新运行，显示详细信息
macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
analyzer = MACDAnalyzer(
    macd,
    min_cross_strength=100.0,
    angle_multiplier=0.5,
    min_hist_threshold=0.0005,
    lookback_period=50,
    min_zero_distance=10.0
)

signals = []
for i in range(len(closes)):
    macd.update(closes[i])
    result = analyzer.get_filtered_signal()

    if result['signal'] != 'none':
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        signals.append((i, time_str, closes[i], result))

print(f"\n检测到 {len(signals)} 个有效信号\n")

if signals:
    print(f"{'序号':<6} {'时间':<20} {'价格':>12} {'信号类型':<20} {'0轴距':<10} {'通过':<6}")
    print("-"*100)

    for idx, time_str, price, result in signals:
        signal_type = result['signal']
        zero_distance = result['metrics']['zero_distance']
        zero_pass = '✓' if result['conditions']['zero_distance_check'] else '✗'

        print(f"{idx+1:<6} {time_str:<20} ${price:>11,.2f} {signal_type:<20} {zero_distance:<10.2f} {zero_pass:<6}")

print("\n" + "="*100)
print("对比总结")
print("="*100)
print("""
通过设置合理的0轴距离阈值，可以有效过滤弱信号：

1. 阈值=0.0（不过滤）：
   - 会检测到所有金叉死叉，包括很多靠近0轴的弱信号
   - 信号数量最多，但质量参差不齐

2. 阈值=10.0（推荐）：
   - 过滤掉靠近0轴的大部分弱信号
   - 保留了强度较高的信号
   - 信号数量适中，质量较好

3. 阈值=50.0或更高：
   - 只保留距离0轴很远的信号
   - 信号数量很少，但都是强信号
   - 可能会错过一些中等强度的有效信号

建议：
- 比特币等高波动资产：推荐阈值10-50
- 股票等中等波动资产：推荐阈值0.5-2.0
- 根据实际回测结果调整阈值
""")

print("="*100)
print("测试完成！")
print("="*100)
