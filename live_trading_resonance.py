"""
实时交易系统（共振策略版本） - Binance WebSocket
基于多指标共振策略，预测价格走势

数据流：
1. REST API 获取历史K线 -> kline_history (deque)
2. WebSocket 推送实时K线 -> 更新 kline_history
3. 每次推送调用 strategy.calculate() 计算指标
4. K线收盘时检查是否产生信号
"""

import asyncio
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

import websockets

from indicators import (
    MACDIndicator,
    RSIIndicator,
    BollingerBandsIndicator,
    KDJIndicator,
    EMAFourLineSystem,
    CCIIndicator,
    ATRIndicator,
)
from resonance_strategy import ResonanceStrategy, SignalType, ResonanceScore
from config import (
    BINANCE_WS_URL,
    USE_PROXY,
    PROXY_URL,
    REQUEST_TIMEOUT,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
    WS_CLOSE_TIMEOUT,
    MAX_RETRIES,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    HEARTBEAT_INTERVAL,
    MACD_PARAMS,
    RSI_PARAMS,
    BB_PARAMS,
    KDJ_PARAMS,
    EMA_PARAMS,
    CCI_PARAMS,
    ATR_PARAMS,
    RESONANCE_PARAMS,
    INDICATOR_SWITCHES,
    get_min_resonance,
)
from dashboard import ConsoleDashboard


