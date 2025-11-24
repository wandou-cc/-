"""
EMA均线指标完整测试套件
包含单元测试和集成测试
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import json
from datetime import datetime
from indicators.ema_cross import (
    EMAIndicator,
    EMAFourLineSystem,
    EMAFourLineAnalyzer,
    EMACrossSystem,  # 向后兼容性测试
    EMACrossAnalyzer
)


class TestEMAIndicator(unittest.TestCase):
    """EMA指标基础功能测试"""

    def test_initialization(self):
        """测试初始化"""
        ema = EMAIndicator(period=10)
        self.assertEqual(ema.period, 10)
        self.assertEqual(ema.alpha, 2.0 / 11)
        self.assertIsNone(ema.ema)
        self.assertEqual(len(ema.price_history), 0)

    def test_calculate_empty_list(self):
        """测试空列表输入"""
        ema = EMAIndicator(period=5)
        result = ema.calculate([])
        self.assertEqual(result, [])

    def test_calculate_single_value(self):
        """测试单个值计算"""
        ema = EMAIndicator(period=5)
        result = ema.calculate([100])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], 100)

    def test_calculate_basic(self):
        """测试基本EMA计算"""
        ema = EMAIndicator(period=5)
        prices = [100, 102, 101, 105, 107]
        result = ema.calculate(prices)

        self.assertEqual(len(result), len(prices))
        # EMA应该是递增的（对于上涨趋势）
        self.assertGreater(result[-1], result[0])
        # 第一个值应该等于价格
        self.assertEqual(result[0], prices[0])

    def test_calculate_invalid_data(self):
        """测试无效数据输入"""
        ema = EMAIndicator(period=5)

        # 测试字符串输入
        with self.assertRaises(ValueError) as context:
            ema.calculate(['invalid', 'data'])
        self.assertIn('价格数据必须是数值类型', str(context.exception))

        # 测试混合类型
        with self.assertRaises(ValueError):
            ema.calculate([100, 'invalid', 102])

    def test_update_basic(self):
        """测试实时更新功能"""
        ema = EMAIndicator(period=5)

        # 第一次更新
        result1 = ema.update(100)
        self.assertEqual(result1, 100)
        self.assertEqual(ema.ema, 100)

        # 第二次更新
        result2 = ema.update(105)
        self.assertGreater(result2, 100)
        self.assertLess(result2, 105)

    def test_update_invalid_data(self):
        """测试更新时的无效数据"""
        ema = EMAIndicator(period=5)

        with self.assertRaises(ValueError) as context:
            ema.update('invalid')
        self.assertIn('价格必须是数值类型', str(context.exception))

    def test_update_sequence(self):
        """测试连续更新与批量计算的一致性"""
        prices = [100, 102, 101, 105, 107, 106, 108, 110]

        # 批量计算
        ema1 = EMAIndicator(period=5)
        batch_result = ema1.calculate(prices)

        # 连续更新
        ema2 = EMAIndicator(period=5)
        update_results = []
        for price in prices:
            update_results.append(ema2.update(price))

        # 结果应该一致
        self.assertEqual(len(batch_result), len(update_results))
        for i in range(len(batch_result)):
            self.assertAlmostEqual(batch_result[i], update_results[i], places=10)

    def test_get_current_value(self):
        """测试获取当前值"""
        ema = EMAIndicator(period=5)

        # 初始状态
        self.assertIsNone(ema.get_current_value())

        # 更新后
        ema.update(100)
        self.assertEqual(ema.get_current_value(), 100)

        ema.update(105)
        current = ema.get_current_value()
        self.assertIsNotNone(current)
        self.assertGreater(current, 100)

    def test_reset(self):
        """测试重置功能"""
        ema = EMAIndicator(period=5)
        ema.update(100)
        ema.update(105)

        # 重置前
        self.assertIsNotNone(ema.ema)
        self.assertGreater(len(ema.price_history), 0)

        # 重置
        ema.reset()

        # 重置后
        self.assertIsNone(ema.ema)
        self.assertEqual(len(ema.price_history), 0)


class TestEMAFourLineSystem(unittest.TestCase):
    """EMA四线系统测试"""

    def test_initialization(self):
        """测试初始化"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        self.assertEqual(system.ultra_fast_period, 5)
        self.assertEqual(system.fast_period, 10)
        self.assertEqual(system.medium_period, 20)
        self.assertEqual(system.slow_period, 60)

    def test_default_parameters(self):
        """测试默认参数"""
        system = EMAFourLineSystem()
        params = system.get_parameters()
        self.assertEqual(params['ultra_fast_period'], 5)
        self.assertEqual(params['fast_period'], 10)
        self.assertEqual(params['medium_period'], 20)
        self.assertEqual(params['slow_period'], 60)

    def test_calculate_insufficient_data(self):
        """测试数据不足时的处理"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        prices = list(range(100, 150))  # 只有50个数据点

        with self.assertRaises(ValueError) as context:
            system.calculate(prices)
        self.assertIn('数据长度不足', str(context.exception))

    def test_calculate_basic(self):
        """测试基本计算"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        prices = list(range(100, 200))  # 100个数据点

        result = system.calculate(prices)

        # 检查返回的键
        self.assertIn('ema_ultra_fast', result)
        self.assertIn('ema_fast', result)
        self.assertIn('ema_medium', result)
        self.assertIn('ema_slow', result)

        # 检查长度
        self.assertEqual(len(result['ema_ultra_fast']), len(prices))
        self.assertEqual(len(result['ema_fast']), len(prices))
        self.assertEqual(len(result['ema_medium']), len(prices))
        self.assertEqual(len(result['ema_slow']), len(prices))

        # 上升趋势中，最后的值应该大于第一个值
        for key in result:
            self.assertGreater(result[key][-1], result[key][0])

    def test_calculate_ema_order(self):
        """测试EMA顺序（上升趋势应该是多头排列）"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        # 创建明显的上升趋势
        prices = [100 + i * 0.5 for i in range(100)]

        result = system.calculate(prices)

        # 在上升趋势的后期，应该接近多头排列
        # 超快线 > 快线 > 中线 > 慢线
        last_idx = -1
        self.assertGreater(
            result['ema_ultra_fast'][last_idx],
            result['ema_fast'][last_idx]
        )
        self.assertGreater(
            result['ema_fast'][last_idx],
            result['ema_medium'][last_idx]
        )

    def test_update_basic(self):
        """测试实时更新"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        prices = list(range(100, 170))

        # 初始化
        for price in prices:
            system.update(price)

        # 再次更新
        result = system.update(170)

        self.assertIn('ema_ultra_fast', result)
        self.assertIn('ema_fast', result)
        self.assertIn('ema_medium', result)
        self.assertIn('ema_slow', result)
        self.assertIn('price', result)
        self.assertEqual(result['price'], 170)

    def test_get_current_values(self):
        """测试获取当前值"""
        system = EMAFourLineSystem(5, 10, 20, 60)
        prices = list(range(100, 170))

        for price in prices:
            system.update(price)

        current = system.get_current_values()

        self.assertIsNotNone(current['ema_ultra_fast'])
        self.assertIsNotNone(current['ema_fast'])
        self.assertIsNotNone(current['ema_medium'])
        self.assertIsNotNone(current['ema_slow'])

    def test_reset(self):
        """测试重置功能"""
        system = EMAFourLineSystem(5, 10, 20, 60)

        # 添加数据
        for i in range(100, 170):
            system.update(i)

        # 重置
        system.reset()

        # 验证重置
        current = system.get_current_values()
        self.assertIsNone(current['ema_ultra_fast'])
        self.assertIsNone(current['ema_fast'])
        self.assertIsNone(current['ema_medium'])
        self.assertIsNone(current['ema_slow'])


