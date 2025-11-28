# -*- coding: utf-8 -*-
"""
实时交易仪表盘 - Rich 版本

基于 Rich 库的美观实时交易信息展示，包括：
- 市场状态概览
- 实时价格和指标
- 交易信号
- 多周期确认状态
- 信号历史记录

使用方法：
    python live_dashboard.py --symbol BTCUSDT --interval 5m
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import argparse
import time
import uuid

try:
    import websockets
    from aiohttp_socks import ProxyConnector
    import aiohttp
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.style import Style
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
except ImportError as e:
    print(f"请安装依赖: pip install websockets aiohttp aiohttp-socks rich")
    print(f"缺失模块: {e}")
    exit(1)

from config import (
    BINANCE_API_URL, BINANCE_WS_URL,
    USE_PROXY, PROXY_URL,
    WS_PING_INTERVAL, WS_PING_TIMEOUT, MAX_RETRIES
)
from strategy_config import get_multi_timeframe_config
from indicators import StreamingKlineBuffer
from strategy import (
    SignalGenerator, TradingSignal,
    MarketState, MarketStateDetector, SignalDirection
)


@dataclass
class PendingVerification:
    """待验证的信号"""
    signal_id: str                    # 信号唯一ID
    signal: TradingSignal             # 原始信号
    entry_price: float                # 开单价格
    entry_time: datetime              # 开单时间
    verify_10min_time: datetime       # 10分钟验证时间
    verify_30min_time: datetime       # 30分钟验证时间
    verified_10min: bool = False      # 是否已验证10分钟
    verified_30min: bool = False      # 是否已验证30分钟
    result_10min: Optional[str] = None   # 10分钟结果: "correct", "wrong", "pending"
    result_30min: Optional[str] = None   # 30分钟结果
    price_at_10min: Optional[float] = None  # 10分钟时的价格
    price_at_30min: Optional[float] = None  # 30分钟时的价格
    profit_10min: Optional[float] = None    # 10分钟盈亏百分比
    profit_30min: Optional[float] = None    # 30分钟盈亏百分比


@dataclass
class VerificationStats:
    """验证统计"""
    total_verified_10min: int = 0
    correct_10min: int = 0
    wrong_10min: int = 0
    total_verified_30min: int = 0
    correct_30min: int = 0
    wrong_30min: int = 0

    @property
    def accuracy_10min(self) -> float:
        if self.total_verified_10min == 0:
            return 0.0
        return self.correct_10min / self.total_verified_10min

    @property
    def accuracy_30min(self) -> float:
        if self.total_verified_30min == 0:
            return 0.0
        return self.correct_30min / self.total_verified_30min

# 禁用 logging 输出到控制台
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Rich 控制台
console = Console()


@dataclass
class DashboardState:
    """仪表盘状态数据"""
    # 基本信息
    symbol: str = "BTCUSDT"
    primary_interval: str = "5m"
    confirmation_intervals: List[str] = field(default_factory=lambda: ["15m", "1h"])

    # 连接状态
    ws_connected: Dict[str, bool] = field(default_factory=dict)
    last_update: Optional[datetime] = None

    # 价格数据
    current_price: float = 0.0
    price_change_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_24h: float = 0.0

    # 市场状态
    market_state: MarketState = MarketState.UNKNOWN
    market_state_confidence: float = 0.0
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    trend_strength: str = "unknown"

    # 指标数据
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema5: Optional[float] = None
    ema20: Optional[float] = None
    ema60: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_percent_b: Optional[float] = None
    atr: Optional[float] = None
    volume_ratio: Optional[float] = None

    # 当前信号
    current_signal: Optional[TradingSignal] = None

    # 信号历史
    signal_history: List[TradingSignal] = field(default_factory=list)

    # K线数量
    kline_counts: Dict[str, int] = field(default_factory=dict)

    # 运行统计
    start_time: Optional[datetime] = None
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0

    # 信号去重：记录上一个有效信号的关键信息
    last_signal_direction: Optional[SignalDirection] = None
    last_signal_kline_time: Optional[int] = None  # 产生信号时的K线开盘时间

    # 信号验证
    pending_verifications: List[PendingVerification] = field(default_factory=list)
    completed_verifications: List[PendingVerification] = field(default_factory=list)
    verification_stats: VerificationStats = field(default_factory=VerificationStats)


class RichDashboard:
    """Rich 实时仪表盘"""

    def __init__(self, state: DashboardState):
        self.state = state
        self.layout = self._create_layout()

    def _create_layout(self) -> Layout:
        """创建布局"""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="middle", ratio=1),
            Layout(name="right", ratio=1)
        )

        layout["left"].split_column(
            Layout(name="market_state", size=12),
            Layout(name="indicators", ratio=1)
        )

        layout["middle"].split_column(
            Layout(name="signal", size=16),
            Layout(name="history", ratio=1)
        )

        layout["right"].split_column(
            Layout(name="verification", size=14),
            Layout(name="verification_history", ratio=1)
        )

        return layout

    def _make_header(self) -> Panel:
        """创建头部面板"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = ""
        if self.state.start_time:
            delta = datetime.now() - self.state.start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f" | 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}"

        # 连接状态
        ws_status = []
        for interval, connected in self.state.ws_connected.items():
            status = "[green]●[/]" if connected else "[red]●[/]"
            ws_status.append(f"{interval}:{status}")
        ws_str = " ".join(ws_status) if ws_status else "[yellow]等待连接...[/]"

        header_text = Text()
        header_text.append("🚀 实时交易仪表盘 V2 ", style="bold cyan")
        header_text.append(f"| {self.state.symbol} ", style="bold white")
        header_text.append(f"| {now}{uptime} ", style="dim")
        header_text.append(f"| WS: {ws_str}")

        return Panel(header_text, style="blue")

    def _make_market_state(self) -> Panel:
        """创建市场状态面板"""
        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        table.add_column("项目", style="cyan", width=12)
        table.add_column("值", justify="right")

        # 价格信息
        price_style = "green" if self.state.price_change_24h >= 0 else "red"
        change_symbol = "+" if self.state.price_change_24h >= 0 else ""
        table.add_row("当前价格", f"[bold {price_style}]${self.state.current_price:,.2f}[/]")
        table.add_row("24h涨跌", f"[{price_style}]{change_symbol}{self.state.price_change_24h:.2f}%[/]")
        table.add_row("24h最高", f"${self.state.high_24h:,.2f}")
        table.add_row("24h最低", f"${self.state.low_24h:,.2f}")

        # 市场状态
        state_colors = {
            MarketState.RANGING: "yellow",
            MarketState.TRENDING_UP: "green",
            MarketState.TRENDING_DOWN: "red",
            MarketState.BREAKOUT_UP: "bold green",
            MarketState.BREAKOUT_DOWN: "bold red",
            MarketState.UNKNOWN: "dim"
        }
        state_names = {
            MarketState.RANGING: "震荡盘整",
            MarketState.TRENDING_UP: "上升趋势",
            MarketState.TRENDING_DOWN: "下降趋势",
            MarketState.BREAKOUT_UP: "向上突破",
            MarketState.BREAKOUT_DOWN: "向下突破",
            MarketState.UNKNOWN: "未知"
        }
        state_color = state_colors.get(self.state.market_state, "dim")
        state_name = state_names.get(self.state.market_state, "未知")
        table.add_row("", "")
        table.add_row("市场状态", f"[{state_color}]{state_name}[/]")
        table.add_row("置信度", f"{self.state.market_state_confidence:.0%}")

        # ADX
        adx_str = f"{self.state.adx:.1f}" if self.state.adx else "N/A"
        adx_color = "green" if self.state.adx and self.state.adx > 25 else "yellow" if self.state.adx and self.state.adx > 20 else "dim"
        table.add_row("ADX", f"[{adx_color}]{adx_str}[/]")

        # DI
        if self.state.plus_di and self.state.minus_di:
            di_str = f"+DI:{self.state.plus_di:.1f} -DI:{self.state.minus_di:.1f}"
            di_color = "green" if self.state.plus_di > self.state.minus_di else "red"
        else:
            di_str = "N/A"
            di_color = "dim"
        table.add_row("DI", f"[{di_color}]{di_str}[/]")

        return Panel(table, title="📊 市场状态", border_style="blue")

    def _make_indicators(self) -> Panel:
        """创建指标面板"""
        table = Table(show_header=True, box=box.SIMPLE, expand=True)
        table.add_column("指标", style="cyan", width=10)
        table.add_column("值", justify="right", width=12)
        table.add_column("状态", width=10)

        # RSI
        if self.state.rsi:
            rsi_status = "超买" if self.state.rsi > 70 else "超卖" if self.state.rsi < 30 else "正常"
            rsi_color = "red" if self.state.rsi > 70 else "green" if self.state.rsi < 30 else "white"
            table.add_row("RSI", f"{self.state.rsi:.1f}", f"[{rsi_color}]{rsi_status}[/]")
        else:
            table.add_row("RSI", "N/A", "[dim]等待数据[/]")

        # MACD
        if self.state.macd_histogram is not None:
            macd_status = "多头" if self.state.macd_histogram > 0 else "空头"
            macd_color = "green" if self.state.macd_histogram > 0 else "red"
            table.add_row("MACD柱", f"{self.state.macd_histogram:.4f}", f"[{macd_color}]{macd_status}[/]")
        else:
            table.add_row("MACD柱", "N/A", "[dim]等待数据[/]")

        # EMA
        if self.state.ema5 and self.state.ema20 and self.state.ema60:
            if self.state.ema5 > self.state.ema20 > self.state.ema60:
                ema_status = "多头排列"
                ema_color = "green"
            elif self.state.ema5 < self.state.ema20 < self.state.ema60:
                ema_status = "空头排列"
                ema_color = "red"
            else:
                ema_status = "交叉中"
                ema_color = "yellow"
            table.add_row("EMA", f"{self.state.ema20:.2f}", f"[{ema_color}]{ema_status}[/]")
        else:
            table.add_row("EMA", "N/A", "[dim]等待数据[/]")

        # 布林带
        if self.state.bb_percent_b is not None:
            if self.state.bb_percent_b > 0.8:
                bb_status = "接近上轨"
                bb_color = "red"
            elif self.state.bb_percent_b < 0.2:
                bb_status = "接近下轨"
                bb_color = "green"
            else:
                bb_status = "中间区域"
                bb_color = "white"
            table.add_row("BOLL %B", f"{self.state.bb_percent_b:.2f}", f"[{bb_color}]{bb_status}[/]")
        else:
            table.add_row("BOLL %B", "N/A", "[dim]等待数据[/]")

        # ATR
        if self.state.atr:
            table.add_row("ATR", f"{self.state.atr:.2f}", "[white]波动率[/]")
        else:
            table.add_row("ATR", "N/A", "[dim]等待数据[/]")

        # 成交量
        if self.state.volume_ratio:
            vol_status = "放量" if self.state.volume_ratio > 1.5 else "缩量" if self.state.volume_ratio < 0.7 else "正常"
            vol_color = "yellow" if self.state.volume_ratio > 1.5 else "dim" if self.state.volume_ratio < 0.7 else "white"
            table.add_row("成交量比", f"{self.state.volume_ratio:.2f}x", f"[{vol_color}]{vol_status}[/]")
        else:
            table.add_row("成交量比", "N/A", "[dim]等待数据[/]")

        # K线数量
        table.add_row("", "", "")
        for interval, count in self.state.kline_counts.items():
            table.add_row(f"K线({interval})", str(count), "")

        return Panel(table, title="📈 技术指标", border_style="green")

    def _make_signal(self) -> Panel:
        """创建信号面板"""
        signal = self.state.current_signal

        if signal is None or signal.direction == SignalDirection.HOLD:
            content = Text("等待信号...", style="dim", justify="center")
            return Panel(content, title="🎯 当前信号", border_style="dim")

        # 信号方向和等级
        if signal.direction == SignalDirection.BUY:
            direction_text = "🟢 做多 (BUY)"
            direction_style = "bold green"
        else:
            direction_text = "🔴 做空 (SELL)"
            direction_style = "bold red"

        grade_colors = {"A": "green", "B": "yellow", "C": "red", "NONE": "dim"}
        grade_color = grade_colors.get(signal.grade.value, "dim")

        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        table.add_column("", width=12)
        table.add_column("", justify="right")

        table.add_row("方向", f"[{direction_style}]{direction_text}[/]")
        table.add_row("等级", f"[{grade_color}][bold]{signal.grade.value}级[/][/]")
        table.add_row("强度", f"{signal.strength:.0%} → {signal.adjusted_strength:.0%}")
        table.add_row("策略", signal.strategy_used)
        table.add_row("确认", f"{'✓' if signal.is_confirmed else '✗'} ({signal.confirmation_count}个周期)")

        table.add_row("", "")
        table.add_row("入场价", f"[bold]${signal.entry_price:,.2f}[/]")
        if signal.stop_loss:
            table.add_row("止损价", f"[red]${signal.stop_loss:,.2f}[/]")
        if signal.take_profit:
            table.add_row("止盈价", f"[green]${signal.take_profit:,.2f}[/]")

        # 预测
        if signal.predictions:
            table.add_row("", "")
            table.add_row("[cyan]预测[/]", "")
            for pred in signal.predictions[:3]:
                arrow = "↑" if pred.direction == "up" else "↓"
                color = "green" if pred.direction == "up" else "red"
                table.add_row(
                    f"  {pred.horizon_minutes}分钟",
                    f"[{color}]{arrow} {pred.confidence:.0%}[/]"
                )

        # 原因
        if signal.reasons:
            table.add_row("", "")
            table.add_row("[cyan]原因[/]", "")
            for reason in signal.reasons[:3]:
                # 截断过长的原因
                short_reason = reason[:30] + "..." if len(reason) > 30 else reason
                table.add_row("", f"[dim]• {short_reason}[/]")

        border_style = "green" if signal.direction == SignalDirection.BUY else "red"
        return Panel(table, title="🎯 当前信号", border_style=border_style)

    def _make_history(self) -> Panel:
        """创建历史记录面板"""
        table = Table(show_header=True, box=box.SIMPLE, expand=True)
        table.add_column("时间", width=8)
        table.add_column("方向", width=6)
        table.add_column("等级", width=4)
        table.add_column("强度", width=6)
        table.add_column("价格", width=12)

        # 只显示有效信号
        valid_signals = [
            s for s in self.state.signal_history
            if s.direction != SignalDirection.HOLD
        ][-10:]  # 最近10条

        for signal in reversed(valid_signals):
            time_str = signal.timestamp.strftime("%H:%M:%S")

            if signal.direction == SignalDirection.BUY:
                direction = "[green]买入[/]"
            else:
                direction = "[red]卖出[/]"

            grade_colors = {"A": "green", "B": "yellow", "C": "red"}
            grade_color = grade_colors.get(signal.grade.value, "dim")
            grade = f"[{grade_color}]{signal.grade.value}[/]"

            strength = f"{signal.adjusted_strength:.0%}"
            price = f"${signal.entry_price:,.2f}"

            table.add_row(time_str, direction, grade, strength, price)

        if not valid_signals:
            table.add_row("[dim]暂无信号记录[/]", "", "", "", "")

        return Panel(table, title=f"📜 信号历史 (共{self.state.total_signals}条)", border_style="cyan")

    def _make_verification(self) -> Panel:
        """创建验证统计面板"""
        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        table.add_column("项目", style="cyan", width=14)
        table.add_column("值", justify="right")

        stats = self.state.verification_stats
        pending_count = len(self.state.pending_verifications)

        table.add_row("待验证信号", f"[yellow]{pending_count}[/]")
        table.add_row("", "")

        # 10分钟验证统计
        table.add_row("[bold]10分钟验证[/]", "")
        table.add_row("  已验证", str(stats.total_verified_10min))
        if stats.total_verified_10min > 0:
            acc_color = "green" if stats.accuracy_10min >= 0.6 else "yellow" if stats.accuracy_10min >= 0.4 else "red"
            table.add_row("  正确/错误", f"[green]{stats.correct_10min}[/]/[red]{stats.wrong_10min}[/]")
            table.add_row("  准确率", f"[{acc_color}]{stats.accuracy_10min:.1%}[/]")
        else:
            table.add_row("  准确率", "[dim]N/A[/]")

        table.add_row("", "")

        # 30分钟验证统计
        table.add_row("[bold]30分钟验证[/]", "")
        table.add_row("  已验证", str(stats.total_verified_30min))
        if stats.total_verified_30min > 0:
            acc_color = "green" if stats.accuracy_30min >= 0.6 else "yellow" if stats.accuracy_30min >= 0.4 else "red"
            table.add_row("  正确/错误", f"[green]{stats.correct_30min}[/]/[red]{stats.wrong_30min}[/]")
            table.add_row("  准确率", f"[{acc_color}]{stats.accuracy_30min:.1%}[/]")
        else:
            table.add_row("  准确率", "[dim]N/A[/]")

        return Panel(table, title="📊 信号验证统计", border_style="magenta")

    def _make_verification_history(self) -> Panel:
        """创建验证历史面板"""
        table = Table(show_header=True, box=box.SIMPLE, expand=True)
        table.add_column("时间", width=8)
        table.add_column("方向", width=4)
        table.add_column("入场价", width=10)
        table.add_column("10分", width=8)
        table.add_column("30分", width=8)

        # 显示待验证的信号
        for pv in self.state.pending_verifications[-5:]:
            time_str = pv.entry_time.strftime("%H:%M:%S")
            direction = "[green]买[/]" if pv.signal.direction == SignalDirection.BUY else "[red]卖[/]"
            entry = f"${pv.entry_price:,.0f}"

            # 10分钟结果
            if pv.verified_10min:
                if pv.result_10min == "correct":
                    r10 = f"[green]✓{pv.profit_10min:+.2f}%[/]"
                else:
                    r10 = f"[red]✗{pv.profit_10min:+.2f}%[/]"
            else:
                remaining = (pv.verify_10min_time - datetime.now()).total_seconds()
                if remaining > 0:
                    r10 = f"[yellow]{int(remaining)}s[/]"
                else:
                    r10 = "[yellow]验证中[/]"

            # 30分钟结果
            if pv.verified_30min:
                if pv.result_30min == "correct":
                    r30 = f"[green]✓{pv.profit_30min:+.2f}%[/]"
                else:
                    r30 = f"[red]✗{pv.profit_30min:+.2f}%[/]"
            else:
                remaining = (pv.verify_30min_time - datetime.now()).total_seconds()
                if remaining > 0:
                    r30 = f"[yellow]{int(remaining/60)}m{int(remaining%60)}s[/]"
                else:
                    r30 = "[yellow]验证中[/]"

            table.add_row(time_str, direction, entry, r10, r30)

        # 显示已完成验证的信号
        for pv in self.state.completed_verifications[-5:]:
            time_str = pv.entry_time.strftime("%H:%M:%S")
            direction = "[green]买[/]" if pv.signal.direction == SignalDirection.BUY else "[red]卖[/]"
            entry = f"${pv.entry_price:,.0f}"

            if pv.result_10min == "correct":
                r10 = f"[green]✓{pv.profit_10min:+.2f}%[/]"
            else:
                r10 = f"[red]✗{pv.profit_10min:+.2f}%[/]"

            if pv.result_30min == "correct":
                r30 = f"[green]✓{pv.profit_30min:+.2f}%[/]"
            else:
                r30 = f"[red]✗{pv.profit_30min:+.2f}%[/]"

            table.add_row(f"[dim]{time_str}[/]", direction, entry, r10, r30)

        if not self.state.pending_verifications and not self.state.completed_verifications:
            table.add_row("[dim]暂无验证记录[/]", "", "", "", "")

        return Panel(table, title="🔍 验证详情", border_style="magenta")

    def _make_footer(self) -> Panel:
        """创建底部面板"""
        stats = Text()
        stats.append("统计: ", style="bold")
        stats.append(f"总信号 {self.state.total_signals} | ", style="white")
        stats.append(f"买入 {self.state.buy_signals} ", style="green")
        stats.append(f"卖出 {self.state.sell_signals} ", style="red")

        # 添加验证准确率
        v_stats = self.state.verification_stats
        if v_stats.total_verified_10min > 0:
            stats.append(f" | 10分准确率: {v_stats.accuracy_10min:.1%}", style="cyan")
        if v_stats.total_verified_30min > 0:
            stats.append(f" | 30分准确率: {v_stats.accuracy_30min:.1%}", style="cyan")

        stats.append(" | 按 Ctrl+C 退出", style="dim")

        return Panel(stats, style="dim")

    def render(self) -> Layout:
        """渲染仪表盘"""
        self.layout["header"].update(self._make_header())
        self.layout["market_state"].update(self._make_market_state())
        self.layout["indicators"].update(self._make_indicators())
        self.layout["signal"].update(self._make_signal())
        self.layout["history"].update(self._make_history())
        self.layout["verification"].update(self._make_verification())
        self.layout["verification_history"].update(self._make_verification_history())
        self.layout["footer"].update(self._make_footer())

        return self.layout


