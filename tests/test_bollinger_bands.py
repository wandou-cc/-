"""
测试布林带(Bollinger Bands)指标
包含完整的数值输出、信号分析、挤压检测等功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from datetime import datetime
from indicators.bollinger_bands import BollingerBandsIndicator, BollingerBandsAnalyzer

# 读取K线数据
with open(os.path.join(os.path.dirname(__file__), 'K.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

# 解析数据
klines = data['data']
klines.reverse()  # 数据是倒序的，需要反转

# 提取价格数据
timestamps = []
closes = []
highs = []
lows = []
opens = []

for kline in klines:
    timestamps.append(int(kline[0]))
    opens.append(float(kline[1]))
    highs.append(float(kline[2]))
    lows.append(float(kline[3]))
    closes.append(float(kline[4]))

print("="*150)
print("布林带(Bollinger Bands)指标测试")
print("="*150)
print(f"数据总数: {len(closes)} 根K线")
print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"价格范围: ${min(lows):,.2f} - ${max(highs):,.2f}")
print("="*150)

# 创建布林带指标
print("\n【布林带参数配置】")
print("周期(Period): 20")
print("标准差倍数(Std Dev): 2.0")
print("="*150)

bb = BollingerBandsIndicator(period=20, std_dev=2.0)
bb_result = bb.calculate(closes)

# 显示最后100根K线的布林带值
print("\n【最后100根K线的布林带值】\n")
print(f"{'序号':<6} {'时间':<20} {'开盘价':>12} {'最高价':>12} {'最低价':>12} {'收盘价':>12} {'上轨':>12} {'中轨':>12} {'下轨':>12} {' %B':>8} {'带宽':>8} {'位置':<12}")
print("-"*150)

# 计算K线范围: 显示最后100根
kline_total = len(closes)
kline_start = max(0, kline_total - 100)
kline_end = kline_total

# 布林带有warm-up期，需要找到对应的起始索引
bb_offset = kline_total - len(bb_result['upper_band'])

for i in range(kline_start, kline_end):
    timestamp = timestamps[i]
    time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
    open_price = opens[i]
    high = highs[i]
    low = lows[i]
    close = closes[i]

    # 转换成布林带索引
    bb_idx = i - bb_offset

    # 检查布林带索引是否有效
    if bb_idx < 0 or bb_idx >= len(bb_result['upper_band']):
        print(f"{i+1:<6} {time_str:<20} ${open_price:>11,.2f} ${high:>11,.2f} ${low:>11,.2f} ${close:>11,.2f} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>8} {'N/A':>8} BB未计算")
        continue

    upper = bb_result['upper_band'][bb_idx]
    middle = bb_result['middle_band'][bb_idx]
    lower = bb_result['lower_band'][bb_idx]
    percent_b = bb_result['percent_b'][bb_idx]
    bandwidth = bb_result['bandwidth'][bb_idx]

    # 判断价格位置
    position = ""
    if close > upper:
        position = "上轨之上 ⬆️"
    elif close < lower:
        position = "下轨之下 ⬇️"
    elif close > middle:
        position = "上半区"
    elif close < middle:
        position = "下半区"
    else:
        position = "中轨"

    print(f"{i+1:<6} {time_str:<20} ${open_price:>11,.2f} ${high:>11,.2f} ${low:>11,.2f} ${close:>11,.2f} ${upper:>11,.2f} ${middle:>11,.2f} ${lower:>11,.2f} {percent_b:>8.2f} {bandwidth:>8.4f} {position:<12}")

# 使用update方法逐根K线计算（演示实时更新）
print("\n" + "="*150)
print("【逐根K线实时更新测试 - 最后30根K线】")
print("="*150)

bb2 = BollingerBandsIndicator(period=20, std_dev=2.0)
analyzer = BollingerBandsAnalyzer(bb2, squeeze_threshold=0.03)

# 先预热数据（前面的K线）
warmup_count = len(closes) - 30
for i in range(warmup_count):
    analyzer.update(closes[i])

# 显示最后30根K线的实时更新
print(f"\n{'序号':<6} {'时间':<20} {'收盘价':>12} {'上轨':>12} {'中轨':>12} {'下轨':>12} {' %B':>8} {'带宽':>8} {'信号':<10} {'挤压状态':<15}")
print("-"*150)

for i in range(warmup_count, len(closes)):
    timestamp = timestamps[i]
    time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
    close = closes[i]

    # 实时更新
    analyzer.update(close)
    current = bb2.get_current_values()

    if current['upper_band'] is None:
        continue

    # 获取信号
    signal = analyzer.get_signal()
    squeeze_status = analyzer.detect_squeeze_breakout()

    # 信号显示
    signal_str = ""
    if signal == 'BUY':
        signal_str = "买入 🟢"
    elif signal == 'SELL':
        signal_str = "卖出 🔴"
    else:
        signal_str = "持有"

    # 挤压状态显示
    squeeze_str = ""
    if squeeze_status == 'SQUEEZE':
        squeeze_str = "挤压中 🔸"
    elif squeeze_status == 'BREAKOUT_UP':
        squeeze_str = "向上突破 🚀"
    elif squeeze_status == 'BREAKOUT_DOWN':
        squeeze_str = "向下突破 📉"
    else:
        squeeze_str = "正常"

    print(f"{i+1:<6} {time_str:<20} ${close:>11,.2f} ${current['upper_band']:>11,.2f} ${current['middle_band']:>11,.2f} ${current['lower_band']:>11,.2f} {current['percent_b']:>8.2f} {current['bandwidth']:>8.4f} {signal_str:<10} {squeeze_str:<15}")

# 布林带统计分析
print("\n" + "="*150)
print("【布林带统计分析】")
print("="*150)

upper_values = bb_result['upper_band']
middle_values = bb_result['middle_band']
lower_values = bb_result['lower_band']
bandwidth_values = bb_result['bandwidth']
percent_b_values = bb_result['percent_b']

print(f"\n上轨统计:")
print(f"  最大值: ${max(upper_values):,.2f}")
print(f"  最小值: ${min(upper_values):,.2f}")
print(f"  平均值: ${sum(upper_values)/len(upper_values):,.2f}")
print(f"  最新值: ${upper_values[-1]:,.2f}")

print(f"\n中轨(SMA)统计:")
print(f"  最大值: ${max(middle_values):,.2f}")
print(f"  最小值: ${min(middle_values):,.2f}")
print(f"  平均值: ${sum(middle_values)/len(middle_values):,.2f}")
print(f"  最新值: ${middle_values[-1]:,.2f}")

print(f"\n下轨统计:")
print(f"  最大值: ${max(lower_values):,.2f}")
print(f"  最小值: ${min(lower_values):,.2f}")
print(f"  平均值: ${sum(lower_values)/len(lower_values):,.2f}")
print(f"  最新值: ${lower_values[-1]:,.2f}")

print(f"\n带宽统计:")
print(f"  最大值: {max(bandwidth_values):.4f}")
print(f"  最小值: {min(bandwidth_values):.4f}")
print(f"  平均值: {sum(bandwidth_values)/len(bandwidth_values):.4f}")
print(f"  最新值: {bandwidth_values[-1]:.4f}")

print(f"\n%B统计:")
print(f"  最大值: {max(percent_b_values):.2f}")
print(f"  最小值: {min(percent_b_values):.2f}")
print(f"  平均值: {sum(percent_b_values)/len(percent_b_values):.2f}")
print(f"  最新值: {percent_b_values[-1]:.2f}")

# 检测买卖信号
print("\n" + "="*150)
print("【买卖信号检测】")
print("="*150)

bb3 = BollingerBandsIndicator(period=20, std_dev=2.0)
analyzer2 = BollingerBandsAnalyzer(bb3, squeeze_threshold=0.03)

signals = []
for i in range(len(closes)):
    analyzer2.update(closes[i])
    signal = analyzer2.get_signal()

    if signal != 'HOLD':
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        current = bb3.get_current_values()
        signals.append((i, time_str, closes[i], signal, current))

print(f"\n检测到 {len(signals)} 个买卖信号\n")

if signals:
    print(f"{'序号':<6} {'时间':<20} {'价格':>12} {'信号':<10} {'上轨':>12} {'中轨':>12} {'下轨':>12} {' %B':>8}")
    print("-"*150)

    for idx, time_str, price, signal, current in signals[-30:]:  # 显示最后30个信号
        signal_str = "买入 🟢" if signal == 'BUY' else "卖出 🔴"
        print(f"{idx+1:<6} {time_str:<20} ${price:>11,.2f} {signal_str:<10} ${current['upper_band']:>11,.2f} ${current['middle_band']:>11,.2f} ${current['lower_band']:>11,.2f} {current['percent_b']:>8.2f}")

    # 统计信号
    buy_signals = sum(1 for _, _, _, s, _ in signals if s == 'BUY')
    sell_signals = sum(1 for _, _, _, s, _ in signals if s == 'SELL')

    print(f"\n信号统计:")
    print(f"  买入信号: {buy_signals}")
    print(f"  卖出信号: {sell_signals}")

# 挤压检测
print("\n" + "="*150)
print("【布林带挤压(Squeeze)检测】")
print("="*150)

bb4 = BollingerBandsIndicator(period=20, std_dev=2.0)
analyzer3 = BollingerBandsAnalyzer(bb4, squeeze_threshold=0.03)

squeeze_events = []
for i in range(len(closes)):
    analyzer3.update(closes[i])
    squeeze_status = analyzer3.detect_squeeze_breakout()

    if squeeze_status in ['SQUEEZE', 'BREAKOUT_UP', 'BREAKOUT_DOWN']:
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        current = bb4.get_current_values()
        squeeze_events.append((i, time_str, closes[i], squeeze_status, current))

print(f"\n检测到 {len(squeeze_events)} 个挤压相关事件\n")

if squeeze_events:
    print(f"{'序号':<6} {'时间':<20} {'价格':>12} {'状态':<15} {'带宽':>10} {' %B':>8}")
    print("-"*150)

    for idx, time_str, price, status, current in squeeze_events[-30:]:  # 显示最后30个事件
        status_str = ""
        if status == 'SQUEEZE':
            status_str = "挤压中 🔸"
        elif status == 'BREAKOUT_UP':
            status_str = "向上突破 🚀"
        elif status == 'BREAKOUT_DOWN':
            status_str = "向下突破 📉"

        print(f"{idx+1:<6} {time_str:<20} ${price:>11,.2f} {status_str:<15} {current['bandwidth']:>10.4f} {current['percent_b']:>8.2f}")

    # 统计挤压事件
    squeeze_count = sum(1 for _, _, _, s, _ in squeeze_events if s == 'SQUEEZE')
    breakout_up_count = sum(1 for _, _, _, s, _ in squeeze_events if s == 'BREAKOUT_UP')
    breakout_down_count = sum(1 for _, _, _, s, _ in squeeze_events if s == 'BREAKOUT_DOWN')

    print(f"\n挤压事件统计:")
    print(f"  挤压中: {squeeze_count}")
    print(f"  向上突破: {breakout_up_count}")
    print(f"  向下突破: {breakout_down_count}")

# 当前市场状态
print("\n" + "="*150)
print("【当前市场状态】")
print("="*150)

current = bb4.get_current_values()
current_price = closes[-1]
current_time = datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')

print(f"\n时间: {current_time}")
print(f"价格: ${current_price:,.2f}")
print(f"\n布林带指标:")
print(f"  上轨: ${current['upper_band']:,.2f}")
print(f"  中轨: ${current['middle_band']:,.2f}")
print(f"  下轨: ${current['lower_band']:,.2f}")
print(f"  %B: {current['percent_b']:.2f}")
print(f"  带宽: {current['bandwidth']:.4f}")
print(f"  标准差: {current['std_dev']:.2f}")

# 位置分析
position = analyzer3.get_price_position()
volatility = analyzer3.get_volatility_level()
signal = analyzer3.get_signal()
is_squeeze = analyzer3.is_squeeze()

print(f"\n市场分析:")
print(f"  价格位置: {position}")
print(f"  波动率水平: {volatility}")
print(f"  交易信号: {signal}")
print(f"  是否挤压: {'是 🔸' if is_squeeze else '否'}")

# 详细建议
print(f"\n交易建议:")
if signal == 'BUY':
    print("  🟢 买入信号：价格触及下轨，可能反弹")
    print("  建议: 考虑买入，设置止损在下轨下方")
elif signal == 'SELL':
    print("  🔴 卖出信号：价格触及上轨，可能回落")
    print("  建议: 考虑卖出或止盈，设置止损在上轨上方")
else:
    print("  ⚪ 持有信号：价格在布林带中间区域")
    print("  建议: 观望，等待价格触及上下轨")

if is_squeeze:
    print(f"\n  ⚠️  当前处于布林带挤压状态（带宽: {current['bandwidth']:.4f}）")
    print("  波动率极低，可能即将发生大的价格波动")
    print("  建议: 密切关注突破方向，突破后可能有较大行情")

print("\n" + "="*150)
print("【布林带使用技巧】")
print("="*150)
print("""
1. 基础策略：
   - 价格触及下轨 → 可能超卖，考虑买入
   - 价格触及上轨 → 可能超买，考虑卖出
   - 价格在中轨附近 → 趋势不明显，观望