class TestEMAFourLineAnalyzer(unittest.TestCase):
    """EMA四线分析器测试"""

    def setUp(self):
        """测试前准备"""
        self.system = EMAFourLineSystem(5, 10, 20, 60)
        self.analyzer = EMAFourLineAnalyzer(self.system)

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.analyzer.ema_system)
        self.assertEqual(len(self.analyzer.previous_values), 4)

    def test_get_signal_initial(self):
        """测试初始信号（无数据）"""
        signal = self.analyzer.get_signal()
        self.assertEqual(signal, 'HOLD')

    def test_get_trend_initial(self):
        """测试初始趋势"""
        trend = self.analyzer.get_trend()
        self.assertEqual(trend, 'SIDEWAYS')

    def test_get_trend_bull(self):
        """测试多头趋势识别"""
        # 创建上升趋势数据
        prices = [100 + i for i in range(100)]

        for price in prices:
            self.system.update(price)

        trend = self.analyzer.get_trend()
        # 应该是某种多头趋势
        self.assertIn('BULL', trend)

    def test_get_trend_bear(self):
        """测试空头趋势识别"""
        # 先上升
        for i in range(100, 170):
            self.system.update(i)

        # 然后下降
        for i in range(170, 100, -1):
            self.system.update(i)

        trend = self.analyzer.get_trend()
        # 应该是某种空头趋势或震荡
        self.assertIn(trend, ['BEAR', 'STRONG_BEAR', 'PERFECT_BEAR', 'SIDEWAYS'])

    def test_get_price_position(self):
        """测试价格位置分析"""
        # 初始化数据
        prices = list(range(100, 170))
        for price in prices:
            self.system.update(price)

        # 测试价格在均线上方
        position_info = self.analyzer.get_price_position(200)
        self.assertEqual(position_info['position'], 'ABOVE_ALL')
        self.assertEqual(position_info['above_count'], 4)

        # 测试价格在均线下方
        position_info = self.analyzer.get_price_position(100)
        self.assertEqual(position_info['position'], 'BELOW_ALL')
        self.assertEqual(position_info['above_count'], 0)

    def test_get_price_position_distances(self):
        """测试价格距离计算"""
        prices = list(range(100, 170))
        for price in prices:
            self.system.update(price)

        position_info = self.analyzer.get_price_position(170)
        distances = position_info['distances']

        # 检查所有距离键
        self.assertIn('ultra_fast', distances)
        self.assertIn('fast', distances)
        self.assertIn('medium', distances)
        self.assertIn('slow', distances)

        # 价格在均线上方，距离应该是正数
        for distance in distances.values():
            self.assertGreaterEqual(distance, 0)

    def test_get_support_resistance(self):
        """测试支撑阻力位"""
        prices = list(range(100, 170))
        for price in prices:
            self.system.update(price)

        sr_levels = self.analyzer.get_support_resistance()

        # 应该返回一些关键位
        self.assertGreater(len(sr_levels), 0)

        # 所有值应该是数字
        for level in sr_levels.values():
            self.assertIsNotNone(level)
            self.assertIsInstance(level, (int, float))

    def test_get_trend_strength(self):
        """测试趋势强度"""
        # 创建强上升趋势
        prices = [100 + i * 2 for i in range(100)]
        for price in prices:
            self.system.update(price)

        strength_info = self.analyzer.get_trend_strength()

        self.assertIn('strength', strength_info)
        self.assertIn('direction', strength_info)
        self.assertIn('score', strength_info)

        # 强度应该是预定义的值
        valid_strengths = ['VERY_STRONG', 'STRONG', 'MODERATE', 'WEAK', 'VERY_WEAK', 'UNKNOWN']
        self.assertIn(strength_info['strength'], valid_strengths)

        # 方向应该是预定义的值
        valid_directions = ['BULL', 'BEAR', 'NEUTRAL']
        self.assertIn(strength_info['direction'], valid_directions)

        # 分数应该在-100到100之间
        self.assertGreaterEqual(strength_info['score'], -100)
        self.assertLessEqual(strength_info['score'], 100)


