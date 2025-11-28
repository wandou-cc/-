"""
调试ATR计算差异
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from indicators.atr_indicator import ATRIndicator

# 读取K线数据
with open(os.path.join(os.path.dirname(__file__), 'K.json'), 'r', encoding='utf-8') as f:
    klines = json.load(f)

# 提取价格数据
highs = [float(k[2]) for k in klines]
lows = [float(k[3]) for k in klines]
closes = [float(k[4]) for k in klines]

print(f"数据总数: {len(closes)}")
print(f"第一条时间戳: {klines[0][0]} (应该是最旧的)")
print(f"最后一条时间戳: {klines[-1][0]} (应该是最新的)")
print()

# 方法1: 使用 calculate() 批量计算
atr1 = ATRIndicator(period=14)
result1 = atr1.calculate(highs, lows, closes, reverse=False)
print(f"calculate() 方法结果数量: {len(result1['atr'])}")
print(f"calculate() 最后5个ATR: {result1['atr'][-5:]}")
print()

# 方法2: 使用 update() 逐个更新
atr2 = ATRIndicator(period=14)
atr_values_update = []
for i in range(len(closes)):
    result = atr2.update(highs[i], lows[i], closes[i])
    if result['atr'] is not None:
        atr_values_update.append(result['atr'])

print(f"update() 方法结果数量: {len(atr_values_update)}")
print(f"update() 最后5个ATR: {atr_values_update[-5:]}")
print()

# 对比差异
if len(result1['atr']) == len(atr_values_update):
    print("结果数量相同")
    # 检查最后几个值的差异
    for i in range(-5, 0):
        diff = abs(result1['atr'][i] - atr_values_update[i])
        print(f"  索引 {i}: calculate={result1['atr'][i]:.6f}, update={atr_values_update[i]:.6f}, 差异={diff:.6f}")
else:
    print(f"结果数量不同: calculate={len(result1['atr'])}, update={len(atr_values_update)}")

    # 对齐后比较
    min_len = min(len(result1['atr']), len(atr_values_update))
    print(f"\n对齐后比较最后5个值:")
    for i in range(-5, 0):
        calc_val = result1['atr'][i] if abs(i) <= len(result1['atr']) else None
        upd_val = atr_values_update[i] if abs(i) <= len(atr_values_update) else None
        if calc_val and upd_val:
            diff = abs(calc_val - upd_val)
            print(f"  索引 {i}: calculate={calc_val:.6f}, update={upd_val:.6f}, 差异={diff:.6f}")
