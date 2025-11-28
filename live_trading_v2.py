# -*- coding: utf-8 -*-
"""
实时交易系统 V2 - 状态机驱动策略

基于 WebSocket 的实时K线数据接入和信号生成系统。
整合新的策略框架：
- 市场状态自动识别（ADX驱动）
- 三种子策略自动切换
- 多周期确认
- 实时信号生成与预测

使用方法：
    python live_trading_v2.py --symbol BTCUSDT --interval 5m
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import argparse

try:
    import websockets
    from aiohttp_socks import ProxyConnector
    import aiohttp
except ImportError:
    print("请安装依赖: pip install websockets aiohttp aiohttp-socks")
    exit(1)

from config import (
    BINANCE_API_URL, BINANCE_WS_URL,
    USE_PROXY, PROXY_URL,
    WS_PING_INTERVAL, WS_PING_TIMEOUT, MAX_RETRIES
)
from strategy_config import STRATEGY_CONFIG, get_multi_timeframe_config
from indicators import StreamingKlineBuffer
from strategy import (
    SignalGenerator, TradingSignal, SignalGrade,
    MarketState, SignalDirection
)


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MultiTimeframeBuffer:
    """多周期K线缓冲区"""
    buffers: Dict[str, StreamingKlineBuffer]

    @classmethod
    def create(cls, intervals: List[str], buffer_size: int = 200):
        """创建多周期缓冲区"""
        buffers = {
            interval: StreamingKlineBuffer(max_closed=buffer_size)
            for interval in intervals
        }
        return cls(buffers=buffers)

    def get_buffer(self, interval: str) -> Optional[StreamingKlineBuffer]:
        """获取指定周期的缓冲区"""
        return self.buffers.get(interval)

    def get_ohlcv_data(self, interval: str) -> Optional[Dict[str, List[float]]]:
        """获取指定周期的OHLCV数据"""
        buffer = self.buffers.get(interval)
        if buffer is None:
            return None

        # 使用 get_price_arrays 方法获取数据
        price_data = buffer.get_price_arrays(include_current=True)

        if len(price_data["closes"]) < 30:
            return None

        return {
            "highs": price_data["highs"],
            "lows": price_data["lows"],
            "closes": price_data["closes"],
            "volumes": price_data["volumes"]
        }


class LiveTradingSystemV2:
    """
    实时交易系统 V2

    特点：
    - 多周期数据同步
    - 市场状态自动识别
    - 策略自动切换
    - 信号实时生成
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        primary_interval: str = "5m",
        confirmation_intervals: List[str] = None
    ):
        """
        初始化实时交易系统

        Args:
            symbol: 交易对
            primary_interval: 主周期
            confirmation_intervals: 确认周期列表
        """
        self.symbol = symbol.upper()
        self.primary_interval = primary_interval

        # 多周期配置
        mtf_config = get_multi_timeframe_config()
        self.confirmation_intervals = confirmation_intervals or mtf_config.get(
            "confirmation_timeframes", ["15m", "1h"]
        )
        self.all_intervals = [primary_interval] + self.confirmation_intervals

        # 创建多周期缓冲区
        self.mtf_buffer = MultiTimeframeBuffer.create(self.all_intervals, buffer_size=200)

        # 创建信号生成器
        self.signal_generator = SignalGenerator(symbol=self.symbol)

        # 状态跟踪
        self.is_running = False
        self.last_signal: Optional[TradingSignal] = None
        self.signal_history: List[TradingSignal] = []

        # WebSocket连接
        self.ws_connections: Dict[str, Any] = {}

        logger.info(f"初始化交易系统: {symbol} | 主周期: {primary_interval} | 确认周期: {self.confirmation_intervals}")

    async def fetch_historical_klines(self, interval: str, limit: int = 200) -> List[List]:
        """获取历史K线数据"""
        url = f"{BINANCE_API_URL}/fapi/v1/klines"
        params = {
            "symbol": self.symbol,
            "interval": interval,
            "limit": limit
        }

        connector = None
        if USE_PROXY and PROXY_URL:
            connector = ProxyConnector.from_url(PROXY_URL)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"获取{interval}历史数据失败: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"获取{interval}历史数据异常: {e}")
            return []

    async def initialize_buffers(self):
        """初始化所有周期的缓冲区"""
        logger.info("正在获取历史K线数据...")

        tasks = [
            self.fetch_historical_klines(interval)
            for interval in self.all_intervals
        ]

        results = await asyncio.gather(*tasks)

        for interval, klines in zip(self.all_intervals, results):
            buffer = self.mtf_buffer.get_buffer(interval)
            if buffer and klines:
                for kline in klines:
                    # 使用 update_from_ws 方法，传入 k 字段格式的数据
                    buffer.update_from_ws({
                        't': kline[0],
                        'o': kline[1],
                        'h': kline[2],
                        'l': kline[3],
                        'c': kline[4],
                        'v': kline[5],
                        'x': True  # 历史K线都是已完成的
                    })
                # 获取K线数量
                candle_count = len(buffer.get_candles(include_current=True))
                logger.info(f"  {interval}: 加载了 {candle_count} 根K线")

    async def connect_websocket(self, interval: str):
        """连接单个周期的WebSocket"""
        stream_name = f"{self.symbol.lower()}@kline_{interval}"
        ws_url = f"{BINANCE_WS_URL}/ws/{stream_name}"

        retry_count = 0

        while self.is_running and retry_count < MAX_RETRIES:
            try:
                ws_kwargs = {
                    'ping_interval': WS_PING_INTERVAL,
                    'ping_timeout': WS_PING_TIMEOUT,
                }

                async with websockets.connect(ws_url, **ws_kwargs) as ws:
                    logger.info(f"WebSocket连接成功: {interval}")
                    retry_count = 0

                    while self.is_running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            data = json.loads(message)
                            await self.process_kline(interval, data)
                        except asyncio.TimeoutError:
                            # 发送ping保持连接
                            await ws.ping()
                        except websockets.ConnectionClosed:
                            logger.warning(f"WebSocket连接关闭: {interval}")
                            break

            except Exception as e:
                retry_count += 1
                logger.error(f"WebSocket错误 ({interval}): {e}, 重试 {retry_count}/{MAX_RETRIES}")
                await asyncio.sleep(5 * retry_count)

    async def process_kline(self, interval: str, data: Dict[str, Any]):
        """处理K线数据"""
        buffer = self.mtf_buffer.get_buffer(interval)
        if buffer is None:
            return

        # 获取K线数据
        kline_data = data.get('k', {})
        if not kline_data:
            return

        # 检查是否是K线关闭
        is_closed = kline_data.get('x', False)

        # 更新缓冲区
        buffer.update_from_ws(kline_data)

        # 只在主周期K线关闭时生成信号
        if interval == self.primary_interval and is_closed:
            await self.generate_signal()

    async def generate_signal(self):
        """生成交易信号"""
        # 获取主周期数据
        primary_data = self.mtf_buffer.get_ohlcv_data(self.primary_interval)
        if primary_data is None:
            return

        # 获取确认周期数据
        timeframe_data = {}
        for interval in self.confirmation_intervals:
            tf_data = self.mtf_buffer.get_ohlcv_data(interval)
            if tf_data:
                timeframe_data[interval] = tf_data

        # 生成信号
        signal = self.signal_generator.generate(
            highs=primary_data["highs"],
            lows=primary_data["lows"],
            closes=primary_data["closes"],
            volumes=primary_data["volumes"],
            timeframe_data=timeframe_data if timeframe_data else None
        )

        # 处理信号
        await self.handle_signal(signal)

    async def handle_signal(self, signal: TradingSignal):
        """处理生成的信号"""
        # 保存信号历史
        self.signal_history.append(signal)
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

        self.last_signal = signal

        # 输出信号信息
        if signal.direction != SignalDirection.HOLD:
            print("\n" + "=" * 60)
            print(self.signal_generator.get_signal_summary(signal))
            print("=" * 60 + "\n")

            # A级和B级信号特别提醒
            if signal.grade in [SignalGrade.A, SignalGrade.B]:
                self._alert_signal(signal)
        else:
            # 无信号时的简单日志
            self._print_status_line(signal)

    def _alert_signal(self, signal: TradingSignal):
        """强信号提醒"""
        direction = "做多" if signal.direction == SignalDirection.BUY else "做空"
        grade = signal.grade.value

        alert_msg = f"""
🚨 {'='*40} 🚨
   {grade}级{direction}信号 @ {signal.entry_price:.2f}
   强度: {signal.adjusted_strength:.0%}
   市场状态: {signal.market_state.value}
   确认: {signal.confirmation_count}个周期
🚨 {'='*40} 🚨
"""
        print(alert_msg)

    def _print_status_line(self, signal: TradingSignal):
        """打印状态行"""
        now = datetime.now().strftime("%H:%M:%S")
        primary_data = self.mtf_buffer.get_ohlcv_data(self.primary_interval)

        if primary_data:
            current_price = primary_data["closes"][-1]
            adx = signal.indicator_values.get('adx', 0) or 0
            state = signal.market_state.value

            status = f"[{now}] {self.symbol} | 价格: {current_price:.2f} | ADX: {adx:.1f} | 状态: {state}"
            print(f"\r{status}", end="", flush=True)

    async def start(self):
        """启动实时交易系统"""
        self.is_running = True

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║          实时交易系统 V2 - 状态机驱动策略                      ║
╠══════════════════════════════════════════════════════════════╣
║  交易对: {self.symbol:<15}                                    ║
║  主周期: {self.primary_interval:<15}                                    ║
║  确认周期: {', '.join(self.confirmation_intervals):<13}                              ║
╚══════════════════════════════════════════════════════════════╝
        """)

        # 初始化历史数据
        await self.initialize_buffers()

        # 启动WebSocket连接
        tasks = [
            self.connect_websocket(interval)
            for interval in self.all_intervals
        ]

        print("\n开始监听实时K线数据...\n")

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.is_running = False

    def stop(self):
        """停止系统"""
        self.is_running = False
        logger.info("系统已停止")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='实时交易系统 V2')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='交易对')
    parser.add_argument('--interval', type=str, default='5m', help='主周期')
    parser.add_argument('--confirm', type=str, nargs='+', default=['15m', '1h'],
                        help='确认周期列表')

    args = parser.parse_args()

    system = LiveTradingSystemV2(
        symbol=args.symbol,
        primary_interval=args.interval,
        confirmation_intervals=args.confirm
    )

    try:
        await system.start()
    except KeyboardInterrupt:
        print("\n\n正在停止系统...")
        system.stop()


if __name__ == "__main__":
    asyncio.run(main())