class TestBackwardCompatibility(unittest.TestCase):
    """向后兼容性测试"""

    def test_old_class_names(self):
        """测试旧类名是否可用"""
        # 应该能够使用旧的类名
        system = EMACrossSystem(5, 10, 20, 60)
        analyzer = EMACrossAnalyzer(system)

        self.assertIsInstance(system, EMAFourLineSystem)
        self.assertIsInstance(analyzer, EMAFourLineAnalyzer)


class TestEMAIntegration(unittest.TestCase):
    """集成测试 - 使用真实数据"""

    @classmethod
    def setUpClass(cls):
        """加载真实K线数据"""
        json_path = os.path.join(os.path.dirname(__file__), 'K.json')

        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            klines = data['data']
            klines.reverse()

            cls.timestamps = []
            cls.closes = []

            for kline in klines:
                cls.timestamps.append(int(kline[0]))
                cls.closes.append(float(kline[4]))

            cls.has_real_data = True
        else:
            cls.has_real_data = False
            print("\n警告: 未找到 K.json 文件，跳过真实数据测试")

    def test_real_data_calculation(self):
        """测试真实数据计算"""
        if not self.has_real_data:
            self.skipTest("没有真实数据")

        system = EMAFourLineSystem(5, 10, 20, 60)

        if len(self.closes) >= 60:
            result = system.calculate(self.closes)

            # 验证结果
            self.assertEqual(len(result['ema_ultra_fast']), len(self.closes))

            # 所有EMA值应该是有效数字
            for key in result:
                for value in result[key]:
                    self.assertIsInstance(value, (int, float))
                    self.assertFalse(float('inf') == value)
                    self.assertFalse(float('-inf') == value)

    def test_real_data_signals(self):
        """测试真实数据信号检测"""
        if not self.has_real_data:
            self.skipTest("没有真实数据")

        system = EMAFourLineSystem(5, 10, 20, 60)
        analyzer = EMAFourLineAnalyzer(system)

        signals = []
        for i, price in enumerate(self.closes):
            system.update(price)
            signal = analyzer.get_signal()

            if signal != 'HOLD':
                signals.append((i, signal))

        # 应该能检测到一些信号
        print(f"\n检测到 {len(signals)} 个交易信号")

        # 验证信号类型
        valid_signals = ['STRONG_BUY', 'BUY', 'WEAK_BUY',
                        'STRONG_SELL', 'SELL', 'WEAK_SELL', 'HOLD']

        for _, signal in signals:
            self.assertIn(signal, valid_signals)


