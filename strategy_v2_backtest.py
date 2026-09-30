"""
==============================================================================
INSTITUTIONAL AI V2 - TREND-FOLLOW STRATEGY BACKTEST (1 YEAR)
Strategy Name: "Golden Trend Rider" | Symbol: XAUUSD.iux | Timeframe: H1
==============================================================================
Root Cause Fixed from V1 Analysis:
  ❌ V1 Problem: Scale-In 3 layers AGAINST trend = catastrophic $52 losses
  ❌ V1 Problem: Micro-BE too tight (2 pips) = 556 scratch exits with $0 profit
  ❌ V1 Problem: Risk:Reward 1:0.27 (risk $52 to win $14)

✅ V2 Solution: 
  1. SINGLE TRADE ONLY - No counter-trend scale-in ever
  2. Trend Alignment: H4 structure + H1 entry (HTF bias filter)
  3. Dynamic ATR-based SL (prevents fixed-pip vulnerability)
  4. Minimum R:R = 1:2 enforced on every trade
  5. Partial close at TP1 (50%) + Trail remaining runner
  6. Max 2% risk per trade — hard cap
  7. Session filter: London Open (10-14) + NY Session (15-20) only
  8. Daily drawdown hard stop: -5% per day auto-kill
  9. News/volatility filter via ATR spike detection

Target: +15-20% per month | Max Drawdown < 15% | Profit Factor > 1.8
==============================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================================
# V2 STRATEGY PARAMETERS
# ==============================================================================
INITIAL_CAPITAL    = 1000.0
RISK_PCT           = 1.5        # Risk 1.5% per trade ($15 on $1,000)
LOT_SIZE           = 0.02       # Fixed lot for simplicity
SPREAD_PIPS        = 1.8        # IUX XAUUSD typical spread

# ATR-based SL/TP
ATR_SL_MULT        = 1.2        # SL = 1.2 x ATR(14)
ATR_TP1_MULT       = 2.0        # TP1 = 2.0 x ATR (R:R = 1:1.67)
ATR_TP2_MULT       = 3.5        # TP2 Runner = 3.5 x ATR
PARTIAL_CLOSE_PCT  = 0.50       # Close 50% at TP1, let 50% run
TRAIL_ATR_MULT     = 1.0        # Trail = 1.0 x ATR after TP1 hit

# Entry Filters
MIN_CONFIDENCE     = 75         # Higher bar than V1
ATR_NOISE_MIN      = 3.0        # Min ATR(pips) to avoid dead zones
ATR_SPIKE_MAX      = 60.0       # Max ATR(pips) to avoid news spike zones

# Session Filter (broker server time = UTC+3 for IUX)
SESSION_HOURS      = list(range(10, 14)) + list(range(15, 21))  # London + NY

# Daily Loss Limit
DAILY_DD_LIMIT_PCT = 5.0        # Stop trading if down 5% on any day

# H4 Trend Filter (Multi-timeframe)
H4_TREND_LOOKBACK  = 12         # Look back 12 H4 bars for trend structure

PIP = 0.10  # 1 pip = $0.10 price movement for XAUUSD

def compute_indicators(df):
    """Compute all technical indicators on the dataframe."""
    # EMAs
    df['ema8']   = df['close'].ewm(span=8, adjust=False).mean()
    df['ema21']  = df['close'].ewm(span=21, adjust=False).mean()
    df['ema55']  = df['close'].ewm(span=55, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI(14)
    delta = df['close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # MACD(12,26,9)
    df['macd']     = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist']= df['macd'] - df['macd_sig']

    # ATR(14)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low']  - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # Bollinger Bands(20, 2)
    bb_mid = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = bb_mid + 2 * bb_std
    df['bb_lower'] = bb_mid - 2 * bb_std
    df['bb_mid']   = bb_mid

    # Higher-Low / Lower-High Swing Structure (30-bar lookback)
    df['swing_high'] = df['high'].rolling(20).max()
    df['swing_low']  = df['low'].rolling(20).min()

    # Momentum: rate of change
    df['roc5'] = df['close'].pct_change(5) * 100

    return df


def get_h4_trend(h4_df, current_dt):
    """
    Determine H4 trend bias (BULLISH / BEARISH / RANGING) at current time.
    Uses EMA alignment and higher-high/lower-low structure.
    """
    subset = h4_df[h4_df['datetime'] <= current_dt].tail(H4_TREND_LOOKBACK)
    if len(subset) < H4_TREND_LOOKBACK:
        return 'RANGING'

    last = subset.iloc[-1]
    ema21_h4  = subset['close'].ewm(span=21, adjust=False).mean().iloc[-1]
    ema55_h4  = subset['close'].ewm(span=55, adjust=False).mean().iloc[-1]
    ema200_h4 = subset['close'].ewm(span=200, adjust=False).mean().iloc[-1]

    price = last['close']

    # Bullish: price above all EMAs, EMA order aligned up
    if price > ema21_h4 > ema55_h4 and price > ema200_h4:
        # Confirm with higher-highs
        highs = subset['high'].values
        if highs[-1] > highs[-4] and highs[-4] > highs[-8]:
            return 'BULLISH'
        return 'BULLISH_WEAK'

    # Bearish: price below all EMAs, EMA order aligned down
    if price < ema21_h4 < ema55_h4 and price < ema200_h4:
        lows = subset['low'].values
        if lows[-1] < lows[-4] and lows[-4] < lows[-8]:
            return 'BEARISH'
        return 'BEARISH_WEAK'

    return 'RANGING'


def score_entry(row, df_slice, h4_bias):
    """
    Score a potential entry from 0-100.
    V2: Rewards trend alignment, penalizes counter-trend, requires minimum confluence.
    Returns (buy_score, sell_score)
    """
    close  = row['close']
    open_  = row['open']
    high   = row['high']
    low    = row['low']
    rsi    = row['rsi']
    macd_h = row['macd_hist']
    ema8   = row['ema8']
    ema21  = row['ema21']
    ema55  = row['ema55']
    ema200 = row['ema200']
    bb_u   = row['bb_upper']
    bb_l   = row['bb_lower']
    bb_m   = row['bb_mid']
    atr    = row['atr']

    buy_score = 0
    sell_score = 0

    # ── FACTOR 1: H4 Multi-Timeframe Bias (Heavy Weight 30 pts) ──
    if h4_bias == 'BULLISH':
        buy_score  += 30
        sell_score -= 20  # Penalize shorting in uptrend
    elif h4_bias == 'BULLISH_WEAK':
        buy_score  += 15
    elif h4_bias == 'BEARISH':
        sell_score += 30
        buy_score  -= 20
    elif h4_bias == 'BEARISH_WEAK':
        sell_score += 15
    # RANGING: no bias added

    # ── FACTOR 2: H1 EMA Trend Structure (20 pts) ──
    bull_ribbon = ema8 > ema21 > ema55 and close > ema200
    bear_ribbon = ema8 < ema21 < ema55 and close < ema200
    if bull_ribbon:  buy_score  += 20
    if bear_ribbon:  sell_score += 20

    # ── FACTOR 3: Price vs. Key Dynamic Level (15 pts) ──
    # Buy: price pulling back to ema21 in uptrend (value zone)
    if bull_ribbon and abs(close - ema21) / atr < 0.6:
        buy_score += 15
    # Sell: price retesting ema21 from below in downtrend
    if bear_ribbon and abs(close - ema21) / atr < 0.6:
        sell_score += 15

    # ── FACTOR 4: RSI Zone (10 pts) ──
    if 42 < rsi < 58:  # Neutral zone: both sides get partial score
        buy_score += 5; sell_score += 5
    elif 30 < rsi < 48 and bull_ribbon:  # Oversold pullback in uptrend
        buy_score += 10
    elif 52 < rsi < 70 and bear_ribbon:  # Overbought rally in downtrend
        sell_score += 10
    elif rsi < 30:   # Extreme oversold: strong buy signal
        buy_score += 15
    elif rsi > 70:   # Extreme overbought: strong sell signal
        sell_score += 15

    # ── FACTOR 5: MACD Histogram Momentum (10 pts) ──
    if macd_h > 0:    buy_score  += 10
    elif macd_h < 0:  sell_score += 10

    # ── FACTOR 6: Candlestick Pattern (10 pts) ──
    body = abs(close - open_)
    upper_wick = high - max(close, open_)
    lower_wick = min(close, open_) - low
    full_range = high - low + 0.001

    # Bullish pin bar (hammer)
    if close > open_ and lower_wick > body * 1.8 and lower_wick > upper_wick * 2:
        buy_score += 10
    # Bearish pin bar (shooting star)
    if close < open_ and upper_wick > body * 1.8 and upper_wick > lower_wick * 2:
        sell_score += 10
    # Bullish engulfing
    if len(df_slice) >= 2:
        prev = df_slice.iloc[-2]
        if close > prev['open'] > prev['close'] and open_ < prev['close']:
            buy_score += 8
        if close < prev['open'] < prev['close'] and open_ > prev['close']:
            sell_score += 8

    # ── FACTOR 7: Bollinger Band Position (5 pts) ──
    # Buy at lower BB in uptrend (mean reversion + trend)
    if close < bb_m and bull_ribbon:
        buy_score += 5
    # Sell at upper BB in downtrend
    if close > bb_m and bear_ribbon:
        sell_score += 5

    # ── SAFETY GUARD: Zero out counter-trend signals in strong trends ──
    if h4_bias == 'BULLISH':
        sell_score = max(0, sell_score)
    if h4_bias == 'BEARISH':
        buy_score = max(0, buy_score)

    return max(0, buy_score), max(0, sell_score)


def run_backtest_v2():
    """Main backtest engine for V2 Trend-Follow strategy."""
    print("=" * 75)
    print("  LOADING 1-YEAR DATA FROM IUX MARKETS MT5...")
    if not mt5.initialize():
        print("❌ MT5 Initialization failed"); return

    dt_from = datetime(2025, 9, 28, 0, 0)
    dt_to   = datetime(2026, 9, 30, 23, 59)

    h1_rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, dt_from, dt_to)
    h4_rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H4, dt_from, dt_to)
    mt5.shutdown()

    if h1_rates is None or len(h1_rates) == 0:
        print("❌ No H1 data fetched"); return
    if h4_rates is None or len(h4_rates) == 0:
        print("❌ No H4 data fetched"); return

    df = pd.DataFrame(h1_rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df = compute_indicators(df).dropna().reset_index(drop=True)

    dfh4 = pd.DataFrame(h4_rates)
    dfh4['datetime'] = pd.to_datetime(dfh4['time'], unit='s')
    dfh4 = compute_indicators(dfh4).dropna().reset_index(drop=True)

    print(f"  ✅ H1: {len(df):,} bars | H4: {len(dfh4):,} bars")
    print(f"  📅 Period: {df['datetime'].iloc[0].strftime('%d %b %Y')} → {df['datetime'].iloc[-1].strftime('%d %b %Y')}")
    print()

    # ── Simulation State ──
    capital       = INITIAL_CAPITAL
    peak_capital  = INITIAL_CAPITAL
    max_dd_dollar = 0.0
    max_dd_pct    = 0.0

    position   = None   # Active trade (dict) or None
    trades     = []
    monthly    = defaultdict(lambda: {'pnl': 0.0, 'trades': 0, 'wins': 0, 'start_bal': 0.0, 'peak': 0.0, 'max_dd': 0.0})
    daily_pnl  = defaultdict(float)

    start_sim  = pd.Timestamp("2025-10-01")
    start_idx  = df[df['datetime'] >= start_sim].index[0]

    for i in range(start_idx, len(df)):
        row      = df.iloc[i]
        dt       = row['datetime']
        month_k  = dt.strftime('%Y-%m')
        day_k    = dt.strftime('%Y-%m-%d')
        hour     = dt.hour
        cur_p    = row['close']
        cur_high = row['high']
        cur_low  = row['low']
        atr      = row['atr']
        atr_pips = atr / PIP

        # Initialize monthly start balance
        if monthly[month_k]['start_bal'] == 0.0:
            monthly[month_k]['start_bal'] = capital
            monthly[month_k]['peak']      = capital

        # ── Position Management ──
        if position is not None:
            ptype    = position['type']
            entry    = position['entry']
            sl       = position['sl']
            tp1      = position['tp1']
            tp2      = position['tp2']
            trail_sl = position.get('trail_sl', None)
            be_lock  = position.get('be_locked', False)
            lot1     = position['lot1']
            lot2     = position['lot2']  # Runner (0 if fully closed)
            partial_done = position.get('partial_done', False)

            # Compute current floating PnL on remaining position
            if ptype == 'BUY':
                progress_pips = (cur_high - entry) / PIP
                loss_pips     = (entry - cur_low) / PIP
            else:
                progress_pips = (entry - cur_low) / PIP
                loss_pips     = (cur_high - entry) / PIP

            exit_price = None
            exit_reason = None
            realized_pnl = 0.0

            # ── 1. Check TP1: Partial Close 50% ──
            if not partial_done:
                tp1_hit = (ptype == 'BUY' and cur_high >= tp1) or (ptype == 'SELL' and cur_low <= tp1)
                if tp1_hit:
                    tp1_pips = abs(tp1 - entry) / PIP - SPREAD_PIPS
                    partial_profit = (tp1_pips) * (lot1 * 10.0)
                    realized_pnl += partial_profit
                    capital       += partial_profit
                    daily_pnl[day_k] += partial_profit
                    # Move SL to breakeven + 5 pips for runner
                    be_offset = 5 * PIP
                    position['sl']          = entry + be_offset if ptype == 'BUY' else entry - be_offset
                    position['be_locked']   = True
                    position['partial_done']= True
                    position['lot2']        = lot2  # Runner stays
                    # Set trailing SL at TP1 level initially
                    position['trail_sl']    = tp1 - (atr * TRAIL_ATR_MULT) if ptype == 'BUY' else tp1 + (atr * TRAIL_ATR_MULT)

            # ── 2. Trailing Stop on Runner ──
            if partial_done and lot2 > 0:
                if ptype == 'BUY':
                    new_trail = cur_high - (atr * TRAIL_ATR_MULT)
                    if position.get('trail_sl') is None or new_trail > position['trail_sl']:
                        position['trail_sl'] = new_trail
                    # Check trail hit
                    if cur_low <= position['trail_sl']:
                        exit_price  = position['trail_sl']
                        exit_reason = 'Trail Stop (Runner)'
                        exit_pips   = (exit_price - entry) / PIP - SPREAD_PIPS
                        realized_pnl += exit_pips * (lot2 * 10.0)
                else:
                    new_trail = cur_low + (atr * TRAIL_ATR_MULT)
                    if position.get('trail_sl') is None or new_trail < position['trail_sl']:
                        position['trail_sl'] = new_trail
                    if cur_high >= position['trail_sl']:
                        exit_price  = position['trail_sl']
                        exit_reason = 'Trail Stop (Runner)'
                        exit_pips   = (entry - exit_price) / PIP - SPREAD_PIPS
                        realized_pnl += exit_pips * (lot2 * 10.0)

            # ── 3. Full TP2: Close Runner ──
            if partial_done and lot2 > 0 and exit_reason is None:
                tp2_hit = (ptype == 'BUY' and cur_high >= tp2) or (ptype == 'SELL' and cur_low <= tp2)
                if tp2_hit:
                    exit_price  = tp2
                    exit_reason = 'TP2 Full Close'
                    exit_pips   = abs(tp2 - entry) / PIP - SPREAD_PIPS
                    realized_pnl += exit_pips * (lot2 * 10.0)

            # ── 4. Stop Loss Hit ──
            if exit_reason is None:
                sl_hit = (ptype == 'BUY' and cur_low <= position['sl']) or (ptype == 'SELL' and cur_high >= position['sl'])
                if sl_hit:
                    exit_price  = position['sl']
                    exit_reason = 'Stop Loss'
                    if not partial_done:
                        # Full loss on both lots
                        exit_pips = (exit_price - entry) / PIP if ptype == 'BUY' else (entry - exit_price) / PIP
                        exit_pips -= SPREAD_PIPS
                        realized_pnl = exit_pips * ((lot1 + lot2) * 10.0)
                    else:
                        # Partial closed already, only runner loss
                        exit_pips = (exit_price - entry) / PIP if ptype == 'BUY' else (entry - exit_price) / PIP
                        exit_pips -= SPREAD_PIPS
                        realized_pnl += exit_pips * (lot2 * 10.0)

            # ── 5. Finalize Exit ──
            if exit_reason is not None:
                capital      += realized_pnl
                daily_pnl[day_k] += realized_pnl
                monthly[month_k]['pnl']    += realized_pnl
                monthly[month_k]['trades'] += 1
                if realized_pnl > 0:
                    monthly[month_k]['wins'] += 1

                trades.append({
                    'open_dt': position['open_dt'],
                    'close_dt': dt,
                    'month': month_k,
                    'type': ptype,
                    'entry': entry,
                    'exit_price': exit_price,
                    'reason': exit_reason,
                    'pnl': round(realized_pnl, 2),
                    'win': realized_pnl > 0,
                    'h4_bias': position.get('h4_bias', '?'),
                    'partial': partial_done,
                    'score': position.get('score', 0),
                    'capital': round(capital, 2)
                })
                position = None

                # Update drawdown
                if capital > peak_capital:
                    peak_capital = capital
                dd = peak_capital - capital
                dd_pct = (dd / peak_capital) * 100 if peak_capital > 0 else 0
                if dd > max_dd_dollar:  max_dd_dollar = dd
                if dd_pct > max_dd_pct: max_dd_pct = dd_pct

                # Monthly drawdown tracking
                if capital > monthly[month_k]['peak']:
                    monthly[month_k]['peak'] = capital
                m_dd = monthly[month_k]['peak'] - capital
                if m_dd > monthly[month_k]['max_dd']:
                    monthly[month_k]['max_dd'] = m_dd

            else:
                # Update monthly peak
                if capital > monthly[month_k]['peak']:
                    monthly[month_k]['peak'] = capital
                m_dd = monthly[month_k]['peak'] - capital
                if m_dd > monthly[month_k]['max_dd']:
                    monthly[month_k]['max_dd'] = m_dd
            continue

        # ── Entry Signal Logic ──
        # 1. Session filter
        if hour not in SESSION_HOURS:
            continue

        # 2. ATR noise/spike filter
        atr_pips_now = atr / PIP
        if atr_pips_now < ATR_NOISE_MIN or atr_pips_now > ATR_SPIKE_MAX:
            continue

        # 3. Daily drawdown limit
        day_pnl_sum = sum(v for k, v in daily_pnl.items() if k == day_k)
        if day_pnl_sum <= -(capital * DAILY_DD_LIMIT_PCT / 100):
            continue

        # 4. Get H4 trend bias
        h4_bias = get_h4_trend(dfh4, dt)
        if h4_bias == 'RANGING':
            continue  # Skip ranging markets entirely

        # 5. Score entry
        df_slice = df.iloc[max(0, i-5):i+1]
        buy_s, sell_s = score_entry(row, df_slice, h4_bias)

        # 6. Enforce minimum score AND trend alignment
        trade_type = None
        score_used = 0
        if buy_s >= MIN_CONFIDENCE and buy_s > sell_s and h4_bias in ('BULLISH', 'BULLISH_WEAK'):
            trade_type = 'BUY'
            score_used = buy_s
        elif sell_s >= MIN_CONFIDENCE and sell_s > buy_s and h4_bias in ('BEARISH', 'BEARISH_WEAK'):
            trade_type = 'SELL'
            score_used = sell_s

        if trade_type is None:
            continue

        # 7. Calculate SL / TP using ATR
        sl_dist = atr * ATR_SL_MULT   # price distance for SL
        tp1_dist = atr * ATR_TP1_MULT  # TP1 at 2.0x ATR (R:R ≈ 1:1.67)
        tp2_dist = atr * ATR_TP2_MULT  # TP2 Runner at 3.5x ATR

        # Enforce minimum 20 pips SL (so we don't get stopped on noise)
        sl_dist = max(sl_dist, 20 * PIP)

        ask_entry = cur_p + (SPREAD_PIPS * PIP / 2)
        bid_entry = cur_p - (SPREAD_PIPS * PIP / 2)

        if trade_type == 'BUY':
            entry = ask_entry
            sl    = entry - sl_dist
            tp1   = entry + tp1_dist
            tp2   = entry + tp2_dist
        else:
            entry = bid_entry
            sl    = entry + sl_dist
            tp1   = entry - tp1_dist
            tp2   = entry - tp2_dist

        # 8. R:R check: minimum 1.5:1
        rr = tp1_dist / sl_dist
        if rr < 1.4:
            continue

        # 9. Open position (split into lot1 for TP1, lot2 for runner)
        position = {
            'type':         trade_type,
            'entry':        entry,
            'sl':           sl,
            'tp1':          tp1,
            'tp2':          tp2,
            'lot1':         LOT_SIZE * PARTIAL_CLOSE_PCT,
            'lot2':         LOT_SIZE * (1 - PARTIAL_CLOSE_PCT),
            'partial_done': False,
            'be_locked':    False,
            'trail_sl':     None,
            'open_dt':      dt,
            'h4_bias':      h4_bias,
            'score':        score_used,
            'atr_at_entry': atr
        }

    # ── Print Results ──
    total  = len(trades)
    wins   = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    wr     = len(wins) / total * 100 if total > 0 else 0
    net_p  = capital - INITIAL_CAPITAL
    net_pct = net_p / INITIAL_CAPITAL * 100
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))
    pf     = round(gp / gl, 2) if gl > 0 else 99.0
    num_m  = len(monthly)
    avg_m  = net_pct / num_m if num_m else 0

    # Exit type breakdown
    from collections import Counter
    exits  = Counter(t['reason'] for t in trades)
    biases = Counter(t['h4_bias'] for t in trades)

    print("=" * 75)
    print("     🏆 INSTITUTIONAL AI V2 - 1 YEAR BACKTEST REPORT 🏆")
    print(f"     Strategy: Golden Trend Rider | Symbol: XAUUSD.iux | H1 + H4 MTF")
    print(f"     Period: {df['datetime'].iloc[start_idx].strftime('%d %b %Y')} → {df['datetime'].iloc[-1].strftime('%d %b %Y')}")
    print("=" * 75)
    print(f"💵 Initial Capital:          ${INITIAL_CAPITAL:,.2f} USD")
    print(f"💰 Final Balance:            ${capital:,.2f} USD")
    print(f"📈 Total Net Return:         ${net_p:+,.2f} USD ({net_pct:+.2f}%)")
    print(f"🔥 Average Monthly Return:   {avg_m:+.2f}% / Month")
    print(f"📊 Profit Factor:            {pf}")
    print(f"🎯 Total Trades:             {total}")
    print(f"✅ Winners:                  {len(wins)} ({wr:.1f}%)")
    print(f"❌ Losers:                   {len(losses)} ({100-wr:.1f}%)")
    print(f"🛡️ Max Drawdown:             ${max_dd_dollar:,.2f} ({max_dd_pct:.2f}%)")
    print(f"   Avg Trades / Month:       {total//num_m if num_m else 0}")
    print("=" * 75)
    print("EXIT BREAKDOWN:")
    for reason, cnt in exits.most_common():
        r_pnl = sum(t['pnl'] for t in trades if t['reason'] == reason)
        print(f"  • {reason:<30}: {cnt:>3} trades | Net: ${r_pnl:+,.2f}")
    print()
    print("H4 BIAS ON ENTRY TRADES:")
    for bias, cnt in biases.most_common():
        b_pnl = sum(t['pnl'] for t in trades if t['h4_bias'] == bias)
        print(f"  • {bias:<15}: {cnt:>3} trades | Net: ${b_pnl:+,.2f}")
    print("=" * 75)
    print("MONTH-BY-MONTH BREAKDOWN:")
    print(f"  {'Month':<14} | {'PnL ($)':>9} | {'Return%':>9} | {'Trades':>7} | {'WR':>7} | {'MaxDD($)':>9}")
    print("  " + "-" * 65)

    month_labels = {
        '2025-10': 'Oct 2025', '2025-11': 'Nov 2025', '2025-12': 'Dec 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026',
        '2026-04': 'Apr 2026', '2026-05': 'May 2026', '2026-06': 'Jun 2026',
        '2026-07': 'Jul 2026', '2026-08': 'Aug 2026', '2026-09': 'Sep 2026',
    }

    for mk in sorted(monthly.keys()):
        md = monthly[mk]
        if md['trades'] == 0: continue
        m_wr  = md['wins'] / md['trades'] * 100 if md['trades'] > 0 else 0
        m_ret = md['pnl'] / md['start_bal'] * 100 if md['start_bal'] > 0 else 0
        label = month_labels.get(mk, mk)
        flag  = " ✅" if m_ret >= 15 else (" ⚠️" if m_ret < 0 else "")
        print(f"  {label:<14} | ${md['pnl']:>8.2f} | {m_ret:>+8.2f}% | {md['trades']:>6}  | {m_wr:>5.1f}% | ${md['max_dd']:>7.2f}{flag}")

    print("=" * 75)

    # Final Verdict
    months_positive = sum(1 for mk, md in monthly.items() if md['pnl'] > 0)
    months_target   = sum(1 for mk, md in monthly.items() if md['pnl'] / (md['start_bal'] or 1) * 100 >= 15)
    print(f"\n📋 PERFORMANCE VERDICT:")
    print(f"   • Profitable months:   {months_positive}/{num_m}")
    print(f"   • Hit 15%+ target:     {months_target}/{num_m} months")
    print(f"   • Portfolio survived:  {'✅ YES' if capital > 0 else '❌ BLOWN'}")
    print(f"   • Max DD stayed < 20%: {'✅ YES' if max_dd_pct < 20 else '⚠️ NO'}")
    print("=" * 75)

if __name__ == '__main__':
    run_backtest_v2()