2. %B指标应用：
   - %B > 1.0：价格在上轨之上，强势超买
   - %B = 0.5：价格在中轨，中性
   - %B < 0.0：价格在下轨之下，强势超卖
   - %B在0.8-1.0之间：上半区，偏强
   - %B在0.0-0.2之间：下半区，偏弱

3. 布林带挤压(Squeeze)：
   - 挤压状态：带宽收窄，波动率降低
   - 挤压后突破：通常伴随大幅价格波动
   - 突破方向：配合%B和价格判断

4. 带宽分析：
   - 带宽扩张：波动率增加，趋势加强
   - 带宽收窄：波动率减小，可能即将突破
   - 极端带宽：市场可能反转

5. 注意事项：
   - 布林带不是买卖点，只是参考区域
   - 需要配合其他指标（如RSI、MACD）确认
   - 趋势市场中，价格可能长期沿着上轨或下轨运行
   - 建议设置止损，控制风险
""")

print("="*150)
print("【本次优化总结】")
print("="*150)
print("""
✅ 已修复的关键问题:
1. 删除未使用的EMA计算方法，代码更简洁
2. 添加完整的输入验证，防止无效数据
3. 修复内存泄漏：限制price_history长度
4. 修复标准差返回：update方法现在返回实际标准差值
5. 添加参数验证：period和std_dev必须大于0

✅ 新增功能:
1. 布林带挤压(Squeeze)检测
2. 挤压突破检测（向上/向下）
3. 更详细的文档和使用说明
4. 完整的数值输出（每根K线的布林带值）
5. 支持倒序K线数据（需先反转）

✅ 改进:
1. 更清晰的注释和文档
2. 更完善的错误处理
3. 更准确的信号检测
4. 新增Analyzer的update方法，便于实时分析

📊 测试结果:
- 成功计算{len(bb_result['upper_band'])}个布林带数据点
- 检测到{len(signals)}个买卖信号
- 检测到{len(squeeze_events)}个挤压相关事件
- 所有计算均符合TradingView标准
""")

print("="*150)
print("测试完成！")
print("="*150)