def run_ema_output(periods=[17, 30, 60, 120], show_all=False):
    """
    输出每一根K线的EMA值

    Args:
        periods: EMA周期列表，默认 [17, 30, 60, 120]
        show_all: 是否显示所有K线，默认False只显示最近30根
    """
    print("="*140)
    print(f"EMA值计算 (周期: {', '.join(map(str, periods))})")
    print("="*140)

    # 检查是否有真实数据
    json_path = os.path.join(os.path.dirname(__file__), 'K.json')

    if not os.path.exists(json_path):
        print("\n警告: 未找到 K.json 文件")
        print("使用模拟数据进行测试\n")

        # 创建模拟数据
        timestamps = [1000000 + i * 60000 for i in range(200)]
        closes = [100 + i * 0.5 + (i % 10) * 0.3 for i in range(200)]
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        klines = data['data']
        klines.reverse()

        timestamps = []
        closes = []

        for kline in klines:
            timestamps.append(int(kline[0]))
            closes.append(float(kline[4]))

    print(f"\n数据总数: {len(closes)} 根K线")
    print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 "
          f"{datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"价格范围: ${min(closes):,.2f} - ${max(closes):,.2f}")
    print()

    # 计算各个周期的EMA
    ema_results = {}
    for period in periods:
        ema_indicator = EMAIndicator(period)
        ema_results[period] = ema_indicator.calculate(closes)

    # 构建表头
    header = f"{'序号':<6} {'时间':<20} {'收盘价':>12}"
    for period in periods:
        header += f" {'EMA' + str(period):>12}"
    print(header)
    print("-"*140)

    # 确定显示范围
    if show_all:
        start_idx = 0
    else:
        start_idx = max(0, len(closes) - 30)

    # 输出每一根K线的EMA值
    for i in range(start_idx, len(closes)):
        timestamp = timestamps[i]
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

        row = f"{i+1:<6} {time_str:<20} ${closes[i]:>11,.2f}"
        for period in periods:
            row += f" ${ema_results[period][i]:>11,.2f}"
        print(row)

    print("="*140)
    print("当前最新值:")
    for period in periods:
        print(f"  EMA({period}):  ${ema_results[period][-1]:,.2f}")
    print("="*140)


