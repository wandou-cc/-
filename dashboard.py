from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich import box
from rich.align import Align
from rich.console import Console, RenderableType, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class DashboardMeta:
    symbol: str
    interval: str
    contract_type: str
    min_signals: int
    ws_url: str = ""
    connection: str = "初始化"


@dataclass
class DashboardState:
    meta: DashboardMeta
    kline: Optional[Dict[str, Any]] = None
    suggestion: Optional[Dict[str, Any]] = None
    indicators: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    heartbeat: Dict[str, Any] = field(default_factory=lambda: {"count": 0, "last": "-"})  # type: ignore[arg-type]
    latest_signal: Optional[Dict[str, Any]] = None
    active_signals: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, str]] = field(default_factory=list)


class ConsoleDashboard:
    """Rich-based streaming dashboard for console trading systems."""

    def __init__(
        self,
        symbol: str,
        interval: str,
        contract_type: str,
        min_signals: int,
        screen: bool = False,
        refresh_interval: float = 0.25,
    ) -> None:
        meta = DashboardMeta(
            symbol=symbol.upper(),
            interval=interval,
            contract_type=contract_type.upper(),
            min_signals=min_signals,
        )
        self.state = DashboardState(meta=meta)
        self.console = Console()
        self.live: Optional[Live] = None
        self.screen = screen
        self.refresh_interval = refresh_interval
        self._last_render = 0.0

    # ------------------------------------------------------------------ #
    # Public lifecycle helpers
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        if self.live:
            return
        self.live = Live(
            self._render_root(),
            console=self.console,
            refresh_per_second=int(1 / self.refresh_interval) if self.refresh_interval > 0 else 4,
            screen=self.screen,
        )
        self.live.start()

    def stop(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None

    # ------------------------------------------------------------------ #
    # State update helpers
    # ------------------------------------------------------------------ #
    def update_meta(self, **meta_fields: Any) -> None:
        for key, value in meta_fields.items():
            if hasattr(self.state.meta, key):
                setattr(self.state.meta, key, value)
        self._refresh()

    def update_market(self, kline: Optional[Dict[str, Any]] = None, suggestion: Optional[Dict[str, Any]] = None) -> None:
        if kline is not None:
            self.state.kline = kline
        if suggestion is not None:
            self.state.suggestion = suggestion
        self._refresh()

    def update_indicators(self, indicators: Dict[str, Any], suggestion: Optional[Dict[str, Any]] = None) -> None:
        self.state.indicators = indicators
        if suggestion is not None:
            self.state.suggestion = suggestion
        self._refresh()

    def update_stats(self, stats: Dict[str, Any]) -> None:
        self.state.stats = stats
        self._refresh()

    def update_signals(
        self,
        latest_signal: Optional[Dict[str, Any]],
        active_signals: List[Dict[str, Any]],
    ) -> None:
        self.state.latest_signal = latest_signal
        self.state.active_signals = active_signals
        self._refresh()

    def update_heartbeat(self, message_count: int) -> None:
        self.state.heartbeat = {
            "count": message_count,
            "last": datetime.now().strftime("%H:%M:%S"),
        }
        self._refresh()

    def push_alert(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.state.alerts.append({"message": message, "level": level, "time": timestamp})
        self.state.alerts = self.state.alerts[-5:]
        self._refresh(force=True)

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #
    def _refresh(self, force: bool = False) -> None:
        now = time.time()
        if not self.live:
            return
        if not force and now - self._last_render < self.refresh_interval:
            return
        self.live.update(self._render_root())
        self._last_render = now

    def _render_root(self) -> RenderableType:
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=4),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=8),
        )
        layout["body"].split_row(
            Layout(name="market", ratio=3),
            Layout(name="indicators", ratio=4),
            Layout(name="signals", ratio=3),
        )

        layout["header"].update(self._render_header())
        layout["market"].update(self._render_market_panel())
        layout["indicators"].update(self._render_indicator_panel())
        layout["signals"].update(self._render_signal_panel())
        layout["footer"].update(self._render_footer())
        return layout

    def _render_header(self) -> Panel:
        meta = self.state.meta
        heartbeat = self.state.heartbeat
        status_style = "bold green"
        if "断开" in meta.connection or "失败" in meta.connection:
            status_style = "bold red"
        elif "连接" not in meta.connection and "成功" not in meta.connection:
            status_style = "bold yellow"

        table = Table.grid(expand=True)
        table.add_column(justify="left")
        table.add_column(justify="center")
        table.add_column(justify="right")

        table.add_row(
            f"[bold cyan]{meta.symbol}[/] · {meta.interval}",
            f"合约: {meta.contract_type}",
            f"最小联动指标: {meta.min_signals}",
        )
        table.add_row(
            Text(f"状态: {meta.connection}", style=status_style),
            f"消息数: {heartbeat.get('count', 0)}",
            f"心跳: {heartbeat.get('last', '-')}",
        )
        table.add_row(
            f"WS: {meta.ws_url or '-'}",
            "",
            "",
        )

        return Panel(table, border_style="cyan", title="系统状态", padding=(0, 1))

    def _render_market_panel(self) -> Panel:
        kline = self.state.kline
        suggestion = self.state.suggestion
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=1)

        if kline:
            status = "[已收]" if kline.get("is_closed") else "[实时]"
            table.add_row(
                f"{status} {kline.get('datetime', '-')}",
                f"成交量: {kline.get('volume', 0):.2f}",
            )
            table.add_row(
                f"开 {kline.get('open', 0):.2f} | 高 {kline.get('high', 0):.2f}",
                f"低 {kline.get('low', 0):.2f} | 收 {kline.get('close', 0):.2f}",
            )
        else:
            table.add_row("等待K线数据...", "")

        suggestion_panel = self._render_suggestion_panel(suggestion)
        container = Table.grid(expand=True)
        container.add_row(table)
        container.add_row(suggestion_panel)
        return Panel(container, border_style="magenta", title="行情 & 建议", padding=(0, 1))

    def _render_suggestion_panel(self, suggestion: Optional[Dict[str, Any]]) -> RenderableType:
        if not suggestion:
            return Panel(
                Align.center(
                    Text("指标累积中，暂无法生成建议", style="dim italic")
                ),
                border_style="dim",
                padding=(1, 2)
            )

        votes = suggestion.get("votes", {})
        bias = suggestion.get("bias", "NEUTRAL")
        color_map = {
            "LONG": "green",
            "SHORT": "red",
            "NEUTRAL": "yellow",
        }
        color = color_map.get(bias, "cyan")
        confidence = suggestion.get("confidence", 0.0)
        summary = suggestion.get("summary", "")
        action = suggestion.get("action", "")

        # 创建置信度进度条
        confidence_bar = self._create_confidence_bar(confidence, color)

        # 主建议区域
        main_table = Table.grid(expand=True)
        main_table.add_column(ratio=3)
        main_table.add_column(ratio=2, justify="right")

        # 大号方向指示
        direction_icon = {
            "LONG": "⬆",
            "SHORT": "⬇",
            "NEUTRAL": "⬌"
        }.get(bias, "•")

        main_table.add_row(
            Text(f"{direction_icon} {bias}", style=f"bold {color} on {color}0", justify="center"),
            f"置信度\n{confidence_bar}"
        )
        main_table.add_row(
            Text(action, style=f"bold {color}"),
            ""
        )
        main_table.add_row(
            Text(summary, style="italic"),
            f"[dim]{suggestion.get('updated_at', '-')}[/]"
        )

        # 投票统计
        buy_count = votes.get('buy', 0)
        sell_count = votes.get('sell', 0)
        wait_count = votes.get('wait', 0)
        total = buy_count + sell_count + wait_count

        vote_table = Table.grid(expand=True, padding=0)
        vote_table.add_column(justify="center")
        vote_table.add_column(justify="center")
        vote_table.add_column(justify="center")

        vote_table.add_row(
            f"[green]买入 {buy_count}[/]",
            f"[red]卖出 {sell_count}[/]",
            f"[yellow]等待 {wait_count}[/]"
        )

        # 投票可视化
        if total > 0:
            buy_bar = int(buy_count / total * 15)
            sell_bar = int(sell_count / total * 15)
            wait_bar = 15 - buy_bar - sell_bar
            vote_visual = f"[green]{'█' * buy_bar}[/][red]{'█' * sell_bar}[/][yellow]{'█' * wait_bar}[/]"
        else:
            vote_visual = "[dim]" + "░" * 15 + "[/]"

        vote_table.add_row(vote_visual, "", "")

        # 详细指标投票
        details = suggestion.get("details", {})
        detail_table = Table(box=box.SIMPLE, expand=True, show_header=False, padding=0)
        detail_table.add_column(width=8, style="bold")
        detail_table.add_column()

        if details.get('buy'):
            detail_table.add_row("[green]看涨[/]", ", ".join(details['buy']))
        if details.get('sell'):
            detail_table.add_row("[red]看跌[/]", ", ".join(details['sell']))
        if details.get('wait'):
            detail_table.add_row("[yellow]观望[/]", ", ".join(details['wait']))

        # 组合面板
        wrapper = Table.grid(expand=True)
        wrapper.add_row(main_table)
        wrapper.add_row("")
        wrapper.add_row(vote_table)
        wrapper.add_row("")
        wrapper.add_row(detail_table)

        return Panel(wrapper, border_style=color, title="[bold]交易建议[/]", padding=(0, 1))

    def _create_confidence_bar(self, confidence: float, color: str) -> str:
        """创建置信度进度条"""
        filled = int(confidence * 10)
        empty = 10 - filled
        percentage = f"{confidence*100:.0f}%"
        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"
        return f"{bar} {percentage}"

    def _render_indicator_panel(self) -> Panel:
        snapshot = self.state.indicators
        table = Table(box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("指标", style="cyan", no_wrap=True, width=8)
        table.add_column("数值", justify="left", ratio=2)
        table.add_column("信号", justify="center", width=12)

        if not snapshot:
            table.add_row("-", "等待数据...", "-")
        else:
            # MACD
            if macd := snapshot.get("macd"):
                signal_type = macd.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                histogram = macd.get('histogram', 0)
                hist_bar = self._create_histogram_bar(histogram)
                table.add_row(
                    "MACD",
                    f"M:{macd.get('macd', 0):.2f} S:{macd.get('signal', 0):.2f}\n{hist_bar}",
                    Text(signal_type, style=signal_style),
                )

            # RSI
            if rsi := snapshot.get("rsi"):
                rsi_val = rsi.get('rsi', 0)
                signal_type = rsi.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                rsi_bar = self._create_rsi_bar(rsi_val)
                table.add_row(
                    "RSI",
                    f"{rsi_val:.1f}\n{rsi_bar}",
                    Text(signal_type, style=signal_style)
                )

            # 布林带
            if bb := snapshot.get("bb"):
                signal_type = bb.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                percent_b = bb.get('percent_b', 0)
                bb_bar = self._create_percent_b_bar(percent_b)
                table.add_row(
                    "BOLL",
                    f"上:{bb.get('upper', 0):.2f} 中:{bb.get('middle', 0):.2f}\n下:{bb.get('lower', 0):.2f} {bb_bar}",
                    Text(signal_type, style=signal_style),
                )

            # KDJ
            if kdj := snapshot.get("kdj"):
                signal_type = kdj.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                k_val = kdj.get('k', 0)
                d_val = kdj.get('d', 0)
                j_val = kdj.get('j', 0)
                kdj_visual = self._create_kdj_visual(k_val, d_val, j_val)
                table.add_row(
                    "KDJ",
                    f"K:{k_val:.1f} D:{d_val:.1f} J:{j_val:.1f}\n{kdj_visual}",
                    Text(signal_type, style=signal_style),
                )

            # EMA
            if ema := snapshot.get("ema"):
                signal_type = ema.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                trend = ema.get('trend', '-')
                trend_arrow = self._get_trend_arrow(trend)
                table.add_row(
                    "EMA",
                    f"超快:{ema.get('ultra_fast', 0):.2f} 快:{ema.get('fast', 0):.2f}\n中:{ema.get('medium', 0):.2f} 慢:{ema.get('slow', 0):.2f}",
                    f"{Text(signal_type, style=signal_style)}\n{trend_arrow}",
                )

            # CCI（新增）
            if cci := snapshot.get("cci"):
                signal_type = cci.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                cci_val = cci.get('cci', 0)
                cci_visual = self._create_cci_visual(cci_val)
                table.add_row(
                    "CCI",
                    f"{cci_val:.1f}\n{cci_visual}",
                    Text(signal_type, style=signal_style),
                )

            # ATR（新增）
            if atr := snapshot.get("atr"):
                signal_type = atr.get("signal_type") or "WAIT"
                signal_style = self._get_signal_style(signal_type)
                atr_val = atr.get('atr', 0)
                atr_visual = self._create_atr_visual(atr_val)
                table.add_row(
                    "ATR",
                    f"{atr_val:.2f}\n{atr_visual}",
                    Text(signal_type, style=signal_style),
                )

          
        return Panel(table, title="核心指标", border_style="blue", padding=(0, 1))

    def _get_signal_style(self, signal: str) -> str:
        """获取信号对应的样式"""
        if signal == "BUY":
            return "bold green"
        elif signal == "SELL":
            return "bold red"
        else:
            return "yellow"

    def _create_histogram_bar(self, value: float, width: int = 20) -> str:
        """创建MACD柱状图可视化"""
        max_val = 5.0
        normalized = max(-1.0, min(1.0, value / max_val))
        bar_len = int(abs(normalized) * width / 2)

        if value > 0:
            return f"[green]{'█' * bar_len}[/]"
        elif value < 0:
            return f"[red]{'█' * bar_len}[/]"
        else:
            return "[dim]│[/]"

    def _create_rsi_bar(self, rsi: float) -> str:
        """创建RSI可视化条"""
        if rsi >= 70:
            color = "red"
            label = "超买"
        elif rsi <= 30:
            color = "green"
            label = "超卖"
        else:
            color = "yellow"
            label = "正常"

        filled = int(rsi / 5)
        empty = 20 - filled
        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/] [{color}]{label}[/]"

    def _create_percent_b_bar(self, percent_b: Optional[float]) -> str:
        """创建%B可视化"""
        if percent_b is None:
            return ""

        if percent_b > 1:
            return "[red]▲上轨外[/]"
        elif percent_b < 0:
            return "[green]▼下轨外[/]"
        else:
            filled = int(percent_b * 10)
            empty = 10 - filled
            return f"[cyan]{'█' * filled}{'░' * empty}[/]"

    def _create_kdj_visual(self, k: float, d: float, j: float) -> str:
        """创建KDJ可视化"""
        if k >= 80:
            k_status = "[red]超买[/]"
        elif k <= 20:
            k_status = "[green]超卖[/]"
        else:
            k_status = "[yellow]正常[/]"

        if k > d:
            cross = "[green]K>D 金叉区[/]"
        else:
            cross = "[red]K<D 死叉区[/]"

        return f"{k_status} {cross}"

    def _create_cci_visual(self, cci: float) -> str:
        """创建CCI可视化"""
        if cci > 200:
            color = "bold red"
            label = "极度超买"
        elif cci > 100:
            color = "red"
            label = "超买"
        elif cci > 0:
            color = "green"
            label = "看涨"
        elif cci > -100:
            color = "yellow"
            label = "看跌"
        elif cci > -200:
            color = "cyan"
            label = "超卖"
        else:
            color = "bold cyan"
            label = "极度超卖"

        # CCI范围通常在-300到+300之间，以0为中心
        # 将其映射到0-20的可视化条
        normalized = max(-300, min(300, cci))
        position = int((normalized + 300) / 30)  # 映射到0-20

        # 创建位置指示器
        bar = ['░'] * 20
        bar[position] = '█'
        bar_str = ''.join(bar)

        return f"[{color}]{bar_str}[/] [{color}]{label}[/]"

    def _create_atr_visual(self, atr: float) -> str:
        """创建ATR波动率可视化"""
        # ATR的可视化基于波动率水平
        # 这里假设ATR值通常在0-100之间（根据标的物不同会有差异）
        # 用条形图表示波动强度

        # 将ATR映射到0-20的可视化条
        # 假设ATR > 50为高波动，< 20为低波动
        if atr > 50:
            color = "red"
            label = "高波动"
            level = min(20, int(atr / 5))
        elif atr > 20:
            color = "yellow"
            label = "中波动"
            level = min(20, int(atr / 3))
        else:
            color = "green"
            label = "低波动"
            level = min(20, int(atr / 2))

        filled = level
        empty = 20 - filled
        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/] [{color}]{label}[/]"

    def _get_trend_arrow(self, trend: str) -> str:
        """获取趋势箭头"""
        if "强" in trend and "上涨" in trend:
            return "[bold green]↑↑↑[/]"
        elif "上涨" in trend:
            return "[green]↑↑[/]"
        elif "强" in trend and "下跌" in trend:
            return "[bold red]↓↓↓[/]"
        elif "下跌" in trend:
            return "[red]↓↓[/]"
        elif "震荡" in trend:
            return "[yellow]→[/]"
        else:
            return "[dim]-[/]"

    def _render_signal_panel(self) -> Panel:
        latest = self.state.latest_signal
        active = self.state.active_signals

        signal_table = Table.grid(expand=True)
        signal_table.add_column()

        if latest:
            signal_table.add_row(self._render_latest_signal(latest))
        else:
            signal_table.add_row("暂无最新信号")

        if active:
            cards = [self._render_active_signal_card(card) for card in active]
            cards_table = Table.grid(expand=True)
            cards_table.add_row(*cards)
            signal_table.add_row(Align.left(cards_table))
        else:
            signal_table.add_row("无待验证信号")

        return Panel(signal_table, title="信号跟踪", border_style="green", padding=(0, 1))

    def _render_latest_signal(self, signal: Dict[str, Any]) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(justify="left")
        table.add_column(justify="right")
        table.add_row(
            Text(f"#{signal.get('id')} {signal.get('type')} {signal.get('direction')}", style="bold green"),
            f"入场: {signal.get('entry_price', 0):.2f}",
        )
        table.add_row(f"时间: {signal.get('time', '-')}", f"状态: {signal.get('status', '-')}")
        reasons = signal.get("reasons", [])
        if reasons:
            table.add_row("理由:", "; ".join(reasons))

        progress = signal.get("progress", [])
        progress_table = Table(box=box.MINIMAL_DOUBLE_HEAD, expand=True)
        progress_table.add_column("周期", justify="center")
        progress_table.add_column("预测", justify="center")
        progress_table.add_column("实际", justify="center")
        progress_table.add_column("结果", justify="center")

        for item in progress:
            style = "yellow"
            if item.get("result") == "命中":
                style = "green"
            elif item.get("result") == "偏离":
                style = "red"
            progress_table.add_row(
                item.get("label", "-"),
                item.get("predicted", "-"),
                item.get("actual", "-") or "-",
                Text(item.get("result", "等待"), style=style),
            )

        wrapper = Table.grid()
        wrapper.add_row(table)
        wrapper.add_row(progress_table)
        return Panel(wrapper, border_style="green")

    def _render_active_signal_card(self, signal: Dict[str, Any]) -> Panel:
        status = signal.get("status", "-")
        style = "green" if "完成" in status else "yellow"
        body = (
            f"{signal.get('type')} · {signal.get('direction')}\n"
            f"价: {signal.get('entry_price', 0):.2f}\n"
            f"进度: {status}"
        )
        return Panel(body, title=f"#{signal.get('id')}", border_style=style, padding=(0, 1), width=26)

    def _render_footer(self) -> Panel:
        stats = self.state.stats
        alerts = self.state.alerts
        table = Table.grid(expand=True)
        table.add_column(ratio=2)
        table.add_column(ratio=3)
        table.add_row(self._render_stats_table(stats), self._render_alerts(alerts))
        return Panel(table, border_style="white", title="统计 & 事件", padding=(0, 1))

    def _render_stats_table(self, stats: Dict[str, Any]) -> Panel:
        if not stats:
            return Panel("统计累积中...", border_style="white")
        accuracy = stats.get("accuracy", {})
        stat_table = Table(box=box.SIMPLE, expand=True)
        stat_table.add_column("维度", justify="center")
        stat_table.add_column("命中率", justify="center")
        stat_table.add_column("正确/验证", justify="center")
        for key, label in (("10m", "10分钟"), ("30m", "30分钟"), ("1h", "1小时")):
            data = accuracy.get(key, {"correct": 0, "checked": 0})
            checked = data.get("checked", 0)
            correct = data.get("correct", 0)
            ratio = (correct / checked * 100) if checked else 0.0
            stat_table.add_row(label, f"{ratio:.1f}%", f"{correct}/{checked}")

        summary = Table.grid()
        summary.add_row(
            f"总信号: {stats.get('total', 0)} | 待验证: {stats.get('active', 0)} | 已完成: {stats.get('completed', 0)}"
        )
        wrapper = Table.grid()
        wrapper.add_row(stat_table)
        wrapper.add_row(summary)
        return Panel(wrapper, border_style="white")

    def _render_alerts(self, alerts: List[Dict[str, str]]) -> Panel:
        if not alerts:
            return Panel("暂无事件推送", border_style="white")
        rows = []
        for alert in alerts:
            level = alert.get("level", "info")
            color = {
                "info": "cyan",
                "success": "green",
                "warning": "yellow",
                "error": "red",
            }.get(level, "cyan")
            rows.append(Text(f"{alert.get('time', '--')} {alert.get('message', '')}", style=color))
        return Panel(Align.left(Group(*rows)), border_style="white")
