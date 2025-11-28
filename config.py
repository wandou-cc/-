"""
配置文件 - Binance API配置
"""

# Binance API配置
# 如果无法访问，可以使用代理或备用域名

# 方式1：使用Binance合约域名
BINANCE_API_URL = "https://fapi.binance.com"
BINANCE_WS_URL = "wss://fstream.binance.com"

# 方式2：使用备用域名（如果主域名无法访问）
# BINANCE_API_URL = "https://fapi1.binance.com"
# BINANCE_WS_URL = "wss://fstream.binance.com"

# 方式3：使用代理（需要安装 aiohttp-socks）
USE_PROXY = True
PROXY_URL = 'socks5://127.0.0.1:7897'  # 例如: "socks5://127.0.0.1:1080" 或 "http://127.0.0.1:7890"
# 如果在中国大陆，可能需要使用代理
# USE_PROXY = True
# PROXY_URL = "http://127.0.0.1:7890"  # 替换为你的代理地址

# WebSocket重连配置
WS_PING_INTERVAL = 20  # WebSocket ping间隔（秒）
WS_PING_TIMEOUT = 10   # WebSocket ping超时（秒）
WS_CLOSE_TIMEOUT = 5   # WebSocket关闭超时（秒）
MAX_RETRIES = 10       # 最大重试次数
HEARTBEAT_INTERVAL = 10  # 心跳日志输出间隔（秒），控制心跳频率而非K线输出频率

# 请求超时配置
REQUEST_TIMEOUT = 30   # HTTP请求超时（秒）

# 交易配置
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL = "5m"
DEFAULT_CONTRACT_TYPE = "perpetual"
MIN_SIGNALS = 3  # 最少需要几个指标同时发出信号

# 指标参数配置
MACD_PARAMS = {
    'fast_period': 12,
    'slow_period': 26,
    'signal_period': 9
}

RSI_PARAMS = {
    'period': 14,
    'overbought': 70,
    'oversold': 30
}

BB_PARAMS = {
    'period': 20,
    'std_dev': 2.0
}

KDJ_PARAMS = {
    'period': 9,
    'signal': 3
}

EMA_PARAMS = {
    'ultra_fast': 5,
    'fast': 10,
    'medium': 20,
    'slow': 60
}

CCI_PARAMS = {
    'period': 20
}

ATR_PARAMS = {
    'period': 14
}

# 指标启用配置
INDICATOR_SWITCHES = {
    'use_macd': True,    # 启用MACD（动量层）
    'use_rsi': True,     # 启用RSI（动量层）
    'use_kdj': True,     # 启用KDJ（动量层）
    'use_boll': False,    # 启用布林带（时机层）
    'use_ema': False,     # 启用EMA四线系统（趋势层）
    'use_cci': True,     # 启用CCI（动量层）
    'use_atr': True,     # 启用ATR（波动率层）
    'use_vwap': False    # 启用VWAP（日内交易基准，适合短周期如1m/5m）
}

# 共振策略配置
RESONANCE_PARAMS = {
    'min_resonance': None,  # 最少共振指标数量（None=自动计算为启用指标数*0.7，或手动指定如5）
    'min_score': 70.0,      # 最低评分（0-100，推荐60-80之间）
}

# 自动计算min_resonance（如果未手动指定）
def _calculate_min_resonance():
    """根据启用的指标数量自动计算最少共振数"""
    if RESONANCE_PARAMS['min_resonance'] is not None:
        return RESONANCE_PARAMS['min_resonance']

    # 统计启用的指标数量
    enabled_count = sum([
        INDICATOR_SWITCHES['use_macd'],
        INDICATOR_SWITCHES['use_rsi'],
        INDICATOR_SWITCHES['use_kdj'],
        INDICATOR_SWITCHES['use_boll'],
        INDICATOR_SWITCHES['use_ema'],
        INDICATOR_SWITCHES['use_cci'],
        INDICATOR_SWITCHES['use_atr'],
        INDICATOR_SWITCHES['use_vwap'],
    ])

    # 默认要求70%的指标共振，向上取整
    import math
    min_resonance = math.ceil(enabled_count * 0.7)

    # 至少要2个指标共振
    return max(2, min_resonance)

# 获取实际的min_resonance值
def get_min_resonance():
    """获取实际的最少共振指标数量"""
    return _calculate_min_resonance()

# 获取启用的指标数量
def get_enabled_indicator_count():
    """获取启用的指标总数"""
    return sum(INDICATOR_SWITCHES.values())