def run_visual_test():
    """运行可视化测试（类似于原来的测试文件）"""
    print("="*120)
    print("EMA均线指标完整测试")
    print("="*120)

    # 检查是否有真实数据
    json_path = os.path.join(os.path.dirname(__file__), 'K.json')

    if not os.path.exists(json_path):
        print("\n警告: 未找到 K.json 文件")
        print("使用模拟数据进行测试\n")

        # 创建模拟数据
        timestamps = [1000000 + i * 60000 for i in range(200)]
        closes = [100 + i * 0.5 + (i % 10) * 0.3 for i in range(200)]
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        klines = data['data']
        klines.reverse()

        timestamps = []
        closes = []

        for kline in klines:
            timestamps.append(int(kline[0]))
            closes.append(float(kline[4]))

        print(f"\n数据总数: {len(closes)} 根K线")
        print(f"时间范围: {datetime.fromtimestamp(timestamps[0]/1000).strftime('%Y-%m-%d %H:%M:%S')} 到 "
              f"{datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"价格范围: ${min(closes):,.2f} - ${max(closes):,.2f}")

    print("\n" + "="*120)
    print("【配置: 短线交易系统 (5, 10, 20, 60)】")
    print("="*120)

    # 创建系统
    system = EMAFourLineSystem(5, 10, 20, 60)
    analyzer = EMAFourLineAnalyzer(system)

    if len(closes) >= 60:
        # 批量计算
        result = system.calculate(closes)

        # 显示最近20个数据
        print(f"\n最近20根K线的EMA值:")
        print(f"{'序号':<6} {'时间':<20} {'收盘价':>12} {'EMA5':>12} {'EMA10':>12} {'EMA20':>12} {'EMA60':>12}")
        print("-"*120)

        for i in range(max(0, len(closes) - 20), len(closes)):
            timestamp = timestamps[i]
            time_str = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

            close = closes[i]
            uf = result['ema_ultra_fast'][i]
            f = result['ema_fast'][i]
            m = result['ema_medium'][i]
            s = result['ema_slow'][i]

            print(f"{i+1:<6} {time_str:<20} ${close:>11,.2f} ${uf:>11,.2f} "
                  f"${f:>11,.2f} ${m:>11,.2f} ${s:>11,.2f}")

        # 信号检测
        print("\n" + "="*120)
        print("【交易信号检测】")
        print("="*120)

        system2 = EMAFourLineSystem(5, 10, 20, 60)
        analyzer2 = EMAFourLineAnalyzer(system2)

        signals = []
        for i, price in enumerate(closes):
            system2.update(price)
            signal = analyzer2.get_signal()

            if signal != 'HOLD':
                time_str = datetime.fromtimestamp(timestamps[i]/1000).strftime('%Y-%m-%d %H:%M:%S')
                signals.append((i, time_str, price, signal))

        print(f"\n检测到 {len(signals)} 个交易信号\n")
        print(f"{'序号':<6} {'时间':<20} {'价格':>12} {'信号':<15}")
        print("-"*120)

        for idx, time_str, price, signal in signals[-15:]:
            print(f"{idx+1:<6} {time_str:<20} ${price:>11,.2f} {signal:<15}")

        # 当前状态
        print("\n" + "="*120)
        print("【当前市场状态】")
        print("="*120)

        current = system2.get_current_values()
        current_price = closes[-1]
        current_time = datetime.fromtimestamp(timestamps[-1]/1000).strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n时间: {current_time}")
        print(f"当前价格: ${current_price:,.2f}")
        print(f"\n四条EMA值:")
        print(f"  EMA(5):  ${current['ema_ultra_fast']:,.2f}")
        print(f"  EMA(10): ${current['ema_fast']:,.2f}")
        print(f"  EMA(20): ${current['ema_medium']:,.2f}")
        print(f"  EMA(60): ${current['ema_slow']:,.2f}")

        # 趋势分析
        trend = analyzer2.get_trend()
        print(f"\n趋势分析: {trend}")

        # 价格位置
        position_info = analyzer2.get_price_position(current_price)
        print(f"\n价格位置: {position_info['position']}")
        print(f"价格在 {position_info['above_count']}/4 条均线之上")

        # 趋势强度
        strength_info = analyzer2.get_trend_strength()
        print(f"\n趋势强度:")
        print(f"  强度: {strength_info['strength']}")
        print(f"  方向: {strength_info['direction']}")
        print(f"  分数: {strength_info['score']}/100")

    print("\n" + "="*120)
    print("测试完成！")
    print("="*120)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == 'visual':
            # 运行可视化测试
            run_visual_test()
        elif sys.argv[1] == 'ema':
            # 输出EMA值
            # 默认周期 17, 30, 60, 120
            periods = [17, 30, 60, 120]
            show_all = False

            # 解析参数
            if len(sys.argv) > 2:
                # 检查是否有 --all 参数
                if '--all' in sys.argv:
                    show_all = True
                    sys.argv.remove('--all')

                # 解析周期参数
                if len(sys.argv) > 2:
                    try:
                        periods = [int(p) for p in sys.argv[2].split(',')]
                    except ValueError:
                        print("错误: 周期参数格式不正确，请使用逗号分隔的数字，如: 17,30,60,120")
                        sys.exit(1)

            run_ema_output(periods=periods, show_all=show_all)
        else:
            print("用法:")
            print("  python test_ema_cross.py           # 运行单元测试")
            print("  python test_ema_cross.py visual    # 运行可视化测试")
            print("  python test_ema_cross.py ema       # 输出EMA值 (默认周期: 17,30,60,120)")
            print("  python test_ema_cross.py ema 5,10,20,60  # 自定义周期")
            print("  python test_ema_cross.py ema --all       # 显示所有K线")
            print("  python test_ema_cross.py ema 17,30,60,120 --all  # 自定义周期并显示所有K线")
    else:
        # 否则运行单元测试
        unittest.main(verbosity=2)