class LiveDashboardSystem:
    """实时仪表盘系统"""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        primary_interval: str = "5m",
        confirmation_intervals: List[str] = None
    ):
        self.symbol = symbol.upper()
        self.primary_interval = primary_interval

        mtf_config = get_multi_timeframe_config()
        self.confirmation_intervals = confirmation_intervals or mtf_config.get(
            "confirmation_timeframes", ["15m", "1h"]
        )
        self.all_intervals = [primary_interval] + self.confirmation_intervals

        # 状态
        self.state = DashboardState(
            symbol=self.symbol,
            primary_interval=primary_interval,
            confirmation_intervals=self.confirmation_intervals,
            start_time=datetime.now()
        )

        # 初始化连接状态
        for interval in self.all_intervals:
            self.state.ws_connected[interval] = False
            self.state.kline_counts[interval] = 0

        # 缓冲区
        self.buffers: Dict[str, StreamingKlineBuffer] = {
            interval: StreamingKlineBuffer(max_closed=200)
            for interval in self.all_intervals
        }

        # 信号生成器和市场状态检测器
        self.signal_generator = SignalGenerator(
            symbol=self.symbol,
            primary_interval=self.primary_interval
        )
        self.state_detector = MarketStateDetector()

        # 仪表盘
        self.dashboard = RichDashboard(self.state)

        # 运行状态
        self.is_running = False

    async def fetch_historical_klines(self, interval: str, limit: int = 200) -> List[List]:
        """获取历史K线"""
        url = f"{BINANCE_API_URL}/fapi/v1/klines"
        params = {"symbol": self.symbol, "interval": interval, "limit": limit}

        connector = None
        if USE_PROXY and PROXY_URL:
            connector = ProxyConnector.from_url(PROXY_URL)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    return []
        except Exception:
            return []

    async def fetch_ticker(self) -> Dict[str, Any]:
        """获取24h行情"""
        url = f"{BINANCE_API_URL}/fapi/v1/ticker/24hr"
        params = {"symbol": self.symbol}

        connector = None
        if USE_PROXY and PROXY_URL:
            connector = ProxyConnector.from_url(PROXY_URL)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        except Exception:
            return {}

    async def initialize(self):
        """初始化数据"""
        # 获取历史K线
        tasks = [self.fetch_historical_klines(interval) for interval in self.all_intervals]
        results = await asyncio.gather(*tasks)

        current_time_ms = int(time.time() * 1000)

        for interval, klines in zip(self.all_intervals, results):
            buffer = self.buffers.get(interval)
            if buffer and klines:
                for kline in klines:
                    # kline[6] 是K线收盘时间，判断是否已收盘
                    close_time = int(kline[6])
                    is_closed = close_time < current_time_ms

                    buffer.update_from_ws({
                        't': kline[0], 'o': kline[1], 'h': kline[2],
                        'l': kline[3], 'c': kline[4], 'v': kline[5], 'x': is_closed
                    })
                self.state.kline_counts[interval] = len(buffer.get_candles())

        # 获取24h行情
        ticker = await self.fetch_ticker()
        if ticker:
            self.state.current_price = float(ticker.get('lastPrice', 0))
            self.state.price_change_24h = float(ticker.get('priceChangePercent', 0))
            self.state.high_24h = float(ticker.get('highPrice', 0))
            self.state.low_24h = float(ticker.get('lowPrice', 0))
            self.state.volume_24h = float(ticker.get('volume', 0))

        # 初始计算
        await self.update_analysis()

    async def connect_websocket(self, interval: str):
        """连接WebSocket"""
        stream_name = f"{self.symbol.lower()}@kline_{interval}"
        ws_url = f"{BINANCE_WS_URL}/ws/{stream_name}"

        retry_count = 0

        while self.is_running and retry_count < MAX_RETRIES:
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT
                ) as ws:
                    self.state.ws_connected[interval] = True
                    retry_count = 0

                    while self.is_running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            data = json.loads(message)
                            await self.process_kline(interval, data)
                        except asyncio.TimeoutError:
                            await ws.ping()
                        except websockets.ConnectionClosed:
                            break

            except Exception:
                retry_count += 1
                self.state.ws_connected[interval] = False
                await asyncio.sleep(5 * retry_count)

        self.state.ws_connected[interval] = False

    async def process_kline(self, interval: str, data: Dict[str, Any]):
        """处理K线数据"""
        kline_data = data.get('k', {})
        if not kline_data:
            return

        buffer = self.buffers.get(interval)
        if buffer:
            buffer.update_from_ws(kline_data)
            self.state.kline_counts[interval] = len(buffer.get_candles())

        # 更新价格
        if interval == self.primary_interval:
            self.state.current_price = float(kline_data.get('c', 0))
            self.state.last_update = datetime.now()
            # 实时更新分析（每次价格变化都重新计算，未收盘K线的当前价格作为收盘价）
            await self.update_analysis()

    async def update_analysis(self):
        """更新分析"""
        buffer = self.buffers.get(self.primary_interval)
        if not buffer:
            return

        price_data = buffer.get_price_arrays(include_current=True)
        if len(price_data["closes"]) < 60:
            return

        highs = price_data["highs"]
        lows = price_data["lows"]
        closes = price_data["closes"]
        volumes = price_data["volumes"]

        # 获取当前K线的时间戳（用于信号去重）
        current_kline_time = None
        if buffer.active_candle:
            current_kline_time = buffer.active_candle.timestamp
        elif buffer.closed_candles:
            current_kline_time = buffer.closed_candles[-1].timestamp

        # 市场状态
        state_result = self.state_detector.detect(highs, lows, closes, volumes)
        self.state.market_state = state_result.state
        self.state.market_state_confidence = state_result.confidence
        self.state.adx = state_result.adx
        self.state.plus_di = state_result.plus_di
        self.state.minus_di = state_result.minus_di
        self.state.trend_strength = state_result.trend_strength.value

        # 收集多周期数据（使用已收盘K线进行确认，更稳定）
        timeframe_data = {}
        for interval in self.confirmation_intervals:
            tf_buffer = self.buffers.get(interval)
            if tf_buffer:
                # 确认周期使用已收盘K线，避免确认结果不稳定
                tf_price = tf_buffer.get_price_arrays(include_current=False)
                if len(tf_price["closes"]) >= 30:
                    timeframe_data[interval] = {
                        "highs": tf_price["highs"],
                        "lows": tf_price["lows"],
                        "closes": tf_price["closes"],
                        "volumes": tf_price["volumes"]
                    }

        # 生成信号
        signal = self.signal_generator.generate(
            highs=highs, lows=lows, closes=closes, volumes=volumes,
            timeframe_data=timeframe_data if timeframe_data else None
        )

        # 更新指标数据
        self.state.rsi = signal.indicator_values.get('rsi')
        self.state.macd = signal.indicator_values.get('macd')
        self.state.macd_signal = signal.indicator_values.get('macd_signal')
        self.state.macd_histogram = signal.indicator_values.get('macd_histogram')
        self.state.ema5 = signal.indicator_values.get('ema5')
        self.state.ema20 = signal.indicator_values.get('ema20')
        self.state.ema60 = signal.indicator_values.get('ema60')
        self.state.bb_percent_b = signal.indicator_values.get('bb_percent_b')
        self.state.atr = signal.indicator_values.get('atr')
        self.state.volume_ratio = signal.indicator_values.get('volume_ratio')

        # 更新当前显示的信号
        self.state.current_signal = signal

        # 信号去重：只有当信号方向改变或K线时间改变时才记录新信号
        is_new_signal = False
        if signal.direction != SignalDirection.HOLD:
            # 检查是否是新信号：方向改变 或 新K线产生的信号
            if (self.state.last_signal_direction != signal.direction or
                self.state.last_signal_kline_time != current_kline_time):
                is_new_signal = True
                self.state.last_signal_direction = signal.direction
                self.state.last_signal_kline_time = current_kline_time
        else:
            # HOLD 信号重置状态，允许同一根K线再次产生信号
            self.state.last_signal_direction = None

        # 只有新信号才记录到历史和统计
        if is_new_signal:
            self.state.signal_history.append(signal)
            if len(self.state.signal_history) > 100:
                self.state.signal_history = self.state.signal_history[-100:]

            self.state.total_signals += 1
            if signal.direction == SignalDirection.BUY:
                self.state.buy_signals += 1
            else:
                self.state.sell_signals += 1

            # 添加到待验证列表
            self._add_pending_verification(signal)

    def _add_pending_verification(self, signal: TradingSignal):
        """添加待验证的信号"""
        from datetime import timedelta

        now = datetime.now()
        verification = PendingVerification(
            signal_id=str(uuid.uuid4())[:8],
            signal=signal,
            entry_price=signal.entry_price,
            entry_time=now,
            verify_10min_time=now + timedelta(minutes=10),
            verify_30min_time=now + timedelta(minutes=30),
        )
        self.state.pending_verifications.append(verification)

        # 限制待验证列表长度
        if len(self.state.pending_verifications) > 50:
            # 移除最旧的已完成验证的
            completed = [pv for pv in self.state.pending_verifications if pv.verified_30min]
            if completed:
                self.state.pending_verifications.remove(completed[0])

    def _verify_signals(self):
        """验证信号结果"""
        now = datetime.now()
        current_price = self.state.current_price

        if current_price <= 0:
            return

        to_remove = []

        for pv in self.state.pending_verifications:
            # 验证10分钟结果
            if not pv.verified_10min and now >= pv.verify_10min_time:
                pv.verified_10min = True
                pv.price_at_10min = current_price

                # 计算盈亏
                if pv.signal.direction == SignalDirection.BUY:
                    pv.profit_10min = (current_price - pv.entry_price) / pv.entry_price * 100
                    pv.result_10min = "correct" if current_price > pv.entry_price else "wrong"
                else:  # SELL
                    pv.profit_10min = (pv.entry_price - current_price) / pv.entry_price * 100
                    pv.result_10min = "correct" if current_price < pv.entry_price else "wrong"

                # 更新统计
                self.state.verification_stats.total_verified_10min += 1
                if pv.result_10min == "correct":
                    self.state.verification_stats.correct_10min += 1
                else:
                    self.state.verification_stats.wrong_10min += 1

            # 验证30分钟结果
            if not pv.verified_30min and now >= pv.verify_30min_time:
                pv.verified_30min = True
                pv.price_at_30min = current_price

                # 计算盈亏
                if pv.signal.direction == SignalDirection.BUY:
                    pv.profit_30min = (current_price - pv.entry_price) / pv.entry_price * 100
                    pv.result_30min = "correct" if current_price > pv.entry_price else "wrong"
                else:  # SELL
                    pv.profit_30min = (pv.entry_price - current_price) / pv.entry_price * 100
                    pv.result_30min = "correct" if current_price < pv.entry_price else "wrong"

                # 更新统计
                self.state.verification_stats.total_verified_30min += 1
                if pv.result_30min == "correct":
                    self.state.verification_stats.correct_30min += 1
                else:
                    self.state.verification_stats.wrong_30min += 1

            # 如果两个验证都完成，移到已完成列表
            if pv.verified_10min and pv.verified_30min:
                to_remove.append(pv)

        # 移动已完成的验证
        for pv in to_remove:
            self.state.pending_verifications.remove(pv)
            self.state.completed_verifications.append(pv)
            # 限制已完成列表长度
            if len(self.state.completed_verifications) > 100:
                self.state.completed_verifications = self.state.completed_verifications[-100:]

    async def run(self):
        """运行仪表盘"""
        self.is_running = True

        # 初始化
        console.print("[cyan]正在初始化...[/]")
        await self.initialize()

        # 启动WebSocket
        ws_tasks = [self.connect_websocket(interval) for interval in self.all_intervals]

        # 启动Rich Live显示
        with Live(self.dashboard.render(), console=console, refresh_per_second=2) as live:
            async def update_display():
                while self.is_running:
                    live.update(self.dashboard.render())
                    await asyncio.sleep(0.5)

            async def verification_loop():
                """定期验证信号"""
                while self.is_running:
                    self._verify_signals()
                    await asyncio.sleep(1)  # 每秒检查一次

            display_task = asyncio.create_task(update_display())
            verification_task = asyncio.create_task(verification_loop())

            try:
                await asyncio.gather(*ws_tasks)
            except asyncio.CancelledError:
                pass
            finally:
                display_task.cancel()
                verification_task.cancel()

    def stop(self):
        """停止系统"""
        self.is_running = False


async def main():
    parser = argparse.ArgumentParser(description='实时交易仪表盘')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='交易对')
    parser.add_argument('--interval', type=str, default='5m', help='主周期')
    parser.add_argument('--confirm', type=str, nargs='+', default=['15m', '1h'],
                        help='确认周期')

    args = parser.parse_args()

    system = LiveDashboardSystem(
        symbol=args.symbol,
        primary_interval=args.interval,
        confirmation_intervals=args.confirm
    )

    try:
        await system.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]正在停止...[/]")
        system.stop()


if __name__ == "__main__":
    asyncio.run(main())