@dataclass
class KlineData:
    """K线数据"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False


@dataclass
class ResonanceTradeSignal:
    """共振交易信号"""
    signal_id: str
    timestamp: int
    datetime_str: str
    signal_type: SignalType
    entry_price: float
    total_score: float
    confidence: float
    resonance_count: int
    trend_aligned: bool
    reasons: List[str] = field(default_factory=list)
    score_details: Dict = field(default_factory=dict)
    indicators: Dict = field(default_factory=dict)

    # 预测和验证
    predicted_direction: str = "HIGHER"  # HIGHER/LOWER
    check_times: Dict[str, int] = field(default_factory=dict)  # {"10min": ts, "30min": ts, "1hour": ts}
    results: Dict[str, Dict] = field(default_factory=dict)  # {"10min": {"price": x, "result": "HIGHER", "checked": True}}


class IndicatorCalculator:
    """指标计算器 - 纯计算，无状态管理"""

    def __init__(self):
        switches = INDICATOR_SWITCHES

        # 初始化启用的指标
        self.macd = MACDIndicator(
            MACD_PARAMS['fast_period'],
            MACD_PARAMS['slow_period'],
            MACD_PARAMS['signal_period']
        ) if switches['use_macd'] else None

        self.rsi = RSIIndicator(RSI_PARAMS['period']) if switches['use_rsi'] else None
        self.bb = BollingerBandsIndicator(BB_PARAMS['period'], BB_PARAMS['std_dev']) if switches['use_boll'] else None
        self.kdj = KDJIndicator(KDJ_PARAMS['period'], KDJ_PARAMS['signal']) if switches['use_kdj'] else None
        self.ema = EMAFourLineSystem(
            EMA_PARAMS['ultra_fast'],
            EMA_PARAMS['fast'],
            EMA_PARAMS['medium'],
            EMA_PARAMS['slow']
        ) if switches['use_ema'] else None
        self.cci = CCIIndicator(CCI_PARAMS['period']) if switches['use_cci'] else None
        self.atr = ATRIndicator(ATR_PARAMS['period']) if switches['use_atr'] else None

        # 记录启用的指标
        self.enabled = {k.replace('use_', '').upper(): v for k, v in switches.items() if k.startswith('use_')}

    def calculate(self, closes: List[float], highs: List[float], lows: List[float]) -> Dict[str, Any]:
        """计算所有启用的指标，返回结果字典"""
        result = {}

        if self.macd:
            r = self.macd.calculate(closes)
            result['macd'] = {'macd_line': r['macd_line'], 'signal_line': r['signal_line'], 'histogram': r['histogram']}

        if self.rsi:
            r = self.rsi.calculate(closes)
            result['rsi'] = {'rsi': r['rsi']}

        if self.bb:
            r = self.bb.calculate(closes)
            result['bb'] = {'upper_band': r['upper_band'], 'middle_band': r['middle_band'],
                           'lower_band': r['lower_band'], 'percent_b': r['percent_b']}

        if self.kdj:
            r = self.kdj.calculate(highs, lows, closes)
            result['kdj'] = {'k': r['k'], 'd': r['d'], 'j': r['j']}

        if self.ema:
            r = self.ema.calculate(closes)
            result['ema'] = {'ema_ultra_fast': r['ema_ultra_fast'], 'ema_fast': r['ema_fast'],
                           'ema_medium': r['ema_medium'], 'ema_slow': r['ema_slow']}

        if self.cci:
            r = self.cci.calculate(highs, lows, closes)
            result['cci'] = {'cci': r['cci']}

        if self.atr:
            r = self.atr.calculate(highs, lows, closes)
            result['atr'] = {'atr': r['atr']}

        return result


class ResonanceStrategyManager:
    """共振策略管理器"""

    def __init__(self):
        switches = INDICATOR_SWITCHES
        min_resonance = RESONANCE_PARAMS['min_resonance'] or get_min_resonance()
        min_score = RESONANCE_PARAMS['min_score']

        self.calculator = IndicatorCalculator()
        self.resonance = ResonanceStrategy(
            min_resonance=min_resonance,
            min_score=min_score,
            use_trend_filter=True,
            use_momentum_filter=True,
            use_volatility_filter=True,
            use_macd=switches['use_macd'],
            use_rsi=switches['use_rsi'],
            use_kdj=switches['use_kdj'],
            use_boll=switches['use_boll'],
            use_ema=switches['use_ema'],
            use_cci=switches['use_cci'],
            use_atr=switches['use_atr'],
        )

        # 缓存上一根K线的指标值
        self._prev_values: Dict[str, Any] = {}
        # 缓存最新计算结果
        self._cached_indicators: Dict[str, Any] = {}
        self._cached_score: Optional[ResonanceScore] = None
        self._indicator_signals: Dict[str, str] = {}

    def calculate(self, klines: List[KlineData], current_kline: KlineData) -> Optional[ResonanceScore]:
        """
        计算指标和共振得分

        Args:
            klines: 已收盘的K线历史
            current_kline: 当前K线（可能未收盘）

        Returns:
            共振得分，如果数据不足返回 None
        """
        # 合并历史和当前K线
        all_klines = list(klines) + [current_kline]

        closes = [k.close for k in all_klines]
        highs = [k.high for k in all_klines]
        lows = [k.low for k in all_klines]

        # 计算指标
        indicators = self.calculator.calculate(closes, highs, lows)
        self._cached_indicators = indicators

        # 检查是否有足够数据
        if not self._has_sufficient_data(indicators):
            return None

        # 计算共振得分
        score = self.resonance.calculate_resonance(
            rsi=indicators.get('rsi', {}).get('rsi'),
            previous_rsi=self._prev_values.get('rsi'),
            kdj_k=indicators.get('kdj', {}).get('k'),
            kdj_d=indicators.get('kdj', {}).get('d'),
            kdj_j=indicators.get('kdj', {}).get('j'),
            previous_k=self._prev_values.get('k'),
            previous_d=self._prev_values.get('d'),
            macd=indicators.get('macd', {}).get('macd_line'),
            macd_signal=indicators.get('macd', {}).get('signal_line'),
            macd_histogram=indicators.get('macd', {}).get('histogram'),
            previous_macd=self._prev_values.get('macd'),
            previous_macd_signal=self._prev_values.get('macd_signal'),
            ema_ultra_fast=indicators.get('ema', {}).get('ema_ultra_fast'),
            ema_fast=indicators.get('ema', {}).get('ema_fast'),
            ema_medium=indicators.get('ema', {}).get('ema_medium'),
            ema_slow=indicators.get('ema', {}).get('ema_slow'),
            bb_upper=indicators.get('bb', {}).get('upper_band'),
            bb_middle=indicators.get('bb', {}).get('middle_band'),
            bb_lower=indicators.get('bb', {}).get('lower_band'),
            bb_percent_b=indicators.get('bb', {}).get('percent_b'),
            cci=indicators.get('cci', {}).get('cci'),
            previous_cci=self._prev_values.get('cci'),
            atr=indicators.get('atr', {}).get('atr'),
            previous_atr=self._prev_values.get('atr'),
            current_price=current_kline.close,
            previous_price=self._prev_values.get('price'),
            high=current_kline.high,
            low=current_kline.low
        )

        self._cached_score = score
        self._update_indicator_signals(score)

        # K线收盘时更新历史值
        if current_kline.is_closed:
            self._prev_values = {
                'rsi': indicators.get('rsi', {}).get('rsi'),
                'k': indicators.get('kdj', {}).get('k'),
                'd': indicators.get('kdj', {}).get('d'),
                'macd': indicators.get('macd', {}).get('macd_line'),
                'macd_signal': indicators.get('macd', {}).get('signal_line'),
                'cci': indicators.get('cci', {}).get('cci'),
                'atr': indicators.get('atr', {}).get('atr'),
                'price': current_kline.close
            }

        return score

    def _has_sufficient_data(self, indicators: Dict) -> bool:
        """检查是否有足够的指标数据"""
        for key, values in indicators.items():
            if isinstance(values, dict):
                for v in values.values():
                    if v is not None:
                        return True
        return False

    def _update_indicator_signals(self, score: ResonanceScore):
        """从共振得分中提取各指标信号"""
        self._indicator_signals = {}
        for indicator, detail in score.details.items():
            if not isinstance(detail, dict):
                continue
            if indicator == 'trend':
                direction = detail.get('direction', 'NEUTRAL')
                self._indicator_signals['EMA'] = 'BUY' if direction == 'BULLISH' else 'SELL' if direction == 'BEARISH' else 'WAIT'
            elif indicator in ['RSI', 'KDJ', 'MACD', 'BOLL', 'CCI', 'ATR']:
                signal = detail.get('signal', 'NEUTRAL')
                self._indicator_signals[indicator] = 'BUY' if signal == 'BUY' else 'SELL' if signal == 'SELL' else 'WAIT'

    def get_snapshot(self) -> Dict[str, Any]:
        """获取当前指标快照（用于 dashboard 显示）"""
        snapshot = {}
        ind = self._cached_indicators

        if 'macd' in ind and ind['macd'].get('macd_line') is not None:
            snapshot['macd'] = {
                'macd': ind['macd']['macd_line'],
                'signal': ind['macd']['signal_line'],
                'histogram': ind['macd']['histogram'],
                'signal_type': self._indicator_signals.get('MACD', 'WAIT')
            }

        if 'rsi' in ind and ind['rsi'].get('rsi') is not None:
            snapshot['rsi'] = {
                'rsi': ind['rsi']['rsi'],
                'signal_type': self._indicator_signals.get('RSI', 'WAIT')
            }

        if 'bb' in ind and ind['bb'].get('middle_band') is not None:
            snapshot['bb'] = {
                'upper': ind['bb']['upper_band'],
                'middle': ind['bb']['middle_band'],
                'lower': ind['bb']['lower_band'],
                'percent_b': ind['bb']['percent_b'],
                'signal_type': self._indicator_signals.get('BOLL', 'WAIT')
            }

        if 'kdj' in ind and ind['kdj'].get('k') is not None:
            snapshot['kdj'] = {
                'k': ind['kdj']['k'],
                'd': ind['kdj']['d'],
                'j': ind['kdj']['j'],
                'signal_type': self._indicator_signals.get('KDJ', 'WAIT')
            }

        if 'ema' in ind and ind['ema'].get('ema_slow') is not None:
            ema = ind['ema']
            trend = 'UP' if ema['ema_fast'] > ema['ema_slow'] else 'DOWN' if ema['ema_fast'] < ema['ema_slow'] else 'NEUTRAL'
            snapshot['ema'] = {
                'ultra_fast': ema['ema_ultra_fast'],
                'fast': ema['ema_fast'],
                'medium': ema['ema_medium'],
                'slow': ema['ema_slow'],
                'signal_type': self._indicator_signals.get('EMA', 'WAIT'),
                'trend': trend
            }

        if 'cci' in ind and ind['cci'].get('cci') is not None:
            snapshot['cci'] = {
                'cci': ind['cci']['cci'],
                'signal_type': self._indicator_signals.get('CCI', 'WAIT')
            }

        if 'atr' in ind and ind['atr'].get('atr') is not None:
            snapshot['atr'] = {
                'atr': ind['atr']['atr'],
                'signal_type': self._indicator_signals.get('ATR', 'WAIT')
            }

        if self._cached_score:
            snapshot['resonance'] = {
                'total_score': self._cached_score.strength,
                'confidence': self._cached_score.confidence,
                'resonance_count': self._cached_score.resonance_count,
                'signal': self._cached_score.signal_type.value,
                'trend_aligned': self._cached_score.trend_aligned
            }

        return snapshot

    @property
    def min_score(self) -> float:
        return self.resonance.min_score

    @property
    def min_resonance(self) -> int:
        return self.resonance.min_resonance


class BinanceResonanceLiveTradingSystem:
    """Binance 实时交易系统"""

    def __init__(self,
                 symbol: str = None,
                 interval: str = None,
                 contract_type: str = None,
                 trade_log_file: str = "trade_signals_resonance.log"):

        self.symbol = (symbol or DEFAULT_SYMBOL).lower()
        self.interval = interval or DEFAULT_INTERVAL
        self.contract_type = (contract_type or DEFAULT_CONTRACT_TYPE).lower()
        self.trade_log_file = trade_log_file

        # 策略
        self.strategy = ResonanceStrategyManager()

        # WebSocket 配置
        ws_base = BINANCE_WS_URL.rstrip('/')
        stream = f"{self.symbol}_{self.contract_type}@continuousKline_{self.interval}"
        self.ws_url = f"{ws_base}/ws/{stream}"

        # K线数据
        self.kline_history: deque = deque(maxlen=200)
        self.current_kline: Optional[KlineData] = None

        # 信号管理
        self.active_signals: List[ResonanceTradeSignal] = []
        self.completed_signals: List[ResonanceTradeSignal] = []

        # 统计
        self.stats = {
            'total': 0,
            '10min': {'checked': 0, 'correct': 0},
            '30min': {'checked': 0, 'correct': 0},
            '1hour': {'checked': 0, 'correct': 0}
        }

        # 消息计数
        self.message_count = 0

        # Dashboard
        self.dashboard = ConsoleDashboard(
            symbol=self.symbol.upper(),
            interval=self.interval,
            contract_type=self.contract_type.upper(),
            min_signals=self.strategy.min_resonance
        )
        self.dashboard.update_meta(ws_url=self.ws_url, connection="初始化中")

        # 初始化日志
        self._init_log_file()
        self._print_init_info()

    def _print_init_info(self):
        """打印初始化信息"""
        enabled = [k for k, v in self.strategy.calculator.enabled.items() if v]
        print(f"[初始化] 交易对: {self.symbol.upper()}, 周期: {self.interval}")
        print(f"[初始化] 策略: {self.strategy.min_resonance}/{len(enabled)}指标共振，评分≥{self.strategy.min_score}")
        print(f"[初始化] 启用指标: {' + '.join(enabled)}")

    def _init_log_file(self):
        """初始化日志文件"""
        if os.path.exists(self.trade_log_file):
            return
        enabled = [k for k, v in self.strategy.calculator.enabled.items() if v]
        with open(self.trade_log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"交易信号日志 - {self.symbol.upper()} {self.interval}\n")
            f.write(f"策略: {self.strategy.min_resonance}/{len(enabled)}指标共振，评分≥{self.strategy.min_score}\n")
            f.write(f"启用指标: {', '.join(enabled)}\n")
            f.write(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    async def initialize_klines(self):
        """从 REST API 获取历史K线"""
        import aiohttp

        connector = None
        if USE_PROXY:
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(PROXY_URL)

        params = {
            'pair': self.symbol.upper(),
            'contractType': self.contract_type.upper(),
            'interval': self.interval,
            'limit': 200
        }

        url = "https://fapi.binance.com/fapi/v1/continuousKlines"
        print(f"[初始化] 正在获取历史K线...")

        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")

                    klines = await response.json()
                    if not klines:
                        print("[警告] 返回的K线数据为空")
                        return

                    current_time_ms = int(time.time() * 1000)

                    for k in klines:
                        close_time = int(k[6])
                        is_closed = close_time < current_time_ms

                        kline = KlineData(
                            timestamp=int(k[0]),
                            open=float(k[1]),
                            high=float(k[2]),
                            low=float(k[3]),
                            close=float(k[4]),
                            volume=float(k[5]),
                            is_closed=is_closed
                        )

                        if is_closed:
                            self.kline_history.append(kline)
                        else:
                            self.current_kline = kline

                    # 初始化计算一次指标
                    if self.kline_history:
                        target = self.current_kline or self.kline_history[-1]
                        history = list(self.kline_history)
                        if not self.current_kline:
                            history = history[:-1]
                        self.strategy.calculate(history, target)

                    print(f"[成功] 已加载 {len(self.kline_history)} 根已收盘K线")

        except Exception as e:
            print(f"[错误] 获取历史K线失败: {e}")

    async def process_kline(self, msg: dict):
        """处理 WebSocket K线消息"""
        # 更新消息计数和心跳
        self.message_count += 1
        self.dashboard.update_heartbeat(self.message_count)

        k = msg['k']
        kline = KlineData(
            timestamp=int(k['t']),
            open=float(k['o']),
            high=float(k['h']),
            low=float(k['l']),
            close=float(k['c']),
            volume=float(k['v']),
            is_closed=k['x']
        )

        # 计算指标
        score = self.strategy.calculate(list(self.kline_history), kline)

        # 更新 dashboard
        self._update_dashboard(kline)

        # K线收盘时处理
        if kline.is_closed:
            self.current_kline = kline
            self.kline_history.append(kline)

            # 检查是否产生信号
            if score and self._should_generate_signal(score):
                signal = self._create_signal(kline, score)
                self.active_signals.append(signal)
                self.stats['total'] += 1
                self._log_signal(signal)
                self.dashboard.push_alert(
                    f"新{signal.signal_type.value}信号 @ {signal.entry_price:.2f}",
                    level="success"
                )

            # 验证待检信号
            await self._check_signals(kline)

    def _should_generate_signal(self, score: ResonanceScore) -> bool:
        """判断是否应该生成信号"""
        return (score.signal_type != SignalType.HOLD and
                score.strength >= self.strategy.min_score)

    def _create_signal(self, kline: KlineData, score: ResonanceScore) -> ResonanceTradeSignal:
        """创建交易信号"""
        ts = kline.timestamp
        direction = "HIGHER" if score.signal_type == SignalType.BUY else "LOWER"

        return ResonanceTradeSignal(
            signal_id=f"{score.signal_type.value}_{ts}",
            timestamp=ts,
            datetime_str=datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            signal_type=score.signal_type,
            entry_price=kline.close,
            total_score=score.strength,
            confidence=score.confidence,
            resonance_count=score.resonance_count,
            trend_aligned=score.trend_aligned,
            reasons=self.strategy.resonance.get_signal_reasons(score),
            score_details=score.details,
            indicators=self.strategy._cached_indicators.copy(),
            predicted_direction=direction,
            check_times={
                '10min': ts + 10 * 60 * 1000,
                '30min': ts + 30 * 60 * 1000,
                '1hour': ts + 60 * 60 * 1000
            },
            results={
                '10min': {'price': None, 'result': None, 'checked': False},
                '30min': {'price': None, 'result': None, 'checked': False},
                '1hour': {'price': None, 'result': None, 'checked': False}
            }
        )

    async def _check_signals(self, kline: KlineData):
        """检查待验证的信号"""
        current_time = kline.timestamp
        current_price = kline.close

        for signal in self.active_signals[:]:
            all_checked = True

            for timeframe in ['10min', '30min', '1hour']:
                result = signal.results[timeframe]
                if result['checked']:
                    continue

                if current_time >= signal.check_times[timeframe]:
                    # 记录结果
                    actual = "HIGHER" if current_price > signal.entry_price else "LOWER" if current_price < signal.entry_price else "EQUAL"
                    result['price'] = current_price
                    result['result'] = actual
                    result['checked'] = True

                    # 更新统计
                    self.stats[timeframe]['checked'] += 1
                    is_correct = signal.predicted_direction == actual
                    if is_correct:
                        self.stats[timeframe]['correct'] += 1

                    self._log_verification(signal, timeframe, current_price, actual, is_correct)
                else:
                    all_checked = False

            # 所有验证完成，移到已完成列表
            if all_checked:
                self.completed_signals.append(signal)
                self.active_signals.remove(signal)

    def _update_dashboard(self, kline: KlineData):
        """更新 dashboard"""
        kline_dict = {
            'timestamp': kline.timestamp,
            'datetime': datetime.fromtimestamp(kline.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'open': kline.open, 'high': kline.high, 'low': kline.low,
            'close': kline.close, 'volume': kline.volume, 'is_closed': kline.is_closed
        }

        snapshot = self.strategy.get_snapshot()
        suggestion = self._get_suggestion()

        self.dashboard.update_market(kline=kline_dict, suggestion=suggestion)
        self.dashboard.update_indicators(snapshot, suggestion=suggestion)
        self.dashboard.update_stats({
            'total': self.stats['total'],
            'active': len(self.active_signals),
            'completed': len(self.completed_signals),
            'accuracy': {
                '10m': self.stats['10min'],
                '30m': self.stats['30min'],
                '1h': self.stats['1hour']
            }
        })

    def _get_suggestion(self) -> Optional[Dict]:
        """获取交易建议"""
        score = self.strategy._cached_score
        if not score:
            return None

        if score.signal_type == SignalType.BUY and score.strength >= self.strategy.min_score:
            bias, action = "LONG", "建议做多"
        elif score.signal_type == SignalType.SELL and score.strength >= self.strategy.min_score:
            bias, action = "SHORT", "建议做空"
        else:
            bias, action = "NEUTRAL", "观望等待"

        signals = self.strategy._indicator_signals
        return {
            'bias': bias,
            'confidence': score.confidence,
            'action': action,
            'summary': f"共振{score.resonance_count}, 评分{score.strength:.1f}",
            'votes': {
                'buy': sum(1 for s in signals.values() if s == 'BUY'),
                'sell': sum(1 for s in signals.values() if s == 'SELL'),
                'wait': sum(1 for s in signals.values() if s == 'WAIT')
            },
            'score': {'total': score.strength, 'resonance': score.resonance_count, 'trend_aligned': score.trend_aligned},
            'updated_at': datetime.now().strftime("%H:%M:%S")
        }

    def _log_signal(self, signal: ResonanceTradeSignal):
        """记录信号到日志"""
        with open(self.trade_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[新信号] {signal.signal_type.value} @ {signal.entry_price:.2f}\n")
            f.write(f"时间: {signal.datetime_str}\n")
            f.write(f"评分: {signal.total_score:.1f}, 信心度: {signal.confidence:.1%}\n")
            f.write(f"共振: {signal.resonance_count}个指标\n")
            f.write(f"预测: {signal.predicted_direction}\n")
            f.write(f"{'=' * 80}\n")
            f.flush()

    def _log_verification(self, signal: ResonanceTradeSignal, timeframe: str,
                          price: float, result: str, is_correct: bool):
        """记录验证结果"""
        change = price - signal.entry_price
        change_pct = change / signal.entry_price * 100
        status = "✓" if is_correct else "✗"

        with open(self.trade_log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timeframe}验证] {status} 预测:{signal.predicted_direction} 实际:{result} ")
            f.write(f"价格:{price:.2f} 变化:{change_pct:+.2f}%\n")
            f.flush()

        self.dashboard.push_alert(
            f"{timeframe}验证{'正确' if is_correct else '错误'}: {change_pct:+.2f}%",
            level="success" if is_correct else "warning"
        )

    async def run(self):
        """运行系统"""
        self.dashboard.update_meta(connection="加载历史数据...")
        await self.initialize_klines()

        self.dashboard.start()
        self.dashboard.push_alert("系统启动", level="info")

        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                self.dashboard.update_meta(connection=f"连接中...")
                ws_kwargs = {
                    'ping_interval': WS_PING_INTERVAL,
                    'ping_timeout': WS_PING_TIMEOUT,
                    'close_timeout': WS_CLOSE_TIMEOUT
                }

                async with websockets.connect(self.ws_url, **ws_kwargs) as ws:
                    retry_count = 0
                    self.dashboard.update_meta(connection="已连接")
                    self.dashboard.push_alert("WebSocket已连接", level="success")

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if 'k' in data:
                                await self.process_kline(data)
                        except Exception as e:
                            print(f"[错误] 处理消息失败: {e}")
                            self.dashboard.push_alert(f"错误: {e}", level="error")

            except websockets.exceptions.ConnectionClosed:
                self.dashboard.update_meta(connection="连接断开")
                self.dashboard.push_alert("连接断开，重连中...", level="warning")
            except Exception as e:
                print(f"[错误] WebSocket异常: {e}")

            retry_count += 1
            await asyncio.sleep(5)

        self.dashboard.push_alert("达到最大重试次数", level="error")
        self.dashboard.stop()


async def main():
    system = BinanceResonanceLiveTradingSystem()
    try:
        await system.run()
    except KeyboardInterrupt:
        system.dashboard.stop()
        print("\n[停止] 系统已停止")


if __name__ == '__main__':
    asyncio.run(main())
