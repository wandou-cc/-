"""
共振策略 - 多指标共振系统（增强版）
专门用于提高10分钟、30分钟短期预测准确率

核心理念：
1. 多个指标必须在同一方向上"共振"（同时给出相同信号）
2. 使用趋势过滤器，只在明确趋势中交易
3. 动量确认机制，确保价格动能支持方向
4. 波动率过滤，避免在震荡市中频繁交易

指标体系（7个指标）：
- 趋势层：EMA四线系统
- 动量层：RSI + KDJ + CCI
- 时机层：MACD + BOLL + ATR
- 可选：VWAP（日内交易基准）
"""

from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import math


class SignalType(Enum):
    """信号类型"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class ResonanceScore:
    """共振得分"""
    signal_type: SignalType
    strength: float  # 信号强度 0-100
    confidence: float  # 信心度 0-1
    resonance_count: int  # 共振指标数量
    details: Dict[str, Dict]  # 各指标详情
    trend_aligned: bool  # 是否与趋势一致
    momentum_confirmed: bool  # 动量是否确认
    volatility_ok: bool  # 波动率是否适合


class ResonanceStrategy:
    """
    共振策略（增强版 - 7指标系统）

    评分维度：
    1. 趋势一致性（25分）- 确保方向与主趋势一致
    2. 指标共振度（50分）- 7个指标共振评分
       - 核心指标（RSI/KDJ/MACD/BOLL）每个7分
       - 辅助指标（CCI/ATR）每个6分
       - VWAP（可选）5分
    3. 动量强度（15分）- 价格动能支持
    4. 时机把握（10分）- 进场时机是否恰当

    信号要求：
    - 至少5个指标共振（7个中5个，VWAP可选）
    - 总分>=70才开单
    - 建议与主趋势一致
    """

    def __init__(self,
                 # 共振要求
                 min_resonance: int = 5,  # 最少共振指标数
                 min_score: float = 70.0,  # 最低总分
                 # 趋势过滤
                 use_trend_filter: bool = True,
                 # 动量过滤
                 use_momentum_filter: bool = True,
                 # 波动率过滤
                 use_volatility_filter: bool = True,
                 min_volatility: float = 0.0005,  # 最小波动率（避免盘整）
                 max_volatility: float = 0.05,   # 最大波动率（避免暴涨暴跌）
                 # 指标开关（控制哪些指标参与共振）
                 use_macd: bool = True,   # 是否使用MACD
                 use_rsi: bool = True,    # 是否使用RSI
                 use_kdj: bool = True,    # 是否使用KDJ
                 use_boll: bool = True,   # 是否使用布林带
                 use_ema: bool = True,    # 是否使用EMA趋势
                 use_cci: bool = True,    # 是否使用CCI
                 use_atr: bool = True,    # 是否使用ATR
                 use_vwap: bool = False):  # 是否使用VWAP（仅日内交易）
        """初始化共振策略"""
        self.min_resonance = min_resonance
        self.min_score = min_score
        self.use_trend_filter = use_trend_filter
        self.use_momentum_filter = use_momentum_filter
        self.use_volatility_filter = use_volatility_filter
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility
        # 指标开关
        self.use_macd = use_macd
        self.use_rsi = use_rsi
        self.use_kdj = use_kdj
        self.use_boll = use_boll
        self.use_ema = use_ema
        self.use_cci = use_cci
        self.use_atr = use_atr
        self.use_vwap = use_vwap

    def check_trend_alignment(self, ema_ultra_fast: float, ema_fast: float,
                             ema_medium: float, ema_slow: float,
                             current_price: float) -> Tuple[str, float]:
        """
        检查趋势一致性（25分）

        Returns:
            (趋势方向, 得分)
        """
        # 判断趋势
        bullish_signals = 0
        bearish_signals = 0

        # EMA排列
        if ema_ultra_fast > ema_fast > ema_medium > ema_slow:
            bullish_signals += 3  # 完美多头排列
        elif ema_ultra_fast < ema_fast < ema_medium < ema_slow:
            bearish_signals += 3  # 完美空头排列
        else:
            # 部分排列
            if ema_ultra_fast > ema_fast:
                bullish_signals += 1
            else:
                bearish_signals += 1
            if ema_fast > ema_medium:
                bullish_signals += 1
            else:
                bearish_signals += 1
            if ema_medium > ema_slow:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # 价格位置
        if current_price > ema_slow:
            bullish_signals += 2
        elif current_price < ema_slow:
            bearish_signals += 2

        # 价格与快线关系
        if current_price > ema_ultra_fast:
            bullish_signals += 1
        elif current_price < ema_ultra_fast:
            bearish_signals += 1

        # 计算得分
        total = bullish_signals + bearish_signals
        if bullish_signals > bearish_signals:
            trend = "BULLISH"
            score = (bullish_signals / 6) * 25  # 最高25分
        elif bearish_signals > bullish_signals:
            trend = "BEARISH"
            score = (bearish_signals / 6) * 25
        else:
            trend = "NEUTRAL"
            score = 0

        return trend, score

    def check_rsi_resonance(self, rsi: float, previous_rsi: Optional[float] = None) -> Tuple[str, float, str]:
        """
        RSI共振检查

        Returns:
            (信号方向, 强度, 原因)
        """
        signal = "NEUTRAL"
        strength = 0.0
        reason = ""

        # 极端超卖/超买
        if rsi < 20:
            signal = "BUY"
            strength = 100
            reason = f"极度超卖(RSI={rsi:.1f})"
        elif rsi < 30:
            signal = "BUY"
            strength = 70 + (30 - rsi) * 3  # 30附近70分，越低越高
            reason = f"超卖区(RSI={rsi:.1f})"
        elif rsi > 80:
            signal = "SELL"
            strength = 100
            reason = f"极度超买(RSI={rsi:.1f})"
        elif rsi > 70:
            signal = "SELL"
            strength = 70 + (rsi - 70) * 3
            reason = f"超买区(RSI={rsi:.1f})"
        else:
            # 中性区，看趋势
            if previous_rsi is not None:
                rsi_change = rsi - previous_rsi
                if abs(rsi_change) > 5:  # RSI快速变化
                    if rsi_change > 0 and rsi < 50:
                        signal = "BUY"
                        strength = 50
                        reason = f"RSI快速上升(RSI={rsi:.1f}, 变化+{rsi_change:.1f})"
                    elif rsi_change < 0 and rsi > 50:
                        signal = "SELL"
                        strength = 50
                        reason = f"RSI快速下降(RSI={rsi:.1f}, 变化{rsi_change:.1f})"

        return signal, strength, reason

    def check_kdj_resonance(self, k: float, d: float, j: float,
                           previous_k: Optional[float] = None,
                           previous_d: Optional[float] = None) -> Tuple[str, float, str]:
        """KDJ共振检查"""
        signal = "NEUTRAL"
        strength = 0.0
        reasons = []

        # 超卖超买判断
        if k < 20 and d < 20:
            signal = "BUY"
            strength = 80
            reasons.append(f"KD双超卖(K={k:.1f}, D={d:.1f})")
        elif k > 80 and d > 80:
            signal = "SELL"
            strength = 80
            reasons.append(f"KD双超买(K={k:.1f}, D={d:.1f})")

        # J值极端
        if j < 0:
            if signal == "BUY":
                strength = 100
            else:
                signal = "BUY"
                strength = 90
            reasons.append(f"J极度超卖({j:.1f})")
        elif j > 100:
            if signal == "SELL":
                strength = 100
            else:
                signal = "SELL"
                strength = 90
            reasons.append(f"J极度超买({j:.1f})")

        # 金叉死叉（强信号）
        if previous_k is not None and previous_d is not None:
            if previous_k < previous_d and k > d:
                if signal == "BUY":
                    strength = min(100, strength + 20)
                else:
                    signal = "BUY"
                    strength = 85
                reasons.append("KDJ金叉")
            elif previous_k > previous_d and k < d:
                if signal == "SELL":
                    strength = min(100, strength + 20)
                else:
                    signal = "SELL"
                    strength = 85
                reasons.append("KDJ死叉")

        # 低位金叉 / 高位死叉（最强信号）
        if previous_k is not None and previous_d is not None:
            if previous_k < previous_d and k > d and k < 30:
                signal = "BUY"
                strength = 100
                reasons.append("低位金叉（最强买入）")
            elif previous_k > previous_d and k < d and k > 70:
                signal = "SELL"
                strength = 100
                reasons.append("高位死叉（最强卖出）")

        reason = "KDJ: " + ", ".join(reasons) if reasons else "KDJ中性"
        return signal, strength, reason

    def check_macd_resonance(self, macd: float, signal_line: float, histogram: float,
                            previous_macd: Optional[float] = None,
                            previous_signal: Optional[float] = None) -> Tuple[str, float, str]:
        """MACD共振检查"""
        sig = "NEUTRAL"
        strength = 0.0
        reasons = []

        # 金叉死叉（最重要）
        if previous_macd is not None and previous_signal is not None:
            if previous_macd < previous_signal and macd > signal_line:
                sig = "BUY"
                # 零轴上方金叉更强
                if macd > 0:
                    strength = 100
                    reasons.append("零轴上方金叉（强势）")
                else:
                    strength = 85
                    reasons.append("MACD金叉")
            elif previous_macd > previous_signal and macd < signal_line:
                sig = "SELL"
                # 零轴下方死叉更强
                if macd < 0:
                    strength = 100
                    reasons.append("零轴下方死叉（强势）")
                else:
                    strength = 85
                    reasons.append("MACD死叉")

        # 柱状图方向（辅助）
        if sig == "NEUTRAL":
            if histogram > 0 and macd > signal_line:
                sig = "BUY"
                strength = 60
                reasons.append("MACD多头排列")
            elif histogram < 0 and macd < signal_line:
                sig = "SELL"
                strength = 60
                reasons.append("MACD空头排列")

        # 背离检查（可选，需要价格数据）
        # 这里简化处理，主要看金叉死叉

        reason = "MACD: " + ", ".join(reasons) if reasons else "MACD中性"
        return sig, strength, reason

    def check_bollinger_resonance(self, upper: float, middle: float, lower: float,
                                  current_price: float, percent_b: Optional[float] = None) -> Tuple[str, float, str]:
        """布林带共振检查"""
        signal = "NEUTRAL"
        strength = 0.0
        reason = ""

        if percent_b is not None:
            if percent_b < 0:
                signal = "BUY"
                strength = 100
                reason = f"价格跌破下轨(%B={percent_b:.2f})"
            elif percent_b < 0.1:
                signal = "BUY"
                strength = 90
                reason = f"触及下轨(%B={percent_b:.2f})"
            elif percent_b < 0.2:
                signal = "BUY"
                strength = 70
                reason = f"接近下轨(%B={percent_b:.2f})"
            elif percent_b > 1:
                signal = "SELL"
                strength = 100
                reason = f"价格突破上轨(%B={percent_b:.2f})"
            elif percent_b > 0.9:
                signal = "SELL"
                strength = 90
                reason = f"触及上轨(%B={percent_b:.2f})"
            elif percent_b > 0.8:
                signal = "SELL"
                strength = 70
                reason = f"接近上轨(%B={percent_b:.2f})"

        return signal, strength, reason

    def check_cci_resonance(self, cci: float, previous_cci: Optional[float] = None) -> Tuple[str, float, str]:
        """
        CCI共振检查

        Returns:
            (信号方向, 强度, 原因)
        """
        signal = "NEUTRAL"
        strength = 0.0
        reasons = []

        # 极端超卖/超买区域
        if cci < -200:
            signal = "BUY"
            strength = 100
            reasons.append(f"极度超卖(CCI={cci:.1f})")
        elif cci < -100:
            signal = "BUY"
            strength = 80 + ((-100 - cci) / 100) * 20  # -100到-200之间，80-100分
            reasons.append(f"超卖区(CCI={cci:.1f})")
        elif cci > 200:
            signal = "SELL"
            strength = 100
            reasons.append(f"极度超买(CCI={cci:.1f})")
        elif cci > 100:
            signal = "SELL"
            strength = 80 + ((cci - 100) / 100) * 20  # 100到200之间，80-100分
            reasons.append(f"超买区(CCI={cci:.1f})")
        else:
            # 中性区，检查趋势和穿越
            if previous_cci is not None:
                # 穿越零轴（重要信号）
                if previous_cci < 0 and cci > 0:
                    signal = "BUY"
                    strength = 75
                    reasons.append(f"CCI向上穿越零轴({cci:.1f})")
                elif previous_cci > 0 and cci < 0:
                    signal = "SELL"
                    strength = 75
                    reasons.append(f"CCI向下穿越零轴({cci:.1f})")
                # 从超卖/超买区反弹
                elif previous_cci < -100 and cci > -100:
                    signal = "BUY"
                    strength = 85
                    reasons.append(f"从超卖区反弹({previous_cci:.1f}->{cci:.1f})")
                elif previous_cci > 100 and cci < 100:
                    signal = "SELL"
                    strength = 85
                    reasons.append(f"从超买区回落({previous_cci:.1f}->{cci:.1f})")
                # CCI快速变化
                elif abs(cci - previous_cci) > 50:
                    if cci > previous_cci and cci < 0:
                        signal = "BUY"
                        strength = 60
                        reasons.append(f"CCI快速上升({previous_cci:.1f}->{cci:.1f})")
                    elif cci < previous_cci and cci > 0:
                        signal = "SELL"
                        strength = 60
                        reasons.append(f"CCI快速下降({previous_cci:.1f}->{cci:.1f})")

        reason = "CCI: " + ", ".join(reasons) if reasons else "CCI中性"
        return signal, strength, reason

    def check_atr_resonance(self, atr: float, high: float, low: float,
                           close: float, previous_atr: Optional[float] = None) -> Tuple[str, float, str]:
        """
        ATR波动率共振检查

        ATR主要用于：
        1. 波动率过滤（已在check_volatility中实现）
        2. 突破有效性确认
        3. 趋势强度判断

        Returns:
            (信号方向, 强度, 原因)
        """
        signal = "NEUTRAL"
        strength = 0.0
        reasons = []

        if atr is None or atr == 0:
            return signal, strength, "ATR数据不足"

        # 计算当前K线的波动幅度与ATR的比值
        current_range = high - low
        range_to_atr = current_range / atr if atr > 0 else 0

        # ATR趋势（波动率是否在增加/减少）
        if previous_atr is not None and previous_atr > 0:
            atr_change = (atr - previous_atr) / previous_atr

            # 波动率快速扩大（趋势加速）
            if atr_change > 0.1:  # ATR增加10%以上
                # 波动率扩大通常意味着趋势加速，但不直接给出方向
                # 需要结合价格位置判断
                price_position = (close - low) / (high - low) if (high - low) > 0 else 0.5

                if price_position > 0.7:  # 收盘在上方，波动率扩大
                    signal = "BUY"
                    strength = 70
                    reasons.append(f"波动率扩大且收高(ATR+{atr_change*100:.1f}%)")
                elif price_position < 0.3:  # 收盘在下方，波动率扩大
                    signal = "SELL"
                    strength = 70
                    reasons.append(f"波动率扩大且收低(ATR+{atr_change*100:.1f}%)")
                else:
                    strength = 30
                    reasons.append(f"波动率扩大(ATR+{atr_change*100:.1f}%)，方向不明")

            # 波动率收缩（可能酝酿突破）
            elif atr_change < -0.1:  # ATR减少10%以上
                strength = 40
                reasons.append(f"波动率收缩(ATR{atr_change*100:.1f}%)，警惕突破")

        # 当前K线波动幅度异常（突破信号）
        if range_to_atr > 1.5:  # 当前K线波动超过ATR的1.5倍
            price_position = (close - low) / (high - low) if (high - low) > 0 else 0.5

            if price_position > 0.7:
                if signal == "BUY":
                    strength = min(100, strength + 30)  # 强化买入信号
                else:
                    signal = "BUY"
                    strength = 75
                reasons.append(f"大阳线突破(幅度{range_to_atr:.1f}倍ATR)")
            elif price_position < 0.3:
                if signal == "SELL":
                    strength = min(100, strength + 30)  # 强化卖出信号
                else:
                    signal = "SELL"
                    strength = 75
                reasons.append(f"大阴线突破(幅度{range_to_atr:.1f}倍ATR)")

        # 波动率过低（盘整）
        elif range_to_atr < 0.5:
            strength = 20
            reasons.append(f"窄幅盘整(幅度{range_to_atr:.1f}倍ATR)")

        reason = "ATR: " + ", ".join(reasons) if reasons else "ATR中性"
        return signal, strength, reason

    def check_vwap_resonance(self, vwap: float, current_price: float,
                            previous_price: Optional[float] = None) -> Tuple[str, float, str]:
        """
        VWAP共振检查

        VWAP是日内交易的重要基准：
        1. 价格在VWAP上方 = 强势
        2. 价格在VWAP下方 = 弱势
        3. 穿越VWAP = 重要信号

        Returns:
            (信号方向, 强度, 原因)
        """
        signal = "NEUTRAL"
        strength = 0.0
        reason = ""

        if vwap is None or vwap == 0:
            return signal, strength, "VWAP数据不足"

        # 计算价格偏离VWAP的程度
        deviation = (current_price - vwap) / vwap * 100

        # 检查穿越（最强信号）
        if previous_price is not None:
            # 向上穿越VWAP
            if previous_price <= vwap and current_price > vwap:
                signal = "BUY"
                strength = 90
                reason = f"向上突破VWAP(偏离+{deviation:.2f}%)"
            # 向下穿越VWAP
            elif previous_price >= vwap and current_price < vwap:
                signal = "SELL"
                strength = 90
                reason = f"向下跌破VWAP(偏离{deviation:.2f}%)"

        # 如果没有穿越，根据偏离程度判断
        if signal == "NEUTRAL":
            if deviation > 2.0:
                signal = "SELL"
                strength = 70
                reason = f"远高于VWAP(+{deviation:.2f}%)，可能回落"
            elif deviation > 0.5:
                signal = "BUY"
                strength = 60
                reason = f"高于VWAP(+{deviation:.2f}%)，强势"
            elif deviation < -2.0:
                signal = "BUY"
                strength = 70
                reason = f"远低于VWAP({deviation:.2f}%)，可能反弹"
            elif deviation < -0.5:
                signal = "SELL"
                strength = 60
                reason = f"低于VWAP({deviation:.2f}%)，弱势"
            else:
                reason = f"接近VWAP(偏离{deviation:.2f}%)"

        return signal, strength, reason

    def check_momentum(self, current_price: float, ema_fast: Optional[float] = None,
                      previous_price: Optional[float] = None) -> Tuple[bool, float]:
        """
        检查动量确认（15分）

        Returns:
            (是否确认, 得分)
        """
        if previous_price is None:
            return False, 0

        # 价格变化率
        price_change = (current_price - previous_price) / previous_price

        # 价格与均线关系(如果EMA未启用,则跳过这部分检查)
        if ema_fast is not None:
            price_ema_diff = (current_price - ema_fast) / ema_fast
        else:
            price_ema_diff = 0

        # 动量得分
        score = 0
        confirmed = False

        # 价格快速变化
        if abs(price_change) > 0.001:  # 0.1%以上变化
            score += 8
            confirmed = True

        # 价格远离均线（动能强）
        if abs(price_ema_diff) > 0.002:  # 0.2%以上偏离
            score += 7
            if abs(price_ema_diff) > 0.005:  # 0.5%以上偏离（强势）
                score += 3

        return confirmed, min(15, score)

    def check_volatility(self, high: float, low: float, close: float) -> Tuple[bool, str]:
        """
        检查波动率是否适合交易

        Returns:
            (是否适合, 原因)
        """
        # 计算波动率
        volatility = (high - low) / close

        if volatility < self.min_volatility:
            return False, f"波动率过低({volatility:.4f}), 市场盘整"
        elif volatility > self.max_volatility:
            return False, f"波动率过高({volatility:.4f}), 市场剧烈波动"
        else:
            return True, f"波动率适中({volatility:.4f})"

    def calculate_resonance(self,
                           # RSI
                           rsi: float,
                           previous_rsi: Optional[float] = None,
                           # KDJ
                           kdj_k: float = None,
                           kdj_d: float = None,
                           kdj_j: float = None,
                           previous_k: Optional[float] = None,
                           previous_d: Optional[float] = None,
                           # MACD
                           macd: float = None,
                           macd_signal: float = None,
                           macd_histogram: float = None,
                           previous_macd: Optional[float] = None,
                           previous_macd_signal: Optional[float] = None,
                           # EMA
                           ema_ultra_fast: float = None,
                           ema_fast: float = None,
                           ema_medium: float = None,
                           ema_slow: float = None,
                           # BOLL
                           bb_upper: float = None,
                           bb_middle: float = None,
                           bb_lower: float = None,
                           bb_percent_b: Optional[float] = None,
                           # CCI（新）
                           cci: Optional[float] = None,
                           previous_cci: Optional[float] = None,
                           # ATR（新）
                           atr: Optional[float] = None,
                           previous_atr: Optional[float] = None,
                           # VWAP（新，可选）
                           vwap: Optional[float] = None,
                           # 价格和K线
                           current_price: float = None,
                           previous_price: Optional[float] = None,
                           high: float = None,
                           low: float = None) -> ResonanceScore:
        """
        计算共振得分（增强版 - 7指标系统）

        评分系统：
        1. 趋势一致性：25分
        2. 指标共振度：50分
           - 核心指标（RSI/KDJ/MACD/BOLL）每个7分
           - 辅助指标（CCI/ATR）每个6分
           - VWAP（可选）5分
        3. 动量确认：15分
        4. 时机把握：10分
        """

        details = {}
        buy_indicators = []
        sell_indicators = []

        # 1. 检查趋势（25分）
        trend = "NEUTRAL"
        trend_score = 0
        if self.use_ema and ema_ultra_fast is not None:
            trend, trend_score = self.check_trend_alignment(
                ema_ultra_fast, ema_fast, ema_medium, ema_slow, current_price
            )
            details['trend'] = {
                'direction': trend,
                'score': trend_score,
                'reason': f"趋势{trend}, 得分{trend_score:.1f}"
            }

        # 2. 检查各指标共振（50分）
        # 核心指标（每个7分）
        # RSI
        rsi_score = 0
        if self.use_rsi and rsi is not None:
            rsi_sig, rsi_str, rsi_reason = self.check_rsi_resonance(rsi, previous_rsi)
            rsi_score = (rsi_str / 100) * 7
            details['RSI'] = {
                'signal': rsi_sig,
                'strength': rsi_str,
                'score': rsi_score,
                'reason': rsi_reason
            }
            if rsi_sig == "BUY":
                buy_indicators.append('RSI')
            elif rsi_sig == "SELL":
                sell_indicators.append('RSI')

        # KDJ
        kdj_score = 0
        if self.use_kdj and kdj_k is not None:
            kdj_sig, kdj_str, kdj_reason = self.check_kdj_resonance(
                kdj_k, kdj_d, kdj_j, previous_k, previous_d
            )
            kdj_score = (kdj_str / 100) * 7
            details['KDJ'] = {
                'signal': kdj_sig,
                'strength': kdj_str,
                'score': kdj_score,
                'reason': kdj_reason
            }
            if kdj_sig == "BUY":
                buy_indicators.append('KDJ')
            elif kdj_sig == "SELL":
                sell_indicators.append('KDJ')

        # MACD
        macd_score = 0
        if self.use_macd and macd is not None:
            macd_sig, macd_str, macd_reason = self.check_macd_resonance(
                macd, macd_signal, macd_histogram, previous_macd, previous_macd_signal
            )
            macd_score = (macd_str / 100) * 7
            details['MACD'] = {
                'signal': macd_sig,
                'strength': macd_str,
                'score': macd_score,
                'reason': macd_reason
            }
            if macd_sig == "BUY":
                buy_indicators.append('MACD')
            elif macd_sig == "SELL":
                sell_indicators.append('MACD')

        # BOLL
        bb_score = 0
        if self.use_boll and bb_upper is not None:
            bb_sig, bb_str, bb_reason = self.check_bollinger_resonance(
                bb_upper, bb_middle, bb_lower, current_price, bb_percent_b
            )
            bb_score = (bb_str / 100) * 7
            details['BOLL'] = {
                'signal': bb_sig,
                'strength': bb_str,
                'score': bb_score,
                'reason': bb_reason
            }
            if bb_sig == "BUY":
                buy_indicators.append('BOLL')
            elif bb_sig == "SELL":
                sell_indicators.append('BOLL')

        # 辅助指标（每个6分）
        # CCI
        cci_score = 0
        if self.use_cci and cci is not None:
            cci_sig, cci_str, cci_reason = self.check_cci_resonance(cci, previous_cci)
            cci_score = (cci_str / 100) * 6
            details['CCI'] = {
                'signal': cci_sig,
                'strength': cci_str,
                'score': cci_score,
                'reason': cci_reason
            }
            if cci_sig == "BUY":
                buy_indicators.append('CCI')
            elif cci_sig == "SELL":
                sell_indicators.append('CCI')

        # ATR
        atr_score = 0
        if self.use_atr and atr is not None:
            atr_sig, atr_str, atr_reason = self.check_atr_resonance(
                atr, high, low, current_price, previous_atr
            )
            atr_score = (atr_str / 100) * 6
            details['ATR'] = {
                'signal': atr_sig,
                'strength': atr_str,
                'score': atr_score,
                'reason': atr_reason
            }
            if atr_sig == "BUY":
                buy_indicators.append('ATR')
            elif atr_sig == "SELL":
                sell_indicators.append('ATR')

        # VWAP（可选，5分）
        vwap_score = 0
        if self.use_vwap and vwap is not None:
            vwap_sig, vwap_str, vwap_reason = self.check_vwap_resonance(
                vwap, current_price, previous_price
            )
            vwap_score = (vwap_str / 100) * 5
            details['VWAP'] = {
                'signal': vwap_sig,
                'strength': vwap_str,
                'score': vwap_score,
                'reason': vwap_reason
            }
            if vwap_sig == "BUY":
                buy_indicators.append('VWAP')
            elif vwap_sig == "SELL":
                sell_indicators.append('VWAP')

        # 计算指标共振得分
        indicator_score = rsi_score + kdj_score + macd_score + bb_score + cci_score + atr_score + vwap_score

        # 3. 检查动量（20分）
        momentum_confirmed, momentum_score = self.check_momentum(
            current_price, ema_fast, previous_price
        )
        details['momentum'] = {
            'confirmed': momentum_confirmed,
            'score': momentum_score,
            'reason': f"动量{'确认' if momentum_confirmed else '未确认'}"
        }

        # 4. 检查波动率
        volatility_ok = True
        volatility_reason = "未检查"
        if self.use_volatility_filter and high is not None and low is not None:
            volatility_ok, volatility_reason = self.check_volatility(high, low, current_price)
        details['volatility'] = {
            'ok': volatility_ok,
            'reason': volatility_reason
        }

        # 5. 时机把握（10分）- 基于指标一致性
        timing_score = 0
        if len(buy_indicators) >= 4 or len(sell_indicators) >= 4:
            timing_score = 10  # 4个以上指标共振，时机完美
        elif len(buy_indicators) >= 3 or len(sell_indicators) >= 3:
            timing_score = 7   # 3个指标共振，时机良好

        details['timing'] = {
            'score': timing_score,
            'reason': f"共振指标数: {max(len(buy_indicators), len(sell_indicators))}"
        }

        # 计算总分
        total_score = 0
        resonance_count = max(len(buy_indicators), len(sell_indicators))

        # 判断信号方向
        if len(buy_indicators) >= self.min_resonance:
            signal_type = SignalType.BUY
            # 买入信号的总分
            total_score = trend_score + indicator_score + momentum_score + timing_score

            # 趋势过滤：如果趋势不对，大幅降分
            if self.use_trend_filter and trend != "BULLISH":
                total_score *= 0.5  # 减半
                details['trend']['penalty'] = "逆趋势交易，得分减半"

            # 动量过滤
            if self.use_momentum_filter and not momentum_confirmed:
                total_score *= 0.8
                details['momentum']['penalty'] = "动量未确认，得分打8折"

        elif len(sell_indicators) >= self.min_resonance:
            signal_type = SignalType.SELL
            # 卖出信号的总分
            total_score = trend_score + indicator_score + momentum_score + timing_score

            # 趋势过滤
            if self.use_trend_filter and trend != "BEARISH":
                total_score *= 0.5
                details['trend']['penalty'] = "逆趋势交易，得分减半"

            # 动量过滤
            if self.use_momentum_filter and not momentum_confirmed:
                total_score *= 0.8
                details['momentum']['penalty'] = "动量未确认，得分打8折"
        else:
            signal_type = SignalType.HOLD
            total_score = 0

        # 波动率过滤
        if not volatility_ok:
            signal_type = SignalType.HOLD
            total_score = 0
            details['volatility']['penalty'] = "波动率不适合，放弃信号"

        # 计算信心度
        confidence = min(1.0, total_score / 100)

        # 检查趋势一致性
        trend_aligned = False
        if signal_type == SignalType.BUY and trend == "BULLISH":
            trend_aligned = True
        elif signal_type == SignalType.SELL and trend == "BEARISH":
            trend_aligned = True

        return ResonanceScore(
            signal_type=signal_type,
            strength=total_score,
            confidence=confidence,
            resonance_count=resonance_count,
            details=details,
            trend_aligned=trend_aligned,
            momentum_confirmed=momentum_confirmed,
            volatility_ok=volatility_ok
        )

    def get_signal_reasons(self, score: ResonanceScore) -> List[str]:
        """生成信号原因列表"""
        reasons = []

        # 计算总指标数（根据启用的指标）
        total_indicators = sum([
            self.use_rsi,
            self.use_kdj,
            self.use_macd,
            self.use_boll,
            self.use_cci,
            self.use_atr,
            self.use_vwap
        ])

        # 总分和共振
        reasons.append(f"总评分: {score.strength:.1f}/100, 信心度: {score.confidence:.1%}")
        reasons.append(f"共振指标数: {score.resonance_count}/{total_indicators}")

        # 趋势
        trend_info = score.details.get('trend', {})
        reasons.append(f"趋势: {trend_info.get('reason', 'N/A')}")
        if 'penalty' in trend_info:
            reasons.append(f"⚠️ {trend_info['penalty']}")

        # 各指标（核心+辅助）
        for indicator in ['RSI', 'KDJ', 'MACD', 'BOLL', 'CCI', 'ATR', 'VWAP']:
            if indicator in score.details:
                info = score.details[indicator]
                if info['signal'] != 'NEUTRAL':
                    reasons.append(f"[{indicator}] {info['reason']} (强度{info['strength']:.0f}, 得分{info['score']:.1f})")

        # 动量
        momentum_info = score.details.get('momentum', {})
        reasons.append(f"动量: {momentum_info.get('reason', 'N/A')} (得分{momentum_info.get('score', 0):.1f})")
        if 'penalty' in momentum_info:
            reasons.append(f"⚠️ {momentum_info['penalty']}")

        # 波动率
        volatility_info = score.details.get('volatility', {})
        reasons.append(f"波动率: {volatility_info.get('reason', 'N/A')}")
        if 'penalty' in volatility_info:
            reasons.append(f"⚠️ {volatility_info['penalty']}")

        # 时机
        timing_info = score.details.get('timing', {})
        reasons.append(f"时机: {timing_info.get('reason', 'N/A')} (得分{timing_info.get('score', 0):.1f})")

        return reasons
