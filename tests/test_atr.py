"""
测试ATR指标 - 波动率分析和止损建议
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from datetime import datetime
from indicators.atr_indicator import ATRIndicator, ATRAnalyzer

# 读取K线数据
with open(os.path.join(os.path.dirname(__file__), 'K.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

klines = data

# 提取价格数据（保持倒序）
timestamps = []
opens = []
highs = []
lows = []
closes = []
volumes = []

for kline in klines:
    timestamps.append(int(kline[0]))
    opens.append(float(kline[1]))
    highs.append(float(kline[2]))
    lows.append(float(kline[3]))
    closes.append(float(kline[4]))
    volumes.append(float(kline[5]))

print("="*130)
print("ATR指标测试 - 波动率分析和止损建议")
print("="*130)
print(f"数据总数: {len(closes)} 根K线")
print(f"数据顺序: 倒序（从新到旧）")
print(f"最新时间: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"最早时间: {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"价格范围: ${min(lows):,.2f} - ${max(highs):,.2f}")
print("="*130)

# 创建ATR指标
print("\n【ATR参数配置】")
atr_period = 14
print(f"ATR周期: {atr_period}")
print("计算方法: Wilder平滑法（无状态计算）")
print("="*130)

# 使用无状态ATR指标进行批量计算
atr_indicator = ATRIndicator(period=atr_period)
analyzer = ATRAnalyzer(period=atr_period)

timestamps_asc = list(timestamps)
highs_asc = list(highs)
lows_asc = list(lows)
closes_asc = list(closes)

full_result = atr_indicator.calculate(highs_asc, lows_asc, closes_asc)
if full_result['atr'] is None:
    print("当前样本数据不足以完成完整ATR计算，将在后续统计中根据有效数据输出结果。")
else:
    print(f"完整样本最新ATR值: ${full_result['atr']:,.2f}")

# 逐步累积数据，模拟实时更新
highs_buffer = []
lows_buffer = []
closes_buffer = []
volatility_records = []

for i in range(len(closes_asc)):
    highs_buffer.append(highs_asc[i])
    lows_buffer.append(lows_asc[i])
    closes_buffer.append(closes_asc[i])

    analysis = analyzer.analyze(highs_buffer, lows_buffer, closes_buffer)

    if analysis['atr'] is None:
        continue

    if i >= atr_period + 20:  # 确保有足够的历史数据
        volatility_records.append({
            'index': i,
            'timestamp': timestamps_asc[i],
            'close': closes_asc[i],
            'atr': analysis['atr'],
            'volatility': analysis['volatility_level'],
            'stop_loss': analysis['stop_loss_distance']
        })

if not volatility_records:
    print("暂无足够的ATR数据用于分析，请检查K线样本后重试。")
    sys.exit(0)

# 显示最近20条波动率记录
print("\n【最近20条波动率分析】\n")
print(f"{'时间':<20} {'收盘价':>12} {'ATR':>12} {'波动率':<12} {'建议止损距离':>15}")
print("-"*130)

for record in volatility_records[-20:]:
    time_str = datetime.fromtimestamp(record['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')
    print(f"{time_str:<20} ${record['close']:>11,.2f} ${record['atr']:>11,.2f} {record['volatility']:<12} ${record['stop_loss']:>14,.2f}")

# 统计波动率分布
volatility_counts = {}
for record in volatility_records:
    vol = record['volatility']
    volatility_counts[vol] = volatility_counts.get(vol, 0) + 1

print("\n波动率分布统计:")
for level, count in sorted(volatility_counts.items()):
    pct = count / len(volatility_records) * 100
    print(f"  {level}: {count} 次 ({pct:.1f}%)")

# 测试4：突破有效性判断
print("\n" + "="*130)
print("【测试4：突破有效性判断】")
print("="*130)

# 计算价格变动
print("\n检测有效突破（价格变动超过1倍ATR）：\n")
print(f"{'时间':<20} {'收盘价':>12} {'价格变动':>12} {'ATR':>12} {'是否有效突破':<15}")
print("-"*130)

breakout_count = 0
for i in range(1, min(50, len(volatility_records))):
    prev_record = volatility_records[-(i+1)]
    curr_record = volatility_records[-i]

    price_move = curr_record['close'] - prev_record['close']
    curr_idx = curr_record['index']
    is_valid = analyzer.is_breakout_valid(
        highs_asc[:curr_idx + 1],
        lows_asc[:curr_idx + 1],
        closes_asc[:curr_idx + 1],
        price_move,
        threshold=1.0
    )

    if is_valid:
        breakout_count += 1
        time_str = datetime.fromtimestamp(curr_record['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')
        direction = "上涨" if price_move > 0 else "下跌"
        print(f"{time_str:<20} ${curr_record['close']:>11,.2f} ${price_move:>11,.2f} ${curr_record['atr']:>11,.2f} {direction}突破")

print(f"\n最近50根K线中有效突破次数: {breakout_count}")

# 测试5：ATR百分比（ATR占价格的百分比）
print("\n" + "="*130)
print("【测试5：ATR百分比分析】")
print("="*130)

atr_percentages = []
for record in volatility_records:
    atr_pct = (record['atr'] / record['close']) * 100
    atr_percentages.append(atr_pct)

print(f"\nATR百分比统计（ATR/收盘价 * 100）:")
print(f"  最大值: {max(atr_percentages):.4f}%")
print(f"  最小值: {min(atr_percentages):.4f}%")
print(f"  平均值: {sum(atr_percentages)/len(atr_percentages):.4f}%")
print(f"  最新值: {atr_percentages[-1]:.4f}%")

# 解读
avg_atr_pct = sum(atr_percentages)/len(atr_percentages)
if avg_atr_pct > 5:
    volatility_desc = "极高波动市场（加密货币、小盘股等）"
elif avg_atr_pct > 2:
    volatility_desc = "高波动市场"
elif avg_atr_pct > 1:
    volatility_desc = "中等波动市场"
else:
    volatility_desc = "低波动市场"

print(f"\n市场特征: {volatility_desc}")

# 测试6：止损策略建议
print("\n" + "="*130)
print("【测试6：止损策略建议】")
print("="*130)

current_atr = volatility_records[-1]['atr']
current_price = volatility_records[-1]['close']

print(f"\n当前价格: ${current_price:,.2f}")
print(f"当前ATR: ${current_atr:,.2f}")
print(f"ATR百分比: {(current_atr/current_price)*100:.4f}%")

print("\n建议止损距离（基于ATR倍数）:")
multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
for mult in multipliers:
    stop_dist = current_atr * mult
    stop_pct = (stop_dist / current_price) * 100

    if mult == 1.0:
        risk_level = "激进（高风险/高收益）"
    elif mult == 1.5:
        risk_level = "中等偏激进"
    elif mult == 2.0:
        risk_level = "标准（推荐）"
    elif mult == 2.5:
        risk_level = "保守"
    else:
        risk_level = "非常保守"

    print(f"  {mult:.1f}x ATR: ${stop_dist:,.2f} ({stop_pct:.2f}%) - {risk_level}")

# 计算多头和空头止损价位
print(f"\n多头止损价位（基于2x ATR）:")
long_stop = current_price - (current_atr * 2)
print(f"  入场价: ${current_price:,.2f}")
print(f"  止损价: ${long_stop:,.2f}")
print(f"  风险: ${current_atr * 2:,.2f} ({(current_atr * 2 / current_price) * 100:.2f}%)")

print(f"\n空头止损价位（基于2x ATR）:")
short_stop = current_price + (current_atr * 2)
print(f"  入场价: ${current_price:,.2f}")
print(f"  止损价: ${short_stop:,.2f}")
print(f"  风险: ${current_atr * 2:,.2f} ({(current_atr * 2 / current_price) * 100:.2f}%)")

# ATR统计摘要
print("\n" + "="*130)
print("【ATR统计摘要】")
print("="*130)

all_atr_values = [r['atr'] for r in volatility_records]
print(f"\nATR统计:")
print(f"  最大值: ${max(all_atr_values):,.2f}")
print(f"  最小值: ${min(all_atr_values):,.2f}")
print(f"  平均值: ${sum(all_atr_values)/len(all_atr_values):,.2f}")
print(f"  最新值: ${all_atr_values[-1]:,.2f}")

# 当前市场状态
print("\n" + "="*130)
print("【当前市场状态】")
print("="*130)

current_record = volatility_records[-1]
current_time = datetime.fromtimestamp(current_record['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')

print(f"\n时间: {current_time}")
print(f"价格: ${current_record['close']:,.2f}")
print(f"ATR: ${current_record['atr']:,.2f}")
print(f"波动率水平: {current_record['volatility']}")
print(f"建议止损距离(2x ATR): ${current_record['stop_loss']:,.2f}")

# ATR使用技巧
print("\n" + "="*130)
print("【ATR使用技巧】")
print("="*130)
print("""
1. 止损设置：
   - 保守策略：使用2-3倍ATR作为止损距离
   - 激进策略：使用1-1.5倍ATR作为止损距离
   - 避免被正常波动触发止损

2. 仓位管理：
   - 高ATR时减小仓位（波动大，风险高）
   - 低ATR时可适当增加仓位
   - 公式：仓位 = 可接受风险金额 / (ATR * 倍数)

3. 突破确认：
   - 价格移动超过1倍ATR = 有效突破
   - 价格移动超过2倍ATR = 强势突破
   - 用于过滤假突破

4. 趋势强度：
   - ATR上升 = 趋势加强或波动增加
   - ATR下降 = 趋势减弱或市场整理
   - 结合价格方向判断趋势质量

5. 入场时机：
   - ATR收缩后扩张 = 新趋势可能开始
   - ATR持续低位 = 可能即将突破
   - 适合在低ATR时建仓，等待波动扩大

6. 与其他指标结合：
   - ATR + 布林带：动态止损
   - ATR + RSI：超买超卖确认
   - ATR + MACD：趋势强度确认
""")

print("="*130)
print("测试完成！")
print("="*130)
