# -*- coding: utf-8 -*-
"""
Binance WebSocket indicator accuracy tester.

用法：
    python binance_indicator_tester.py --symbol BTCUSDT --interval 5m --contract perpetual

脚本流程：
1. 先用 REST API 拉取一定数量的历史K线，初始化 StreamingKlineBuffer；
2. 连接 Binance WebSocket (连续合约K线)，实时更新缓冲区，未收盘K线使用“最新价格”；
3. 每根K线收盘后，再次通过 REST 拉取最新历史K线作为参考，
   计算指标并与实时流计算的结果对比，输出差值，帮助验证指标准确性。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import signal
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientError
import websockets

from config import (
    BINANCE_API_URL,
    BINANCE_WS_URL,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_INTERVAL,
    DEFAULT_SYMBOL,
    INDICATOR_SWITCHES,
    MACD_PARAMS,
    RSI_PARAMS,
    BB_PARAMS,
    KDJ_PARAMS,
    EMA_PARAMS,
    CCI_PARAMS,
    ATR_PARAMS,
    REQUEST_TIMEOUT,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_CLOSE_TIMEOUT,
    USE_PROXY,
    PROXY_URL,
)
from indicators import (
    MACDIndicator,
    RSIIndicator,
    BollingerBandsIndicator,
    KDJIndicator,
    EMAFourLineSystem,
    CCIIndicator,
    ATRIndicator,
    StreamingKlineBuffer,
    StreamingCandle,
)


class BinanceIndicatorAccuracyTester:
    """接入Binance WebSocket，对比实时指标与REST参考值。"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        contract_type: str,
        history_limit: int = 400,
        reference_limit: int = 200,
        log_interval: float = 5.0,
    ) -> None:
        self.symbol = symbol.upper()
        self.interval = interval
        self.contract_type = contract_type.upper()
        self.history_limit = history_limit
        self.reference_limit = reference_limit
        self.log_interval = log_interval

        ws_base = BINANCE_WS_URL.rstrip("/")
        stream = f"{self.symbol.lower()}_{self.contract_type.lower()}@continuousKline_{self.interval}"
        self.ws_url = f"{ws_base}/ws/{stream}"

        self.buffer = StreamingKlineBuffer(max_closed=max(history_limit, reference_limit) + 10)
        self.last_live_log = 0.0
        self.last_closed_ts: Optional[int] = None
        self.http_timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.use_proxy = USE_PROXY
        self.proxy_url = PROXY_URL

        # 指标实例（根据config的开关）
        switches = INDICATOR_SWITCHES
        self.macd = MACDIndicator(
            MACD_PARAMS["fast_period"],
            MACD_PARAMS["slow_period"],
            MACD_PARAMS["signal_period"],
        ) if switches.get("use_macd") else None
        self.rsi = RSIIndicator(RSI_PARAMS["period"]) if switches.get("use_rsi") else None
        self.bb = BollingerBandsIndicator(BB_PARAMS["period"], BB_PARAMS["std_dev"]) if switches.get("use_boll") else None
        self.kdj = KDJIndicator(KDJ_PARAMS["period"], KDJ_PARAMS["signal"]) if switches.get("use_kdj") else None
        self.ema = EMAFourLineSystem(
            EMA_PARAMS["ultra_fast"],
            EMA_PARAMS["fast"],
            EMA_PARAMS["medium"],
            EMA_PARAMS["slow"],
        ) if switches.get("use_ema") else None
        self.cci = CCIIndicator(CCI_PARAMS["period"]) if switches.get("use_cci") else None
        self.atr = ATRIndicator(ATR_PARAMS["period"]) if switches.get("use_atr") else None

    async def start(self) -> None:
        """入口：先加载历史数据，再启动WebSocket循环。"""
        await self._load_initial_history()
        print(f"[INFO] WebSocket URL: {self.ws_url}")
        await self._stream_loop()

    async def _fetch_klines(self, limit: int, retries: int = 5) -> List[List[Any]]:
        """通过REST接口获取历史K线（带重试）。"""
        url = f"{BINANCE_API_URL.rstrip('/')}/fapi/v1/continuousKlines"
        params = {
            "pair": self.symbol,
            "contractType": self.contract_type,
            "interval": self.interval,
            "limit": limit,
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            connector = None
            if self.use_proxy:
                from aiohttp_socks import ProxyConnector  # type: ignore

                connector = ProxyConnector.from_url(self.proxy_url)

            try:
                async with aiohttp.ClientSession(timeout=self.http_timeout, connector=connector) as session:
                    async with session.get(url, params=params) as resp:
                        resp.raise_for_status()
                        return await resp.json()
            except (ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                wait = min(2 ** (attempt - 1), 10)
                print(f"[WARN] 获取历史K线失败({attempt}/{retries}): {exc}. {wait}s后重试...")
                await asyncio.sleep(wait)

        raise RuntimeError(f"连续{retries}次请求失败: {last_error}")

    async def _load_initial_history(self) -> None:
        """拉取历史数据，初始化缓冲区。"""
        print(f"[INIT] 载入最近 {self.history_limit} 根K线...")
        klines = await self._fetch_klines(self.history_limit)

        # Binance REST API 会返回当前未收盘的K线
        # K线数据格式: [open_time, open, high, low, close, volume, close_time, ...]
        current_time_ms = int(time.time() * 1000)

        for entry in klines:
            close_time = int(entry[6])  # close_time 是第7个字段
            is_closed = close_time < current_time_ms

            candle = StreamingCandle(
                timestamp=int(entry[0]),
                open=float(entry[1]),
                high=float(entry[2]),
                low=float(entry[3]),
                close=float(entry[4]),
                volume=float(entry[5]),
                is_closed=is_closed,
            )
            self.buffer.update(candle)

        if klines:
            first_ts = datetime.fromtimestamp(klines[0][0] / 1000)
            last_ts = datetime.fromtimestamp(klines[-1][0] / 1000)
            closed_count = len(self.buffer.closed_candles)
            has_active = self.buffer.active_candle is not None
            print(f"[INIT] 完成，时间范围 {first_ts} -> {last_ts}")
            print(f"[INIT] 已收盘K线: {closed_count}, 当前K线: {'有' if has_active else '无'}")

    async def _stream_loop(self) -> None:
        """维护WebSocket连接并处理推送。"""
        ws_kwargs = {
            "ping_interval": WS_PING_INTERVAL,
            "ping_timeout": WS_PING_TIMEOUT,
            "close_timeout": WS_CLOSE_TIMEOUT,
        }

        while True:
            try:
                async with websockets.connect(self.ws_url, **ws_kwargs) as ws:
                    print("[INFO] WebSocket connected.")
                    async for raw in ws:
                        data = json.loads(raw)
                        k = data.get("k")
                        if not k:
                            continue
                        self.buffer.update_from_ws(k)
                        await self._handle_stream_kline(k)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[WARN] WebSocket异常: {exc}. 5秒后重试...")
                await asyncio.sleep(5)

    async def _handle_stream_kline(self, payload: Dict[str, Any]) -> None:
        """处理每条K线推送。"""
        timestamp = int(payload["t"])
        is_closed = bool(payload["x"])

        now = time.time()
        if now - self.last_live_log >= self.log_interval:
            snapshot = self._calculate_indicators(self.buffer.get_price_arrays())
            self._print_live_snapshot(payload, snapshot)
            self.last_live_log = now

        if is_closed and timestamp != self.last_closed_ts:
            self.last_closed_ts = timestamp
            await self._compare_with_reference(payload)

    async def _compare_with_reference(self, payload: Dict[str, Any]) -> None:
        """K线收盘时，拉取参考数据并输出差值。"""
        live_arrays = self.buffer.get_price_arrays(include_current=False)
        live_snapshot = self._calculate_indicators(live_arrays)

        reference_snapshot: Dict[str, Dict[str, float]] = {}
        try:
            reference_arrays = await self._build_reference_arrays()
            ref_length = len(reference_arrays.get("closes", []))
            if ref_length > 0:
                live_arrays = self._limit_arrays(live_arrays, ref_length)
                reference_arrays = self._limit_arrays(reference_arrays, ref_length)
                live_snapshot = self._calculate_indicators(live_arrays)
            reference_snapshot = self._calculate_indicators(reference_arrays)
        except Exception as exc:
            print(f"[WARN] 获取参考数据失败: {exc}")

        comparison = self._compare_snapshots(live_snapshot, reference_snapshot)
        self._print_accuracy(payload, live_snapshot, comparison)

    async def _build_reference_arrays(self) -> Dict[str, List[float]]:
        """重新拉取一次历史K线作为参考，保证全量收盘数据。"""
        klines = await self._fetch_klines(self.reference_limit)

        # Binance REST API 会返回当前未收盘的K线，需要排除
        # K线数据格式: [open_time, open, high, low, close, volume, close_time, ...]
        # 通过检查 close_time 是否已经过去来判断是否收盘
        import time
        current_time_ms = int(time.time() * 1000)

        candles = []
        for entry in klines:
            close_time = int(entry[6])  # close_time 是第7个字段
            # 只保留已收盘的K线（close_time 已经过去）
            if close_time < current_time_ms:
                candles.append(StreamingCandle(
                    timestamp=int(entry[0]),
                    open=float(entry[1]),
                    high=float(entry[2]),
                    low=float(entry[3]),
                    close=float(entry[4]),
                    volume=float(entry[5]),
                    is_closed=True,
                ))

        arrays = {
            "opens": [c.open for c in candles],
            "highs": [c.high for c in candles],
            "lows": [c.low for c in candles],
            "closes": [c.close for c in candles],
            "volumes": [c.volume for c in candles],
        }
        return arrays

    def _limit_arrays(self, arrays: Dict[str, List[float]], limit: Optional[int]) -> Dict[str, List[float]]:
        """截取数组尾部，保证实时与参考使用相同的数据窗口。"""
        if not limit or limit <= 0:
            return arrays

        limited: Dict[str, List[float]] = {}
        for key, values in arrays.items():
            if len(values) <= limit:
                limited[key] = list(values)
            else:
                limited[key] = values[-limit:]
        return limited

    def _calculate_indicators(self, arrays: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
        """基于给定数组计算所有启用的指标。"""
        closes = arrays["closes"]
        highs = arrays["highs"]
        lows = arrays["lows"]
        volumes = arrays["volumes"]
        snapshot: Dict[str, Dict[str, float]] = {}

        if not closes:
            return snapshot

        if self.macd:
            macd = self.macd.calculate(closes)
            if macd["macd_line"] is not None and macd["signal_line"] is not None:
                snapshot["MACD"] = {
                    "macd": float(macd["macd_line"]),
                    "signal": float(macd["signal_line"]),
                    "hist": float(macd["histogram"]),
                }

        if self.rsi:
            rsi = self.rsi.calculate(closes)
            if rsi["rsi"] is not None:
                snapshot["RSI"] = {"rsi": float(rsi["rsi"])}

        if self.bb:
            bb = self.bb.calculate(closes)
            if bb["middle_band"] is not None:
                snapshot["BOLL"] = {
                    "upper": float(bb["upper_band"]),
                    "mid": float(bb["middle_band"]),
                    "lower": float(bb["lower_band"]),
                    "percent_b": float(bb["percent_b"]),
                }

        if self.kdj:
            kdj = self.kdj.calculate(highs, lows, closes)
            if kdj["k"] is not None:
                snapshot["KDJ"] = {
                    "k": float(kdj["k"]),
                    "d": float(kdj["d"]),
                    "j": float(kdj["j"]),
                }

        if self.ema:
            ema = self.ema.calculate(closes)
            if ema["ema_slow"] is not None:
                snapshot["EMA"] = {
                    "ultra_fast": float(ema["ema_ultra_fast"]),
                    "fast": float(ema["ema_fast"]),
                    "medium": float(ema["ema_medium"]),
                    "slow": float(ema["ema_slow"]),
                }

        if self.cci:
            cci = self.cci.calculate(highs, lows, closes)
            if cci["cci"] is not None:
                snapshot["CCI"] = {"cci": float(cci["cci"])}

        if self.atr:
            atr = self.atr.calculate(highs, lows, closes)
            if atr["atr"] is not None:
                snapshot["ATR"] = {"atr": float(atr["atr"])}


        return snapshot

    def _compare_snapshots(
        self, live: Dict[str, Dict[str, float]], reference: Dict[str, Dict[str, float]]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """对比实时数据与参考数据，返回差值。"""
        comparison: Dict[str, Dict[str, Dict[str, float]]] = {}
        for indicator, live_values in live.items():
            reference_values = reference.get(indicator)
            if not reference_values:
                continue
            diffs: Dict[str, Dict[str, float]] = {}
            for key, live_value in live_values.items():
                ref_value = reference_values.get(key)
                if ref_value is None:
                    continue
                diffs[key] = {
                    "live": live_value,
                    "ref": ref_value,
                    "diff": abs(live_value - ref_value),
                }
            if diffs:
                comparison[indicator] = diffs
        return comparison

    def _print_live_snapshot(self, payload: Dict[str, Any], snapshot: Dict[str, Dict[str, float]]) -> None:
        """实时输出最新价与部分指标。"""
        if not snapshot:
            return
        ts = datetime.fromtimestamp(int(payload["t"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        close_price = float(payload["c"])
        status = "CLOSED" if payload["x"] else "LIVE"
        line = f"[{status}] {ts} close={close_price:.2f}"

        highlight = []
        if "RSI" in snapshot:
            highlight.append(f"RSI {snapshot['RSI']['rsi']:.2f}")
        if "MACD" in snapshot:
            highlight.append(f"MACD hist {snapshot['MACD']['hist']:.5f}")
        if "BOLL" in snapshot:
            highlight.append(f"%B {snapshot['BOLL']['percent_b']:.3f}")
        if "KDJ" in snapshot:
            highlight.append(f"K {snapshot['KDJ']['k']:.1f}/D {snapshot['KDJ']['d']:.1f}")
        if "EMA" in snapshot:
            ema = snapshot["EMA"]
            highlight.append(f"EMA(f/m/s) {ema['fast']:.2f}/{ema['medium']:.2f}/{ema['slow']:.2f}")
        if "CCI" in snapshot:
            highlight.append(f"CCI {snapshot['CCI']['cci']:.1f}")
        if "ATR" in snapshot:
            highlight.append(f"ATR {snapshot['ATR']['atr']:.2f}")
      
        if highlight:
            line += " | " + " | ".join(highlight)
        print(line)

    def _print_accuracy(
        self,
        payload: Dict[str, Any],
        snapshot: Dict[str, Dict[str, float]],
        comparison: Dict[str, Dict[str, Dict[str, float]]],
    ) -> None:
        """输出实时指标与REST参考值之间的差异。"""
        ts = datetime.fromtimestamp(int(payload["t"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        close_price = float(payload["c"])
        print(f"[CLOSE] {ts} close={close_price:.2f}, volume={payload['v']}")

        if not comparison:
            print("        无可对比的指标（数据可能不足）")
            return

        for indicator, fields in comparison.items():
            parts = []
            for name, values in fields.items():
                diff = values["diff"]
                parts.append(
                    f"{name}: live={values['live']:.6f} ref={values['ref']:.6f} Δ={diff:.6g}"
                )
            print(f"        {indicator}: " + "; ".join(parts))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Binance WebSocket 指标准确性测试工具")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="交易对 (默认: %(default)s)")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="K线周期 (默认: %(default)s)")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT_TYPE, help="合约类型 (默认: %(default)s)")
    parser.add_argument("--history", type=int, default=400, help="初始化历史K线数量")
    parser.add_argument("--reference", type=int, default=200, help="参考K线数量（REST对比）")
    parser.add_argument("--log-interval", type=float, default=5.0, help="实时输出间隔（秒）")
    args = parser.parse_args()

    tester = BinanceIndicatorAccuracyTester(
        symbol=args.symbol,
        interval=args.interval,
        contract_type=args.contract,
        history_limit=args.history,
        reference_limit=args.reference,
        log_interval=args.log_interval,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_sigint() -> None:
        if not stop_event.is_set():
            stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_sigint)

    runner = asyncio.create_task(tester.start())
    stopper = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait(
        {runner, stopper},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stopper in done and not stop_event.is_set():
        stop_event.set()

    for task in pending:
        task.cancel()

    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    if not runner.done():
        runner.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await runner


if __name__ == "__main__":
    asyncio.run(main())
