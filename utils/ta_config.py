"""Centralized TA indicator parameters and signal thresholds.

Every magic number for technical analysis lives here.
Scripts import from here, never hardcode indicator parameters.
"""

# =============================================================================
# INDICATOR COMPUTATION PARAMETERS
# =============================================================================

# RSI
RSI_PERIOD = 14

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Bollinger Bands
BB_PERIOD = 20
BB_STD = 2.0

# ADX
ADX_PERIOD = 14

# SMAs
SMA_FAST = 20
SMA_MID = 50
SMA_SLOW = 200

# Stochastic RSI
STOCH_RSI_LENGTH = 14
STOCH_RSI_K = 3
STOCH_RSI_D = 3

# ATR
ATR_PERIOD = 14

# Volume
VOLUME_SMA_PERIOD = 20
VOLUME_SMA_LONG = 50

# =============================================================================
# SIGNAL THRESHOLDS
# =============================================================================

# RSI levels
RSI_OVERSOLD = 30
RSI_APPROACHING_OVERSOLD = 40
RSI_OVERBOUGHT = 70
RSI_ELEVATED = 60

# ADX levels
ADX_WEAK = 20
ADX_STRONG = 25

# Bollinger Band position
BB_LOWER_THRESHOLD = 0.2
BB_UPPER_THRESHOLD = 0.8

# Volume
VOLUME_SPIKE = 2.0
VOLUME_HIGH = 1.5

# Fibonacci
FIB_PROXIMITY_PCT = 2.0
FIB_LOOKBACK = 60

# =============================================================================
# PATTERN DETECTION
# =============================================================================

# Bull flag
BULL_FLAG_POLE_MIN = 0.08        # 8% minimum pole move
BULL_FLAG_CONSOL_MAX = 0.06      # 6% max consolidation range

# Lookbacks
PATTERN_LOOKBACK = 120
DIV_LOOKBACK = 60
DIV_SWING_WINDOW = 5
SWING_POINT_WINDOW = 10          # Default window for swing point detection

# =============================================================================
# SCORING / CONFLUENCE
# =============================================================================

SIGNAL_BULLISH_THRESHOLD = 3     # bullish >= bearish + N → bullish verdict
CONFLUENCE_BOOST = 15            # Bonus points for multi-indicator confirmation

# =============================================================================
# FIBONACCI LEVELS
# =============================================================================

FIB_LEVELS = {
    0.0: "0% (Swing Low)",
    0.236: "23.6%",
    0.382: "38.2%",
    0.5: "50%",
    0.618: "61.8%",
    0.786: "78.6%",
    1.0: "100% (Swing High)",
}

# Standard retracement ratios
FIB_RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
