"""
RSI指标综合测试
测试每根K线的RSI值、超买超卖状态和背离信号
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.rsi_indicator import RSIIndicator, RSIAnalyzer


def load_kline_data(file_path: str):
    """
    从JSON文件加载K线数据

    Args:
        file_path: K线数据文件路径

    Returns:
        K线数据列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data['data']


def format_timestamp(timestamp_ms: str) -> str:
    """
    格式化时间戳

    Args:
        timestamp_ms: 毫秒时间戳字符串

    Returns:
        格式化的日期时间字符串
    """
    timestamp_sec = int(timestamp_ms) / 1000
    dt = datetime.fromtimestamp(timestamp_sec)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def test_rsi_with_kline_data():
    """
    使用K线数据测试RSI指标
    """
    print("=" * 100)
    print("RSI 指标综合分析测试")
    print("=" * 100)

    # 加载K线数据
    kline_file = os.path.join(os.path.dirname(__file__), 'K.json')
    kline_data = load_kline_data(kline_file)

    # K线数据格式: [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量, ...]
    # 数据是倒序的（最新的在前），需要反转
    # 提取收盘价
    prices = [float(k[4]) for k in reversed(kline_data)]
    timestamps = [k[0] for k in reversed(kline_data)]

    print(f"\n总共加载了 {len(prices)} 根K线数据")
    print(f"时间范围: {format_timestamp(timestamps[0])} 至 {format_timestamp(timestamps[-1])}")
    print(f"价格范围: {min(prices):.2f} - {max(prices):.2f}")

    # 初始化RSI指标（14周期，使用EMA方法）
    rsi_period = 14
    overbought_threshold = 70  # 超买阈值
    oversold_threshold = 30    # 超卖阈值

    print(f"\nRSI 参数配置:")
    print(f"  - 周期: {rsi_period}")
    print(f"  - 计算方法: EMA (TradingView标准)")
    print(f"  - 超买阈值: {overbought_threshold}")
    print(f"  - 超卖阈值: {oversold_threshold}")

    # 创建RSI指标和分析器
    rsi = RSIIndicator(period=rsi_period, use_ema=True)
    analyzer = RSIAnalyzer(rsi, overbought=overbought_threshold, oversold=oversold_threshold)

    # 批量计算RSI
    print("\n正在计算RSI...")
    result = rsi.calculate(prices)
    rsi_values = result['rsi']

    print(f"计算完成！共生成 {len(rsi_values)} 个RSI值")

    # 详细输出每根K线的分析结果
    print("\n" + "=" * 100)
    print("每根K线的详细分析 (倒序显示，最新的在前)")
    print("=" * 100)
    print(f"{'序号':<6} {'时间':<20} {'价格':<12} {'RSI':<8} {'状态':<12} {'超买':<6} {'超卖':<6} {'信号':<8}")
    print("-" * 90)

    # 用于统计
    buy_signals = []
    sell_signals = []
    overbought_count = 0
    oversold_count = 0

    # 从最新的K线开始显示（倒序）

    for idx in range(len(rsi_values) - 1, -1, -1):
        # 计算在原始数据中的索引（现在已经是正序了）
        price_index = idx + rsi_period

        timestamp = format_timestamp(timestamps[price_index])
        price = prices[price_index]
        rsi_value = rsi_values[idx]

        # 判断超买超卖
        is_overbought = rsi_value > overbought_threshold
        is_oversold = rsi_value < oversold_threshold

        if is_overbought:
            overbought_count += 1
        if is_oversold:
            oversold_count += 1

        # 判断动量状态
        if is_overbought:
            momentum = "超买"
        elif is_oversold:
            momentum = "超卖"
        elif rsi_value > 50:
            momentum = "看涨"
        elif rsi_value < 50:
            momentum = "看跌"
        else:
            momentum = "中性"

        # 检测交易信号（需要比较前一个RSI值）
        signal = "-"
        if idx > 0:
            prev_rsi = rsi_values[idx - 1]
            # 从超卖区反弹
            if prev_rsi <= oversold_threshold and rsi_value > oversold_threshold:
                signal = "买入"
                buy_signals.append((timestamp, price, rsi_value))
            # 从超买区回落
            elif prev_rsi >= overbought_threshold and rsi_value < overbought_threshold:
                signal = "卖出"
                sell_signals.append((timestamp, price, rsi_value))

        # 输出当前K线的分析结果
        display_index = len(rsi_values) - idx
        print(f"{display_index:<6} {timestamp:<20} {price:<12.2f} {rsi_value:<8.2f} {momentum:<12} "
              f"{'是' if is_overbought else '否':<6} {'是' if is_oversold else '否':<6} "
              f"{signal:<8}")

    # 输出统计摘要
    print("\n" + "=" * 100)
    print("统计摘要")
    print("=" * 100)

    print(f"\n超买超卖统计:")
    print(f"  - 超买次数: {overbought_count} ({overbought_count/len(rsi_values)*100:.1f}%)")
    print(f"  - 超卖次数: {oversold_count} ({oversold_count/len(rsi_values)*100:.1f}%)")

    print(f"\n交易信号统计:")
    print(f"  - 买入信号: {len(buy_signals)} 次")
    if buy_signals:
        print("    最近3次买入信号:")
        for ts, price, rsi in buy_signals[:3]:
            print(f"      {ts} - 价格: {price:.2f}, RSI: {rsi:.2f}")

    print(f"  - 卖出信号: {len(sell_signals)} 次")
    if sell_signals:
        print("    最近3次卖出信号:")
        for ts, price, rsi in sell_signals[:3]:
            print(f"      {ts} - 价格: {price:.2f}, RSI: {rsi:.2f}")

    # RSI统计
    print(f"\nRSI 统计:")
    print(f"  - 平均值: {sum(rsi_values)/len(rsi_values):.2f}")
    print(f"  - 最大值: {max(rsi_values):.2f}")
    print(f"  - 最小值: {min(rsi_values):.2f}")
    print(f"  - 当前值: {rsi_values[-1]:.2f}")

    print("\n" + "=" * 100)
    print("测试完成！")
    print("=" * 100)


