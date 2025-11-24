"""
测试MACD指标 - 金叉、死叉、背离分析
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
klines.reverse()  # 数据是倒序的，需要反转

# 提取价格数据
timestamps = []
closes = []
highs = []
lows = []

for kline in klines:
    timestamps.append(int(kline[0]))
    closes.append(float(kline[4]))
    highs.append(float(kline[2]))
    lows.append(float(kline[3]))

print("="*130)
print("MACD指标测试 - 金叉、死叉、背离分析")
print("="*130)
print(f"数据总数: {len(closes)} 根K线")
print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"价格范围: ${min(lows):,.2f} - ${max(highs):,.2f}")
print("="*130)

# 创建MACD指标
print("\n【MACD参数配置】")
print("快速EMA: 12")
print("慢速EMA: 26")
print("信号线: 9")
print("="*130)

macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
macd_result = macd.calculate(closes)

# 显示最后100根K线的MACD值(去掉最近30根)
print("\n【最后100根K线的MACD值 (去掉最近30根)】\n")
print(f"{'序号':<6} {'时间':<20} {'收盘价':>12} {'MACD线':>12} {'信号线':>12} {'柱状图':>12} {'状态':<20}")
print("-"*130)

# 计算K线范围: 从倒数第130根到倒数第31根 (共100根)
kline_total = len(closes)
kline_start = max(0, kline_total - 130)  # K线倒数第130根
kline_end = kline_total           # K线倒数第31根(不包含最近30根)

# MACD有warm-up期,需要找到MACD结果对应的K线起始索引
macd_offset = kline_total - len(macd_result['macd_line'])

for i in range(kline_start, kline_end):
    timestamp = timestamps[i]
    time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
    close = closes[i]

    # 转换成MACD索引
    macd_idx = i - macd_offset

    # 检查MACD索引是否有效
    if macd_idx < 0 or macd_idx >= len(macd_result['macd_line']):
        print(f"{i+1:<6} {time_str:<20} ${close:>11,.2f} {'N/A':>12} {'N/A':>12} {'N/A':>12} MACD未计算")
        continue

    macd_line = macd_result['macd_line'][macd_idx]
    signal_line = macd_result['signal_line'][macd_idx]
    histogram = macd_result['histogram'][macd_idx]

    # 判断状态
    status = ""
    if macd_idx > 0:
        prev_hist = macd_result['histogram'][macd_idx-1]
        prev_macd = macd_result['macd_line'][macd_idx-1]
        prev_signal = macd_result['signal_line'][macd_idx-1]
        
        # 金叉：MACD线向上穿越信号线
        if prev_macd < prev_signal and macd_line > signal_line:
            status = "金叉 🔺"
        # 死叉：MACD线向下穿越信号线
        elif prev_macd > prev_signal and macd_line < signal_line:
            status = "死叉 🔻"
        # 柱状图由负转正
        elif prev_hist < 0 and histogram > 0:
            status = "柱状图转正 +"
        # 柱状图由正转负
        elif prev_hist > 0 and histogram < 0:
            status = "柱状图转负 -"
    
    # MACD位置
    if macd_line > 0 and signal_line > 0:
        status += " [零轴上方]" if status else "零轴上方"
    elif macd_line < 0 and signal_line < 0:
        status += " [零轴下方]" if status else "零轴下方"
    
    print(f"{i+1:<6} {time_str:<20} ${close:>11,.2f} {macd_line:>12.2f} {signal_line:>12.2f} {histogram:>12.2f} {status:<20}")

# 测试新增的 get_filtered_signal 方法（多维度过滤）
print("\n" + "="*130)
print("【新增功能测试 - 多维度过滤信号】")
print("="*130)

print("\n使用 get_filtered_signal() 方法进行多维度过滤：")
print("  - 角度检查: 使用线性回归计算斜率差")
print("  - 动能检查: 柱状图趋势检查（允许小幅波动）")
print("  - 阈值检查: 柱状图绝对值阈值")
print("  - 0轴距离检查: 过滤太靠近0轴的金叉死叉")

macd3 = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
analyzer3 = MACDAnalyzer(
    macd3,
    # 角度过滤：MACD线和信号线交叉时的角度阈值系数
    # 值越大，要求交叉角度越大才算有效信号（范围：0.3-0.8）
    # 计算方式：斜率差 > 标准差 * angle_multiplier
    angle_multiplier=0.5,

    # 柱状图阈值过滤：要求柱状图绝对值必须大于此值
    # 作用：过滤掉柱状图太小的信号，避免横盘震荡噪音
    # 计算方式：abs(histogram) > min_hist_threshold
    min_hist_threshold=10,

    # 回溯周期：计算标准差时使用的历史数据长度
    # 用于角度检查的动态阈值计算（范围：30-100）
    lookback_period=50,

    # 0轴距离过滤：MACD线和信号线距离0轴的最小距离
    # 作用：过滤太靠近0轴的金叉死叉，只关注趋势明显的信号
    # 计算方式：min(abs(macd), abs(signal)) >= min_zero_distance
    min_zero_distance=300.0
)

filtered_signals = []
for i in range(len(closes)):
    macd3.update(closes[i])
    signal_result = analyzer3.get_filtered_signal()

    if signal_result['signal'] != 'none':
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        filtered_signals.append((i, time_str, closes[i], signal_result))

print(f"\n检测到 {len(filtered_signals)} 个信号（包括强信号和弱信号）\n")

if filtered_signals:
    print(f"{'序号':<6} {'时间':<20} {'价格':>12} {'信号类型':<20} {'角度':<6} {'动能':<6} {'阈值':<6} {'0轴':<6} {'角度值':>10} {'0轴距':>10}")
    print("-"*130)
    for idx, time_str, price, result in filtered_signals[:20]:  # 显示前20个
        signal_type = result['signal']
        conditions = result['conditions']
        angle = '✓' if conditions['angle_check'] else '✗'
        momentum = '✓' if conditions['momentum_check'] else '✗'
        threshold = '✓' if conditions['threshold_check'] else '✗'
        zero_dist = '✓' if conditions['zero_distance_check'] else '✗'
        angle_value = result['metrics']['angle']
        zero_distance = result['metrics']['zero_distance']

        print(f"{idx+1:<6} {time_str:<20} ${price:>11,.2f} {signal_type:<20} {angle:<6} {momentum:<6} {threshold:<6} {zero_dist:<6} {angle_value:>10.4f} {zero_distance:>10.2f}")

    # 统计各类信号
    strong_golden = sum(1 for _, _, _, r in filtered_signals if r['signal'] == 'strong_golden')
    weak_golden = sum(1 for _, _, _, r in filtered_signals if r['signal'] == 'weak_golden')
    strong_dead = sum(1 for _, _, _, r in filtered_signals if r['signal'] == 'strong_dead')
    weak_dead = sum(1 for _, _, _, r in filtered_signals if r['signal'] == 'weak_dead')

    print(f"\n信号分类统计:")
    print(f"  强金叉 (4个条件全满足): {strong_golden}")
    print(f"  弱金叉 (2-3个条件满足): {weak_golden}")
    print(f"  强死叉 (4个条件全满足): {strong_dead}")
    print(f"  弱死叉 (2-3个条件满足): {weak_dead}")

    # 显示过滤参数
    params = analyzer3.get_filter_parameters()
    print(f"\n过滤参数配置:")
    print(f"  角度倍数: {params['angle_multiplier']}")
    print(f"  最小柱状图阈值: {params['min_hist_threshold']}")
    print(f"  回溯周期: {params['lookback_period']}")
    print(f"  距离0轴最小距离: {params['min_zero_distance']}")

# MACD统计分析
print("\n" + "="*130)
print("【MACD统计分析】")
print("="*130)

macd_values = macd_result['macd_line']
signal_values = macd_result['signal_line']
histogram_values = macd_result['histogram']

print(f"\nMACD线统计:")
print(f"  最大值: {max(macd_values):,.2f}")
print(f"  最小值: {min(macd_values):,.2f}")
print(f"  平均值: {sum(macd_values)/len(macd_values):,.2f}")
print(f"  最新值: {macd_values[-1]:,.2f}")

print(f"\n信号线统计:")
print(f"  最大值: {max(signal_values):,.2f}")
print(f"  最小值: {min(signal_values):,.2f}")
print(f"  平均值: {sum(signal_values)/len(signal_values):,.2f}")
print(f"  最新值: {signal_values[-1]:,.2f}")

print(f"\n柱状图统计:")
print(f"  最大值: {max(histogram_values):,.2f}")
print(f"  最小值: {min(histogram_values):,.2f}")
print(f"  平均值: {sum(histogram_values)/len(histogram_values):,.2f}")
print(f"  最新值: {histogram_values[-1]:,.2f}")

# 当前市场状态
print("\n" + "="*130)
print("【当前市场状态】")
print("="*130)

current = macd3.get_current_values()
current_price = closes[-1]
current_time = datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')

print(f"\n时间: {current_time}")
print(f"价格: ${current_price:,.2f}")
print(f"\nMACD指标:")
print(f"  MACD线: {current['macd_line']:,.2f}")
print(f"  信号线: {current['signal_line']:,.2f}")
print(f"  柱状图: {current['histogram']:,.2f}")

# 趋势分析
trend = analyzer3.get_trend_strength()
print(f"\n趋势分析: {trend}")

if current['macd_line'] > current['signal_line']:
    if current['macd_line'] > 0:
        print("  💹 强势多头：MACD线在零轴上方且在信号线上方")
        print("  建议: 强势上涨，持有多单")
    else:
        print("  📈 弱势多头：MACD线在零轴下方但在信号线上方")
        print("  建议: 可能筑底，观察是否向上突破零轴")
else:
    if current['macd_line'] < 0:
        print("  📉 强势空头：MACD线在零轴下方且在信号线下方")
        print("  建议: 强势下跌，保持观望")
    else:
        print("  📊 弱势空头：MACD线在零轴上方但在信号线下方")
        print("  建议: 可能见顶，注意风险")

# 柱状图分析
if abs(current['histogram']) > 100:
    print(f"\n  ⚡ 柱状图较大({current['histogram']:.2f})，趋势较强")
elif abs(current['histogram']) < 20:
    print(f"\n  ⚠️  柱状图较小({current['histogram']:.2f})，趋势较弱或即将转折")

print("\n" + "="*130)
print("【MACD使用技巧】")
print("="*130)
print("""
1. 金叉死叉信号：
   - 金叉（买入）：MACD线向上穿越信号线
   - 死叉（卖出）：MACD线向下穿越信号线
   - 零轴上方的金叉更可靠（强势区域）

