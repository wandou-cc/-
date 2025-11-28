# -*- coding: utf-8 -*-
"""
Streaming helpers for WebSocket based indicator calculation.

These helpers keep an in-memory K线序列，保证：
1. WebSocket 同一根K线多次推送时不会重复写入历史；
2. 最新一根未收盘K线始终以“当前收盘价=最新推送价格”的方式参与指标计算；
3. 只在K线真正收盘时才写入历史队列，避免信号重复触发。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Deque, Dict, List, Optional


@dataclass
class StreamingCandle:
    """单根K线的内部表示."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False

    def merge(self, other: "StreamingCandle") -> None:
        """融合同一时间戳的最新推送."""
        if self.timestamp != other.timestamp:
            raise ValueError("无法合并不同时间戳的K线")
        self.high = max(self.high, other.high)
        self.low = min(self.low, other.low)
        self.close = other.close
        self.volume = other.volume
        self.is_closed = other.is_closed

    def clone(self) -> "StreamingCandle":
        """返回副本，避免外部意外修改内部数据."""
        return replace(self)


class StreamingKlineBuffer:
    """
    维护实时K线序列的环形缓冲区，配合无状态指标使用。

    - closed_candles 只存储已经收盘的K线
    - active_candle 保持最新（可能未收盘）的K线
    """

    def __init__(self, max_closed: int = 500):
        self.closed_candles: Deque[StreamingCandle] = deque(maxlen=max_closed)
        self.active_candle: Optional[StreamingCandle] = None
        self.last_closed_ts: Optional[int] = None

    def update(self, candle: StreamingCandle) -> None:
        """
        用最新的WebSocket推送更新缓冲区。

        Args:
            candle: 新推送到的K线数据
        """
        if candle.is_closed and self.last_closed_ts and candle.timestamp <= self.last_closed_ts:
            # Binance在重连时可能重复下发已收盘K线，这里直接丢弃
            return

        if self.active_candle and candle.timestamp == self.active_candle.timestamp:
            # 同一根K线的增量更新
            self.active_candle.merge(candle)
        else:
            # 新时间戳 -> 将上一根K线落盘后再替换
            self._finalize_active()
            self.active_candle = candle.clone()

        if self.active_candle and self.active_candle.is_closed:
            self._finalize_active()

    def update_from_ws(self, payload: Dict[str, str]) -> None:
        """
        直接传入Binance/k线推送中的 `k` 字段.

        Args:
            payload: 形如
                {
                    "t": 123456789,  # 开始时间毫秒
                    "o": "1.0",
                    "h": "1.2",
                    "l": "0.8",
                    "c": "1.1",
                    "v": "123.45",
                    "x": true/false  # 是否收盘
                }
        """
        candle = StreamingCandle(
            timestamp=int(payload["t"]),
            open=float(payload["o"]),
            high=float(payload["h"]),
            low=float(payload["l"]),
            close=float(payload["c"]),
            volume=float(payload["v"]),
            is_closed=bool(payload["x"]),
        )
        self.update(candle)

    def get_candles(self, include_current: bool = True) -> List[StreamingCandle]:
        """
        以列表形式返回当前缓冲区中的K线。

        Args:
            include_current: 是否包含尚未收盘的最后一根K线
        """
        candles = [c.clone() for c in self.closed_candles]
        if include_current and self.active_candle:
            candles.append(self.active_candle.clone())
        return candles

    def get_price_arrays(self, include_current: bool = True) -> Dict[str, List[float]]:
        """
        直接返回价格、成交量数组，供无状态指标使用。
        """
        candles = self.get_candles(include_current=include_current)
        opens = [c.open for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        return {
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
        }

    def _finalize_active(self) -> None:
        if not self.active_candle:
            return
        self.active_candle.is_closed = True
        self.last_closed_ts = self.active_candle.timestamp
        self.closed_candles.append(self.active_candle)
        self.active_candle = None