def test_realtime_update():
    """
    测试实时更新功能
    """
    print("\n\n" + "=" * 100)
    print("实时更新测试")
    print("=" * 100)

    # 加载K线数据
    kline_file = os.path.join(os.path.dirname(__file__), 'K.json')
    kline_data = load_kline_data(kline_file)

    # 数据是倒序的，需要反转
    prices = [float(k[4]) for k in reversed(kline_data)]
    timestamps = [k[0] for k in reversed(kline_data)]

    # 创建RSI指标和分析器
    rsi = RSIIndicator(period=14, use_ema=True)
    analyzer = RSIAnalyzer(rsi, overbought=70, oversold=30)

    # 先用前面的数据初始化RSI（累积前280根）
    for i in range(len(prices) - 20):
        rsi.update(prices[i])

    # 模拟实时更新最后20根K线
    print("\n模拟实时更新最后20根K线:")
    print(f"{'序号':<6} {'时间':<20} {'价格':<12} {'RSI':<8} {'动量':<12} {'信号':<8}")
    print("-" * 80)

    start_index = len(prices) - 20

    for i in range(start_index, len(prices)):
        price = prices[i]
        result = rsi.update(price)

        if result['rsi'] is not None:
            analysis = analyzer.get_comprehensive_analysis()
            timestamp = format_timestamp(timestamps[i])

            print(f"{i-start_index+1:<6} {timestamp:<20} {price:<12.2f} "
                  f"{result['rsi']:<8.2f} {analysis['momentum_level']:<12} "
                  f"{analysis['signal']:<8}")

    print("\n" + "=" * 100)


if __name__ == '__main__':
    # 运行综合测试
    test_rsi_with_kline_data()

    # 运行实时更新测试
    test_realtime_update()