2. 零轴突破：
   - MACD线突破零轴向上：确认上涨趋势
   - MACD线跌破零轴向下：确认下跌趋势

3. 背离信号：
   - 顶背离：价格新高，MACD不创新高 → 看跌
   - 底背离：价格新低，MACD不创新低 → 看涨

4. 柱状图分析：
   - 柱状图由负转正：买入信号
   - 柱状图由正转负：卖出信号
   - 柱状图长度：反映趋势强度

5. 多周期验证：
   - 结合不同时间周期的MACD，提高准确性
   - 日线金叉+小时线金叉 = 更强信号
""")

print("="*130)
print("【本次优化总结】")
print("="*130)
print("""
✅ 已修复的关键问题:
1. EMA 初始化: 改用 SMA 作为初始值（符合 TradingView 标准）
2. 输入验证: 添加价格有效性检查，防止无效数据
3. 趋势强度判断: 使用历史百分位数，修复逻辑错误
4. 内存泄漏: 限制历史数据长度（slow_period + 100）

✅ 算法改进:
1. 交叉强度计算: 使用归一化处理，考虑市场波动性
2. 角度检查: 使用线性回归计算斜率（5个数据点），更稳健
3. 动能检查: 允许小幅波动（5个点中3次递增/递减即可）
4. 代码重构: 提取公共方法 _detect_cross()，减少重复代码

✅ 新增功能:
1. get_filtered_signal(): 多维度过滤，返回详细信号信息
2. 支持强/弱信号分类，提供更精细的交易决策
3. 所有方法向后兼容，不影响现有代码

⚙️ 建议的参数配置:
- angle_multiplier: 0.3-0.8（角度敏感度）
- min_hist_threshold: 0.0001-0.001（柱状图最小阈值）
- lookback_period: 30-100（标准差回溯周期）
""")

print("="*130)
print("测试完成！")
print("="*130)

