"""
==============================================================================
INSTITUTIONAL AI V3 - SMART TREND SNIPER BACKTEST (1 YEAR: Oct 2025 - Sep 2026)
Strategy: Single-Trade Trend-Follow with Partial Close + Trailing Runner
Symbol: XAUUSD.iux | Timeframe: H1 (Entry) + H4 (Bias Filter)
==============================================================================
KEY FIXES from V1 (Scale-In Disaster) & V2 (Zero-trade debug):
  ✅ Correct XAUUSD pips: 1 pip = $0.10 price, POINT = 0.01
  ✅ ATR in price units (avg ~$21 = ~210 pips for H1 Gold)
  ✅ Correct lot: 0.05 lot ($1 per pip) — proper sizing for $1,000 
  ✅ Dynamic ATR-SL avoids fixed pip vulnerability
  ✅ H4 trend bias (strict: no ranging market entries)
  ✅ EMA pullback entries (best R:R vs. breakout chasing)
  ✅ Partial close 50% at TP1 + trail runner
  ✅ Daily loss limit -5% per day

MONEY MATH:
  • 0.05 lot → $1.00 profit per 1 price unit ($1.00/pip)
  • ATR on H1 Gold ≈ $15-25 price range average
  • SL = 0.8 × ATR ≈ $14 per trade (1.4% of $1,000)
  • TP1 = 1.6 × ATR ≈ $28 on 50% position = +$14 net
  • TP2 (runner) = 3.0 × ATR ≈ $52 on 50% position = +$26 extra
  • 10 trades/month × 60% WR → ~6 winners → +$14×6 = +$84 from TP1 alone
  • Runners add significant upside in trending months
==============================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================================
# STRATEGY PARAMETERS (tuned for XAUUSD H1, $1,000 capital)
# ==============================================================================
INITIAL_CAPITAL = 1000.0

# Lot sizing — 0.05 lot = $1 profit per price unit / pip on Gold
# Risk per trade: 0.8 × ATR × $1/pip ≈ $14 on avg (1.4%)
LOT_FULL     = 0.05          # Full position lot
LOT_HALF     = 0.025         # Half position (50% closed at TP1)
SPREAD       = 0.30          # IUX XAUUSD spread in price units (~$0.30 = ~3 pips)

# ATR-based exit levels (price-based, NOT pips)
ATR_SL_MULT  = 0.8          # SL = 0.8 × ATR
ATR_TP1_MULT = 1.6          # TP1 = 1.6 × ATR  (R:R ≈ 1:2)
ATR_TP2_MULT = 3.0          # TP2 = 3.0 × ATR  (Runner, R:R ≈ 1:3.75)
ATR_TRAIL    = 1.0          # Trail distance for runner

# ATR filters (in price units, NOT pips)
ATR_MIN      = 5.0          # Avoid flat/dead market (< $5 ATR)
ATR_MAX      = 120.0        # Avoid extreme news spikes (> $120 ATR)

# Session filter (broker server UTC+3 → use 10-20 for London+NY)
SESSION_HOURS = set(range(10, 21))

# Min confluence score (0-100 scale)
MIN_SCORE    = 70

# Max risk per day
DAILY_DD_PCT = 5.0           # Stop new trades if daily loss > 5%

# H4 lookback bars for trend
H4_LOOKBACK  = 20

def compute_indicators_gold(df):
    """Compute indicators appropriate for Gold H1 timescale."""
    # Fast EMAs for trend direction
    df['ema9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema21']  = df['close'].ewm(span=21,  adjust=False).mean()
    df['ema50']  = df['close'].ewm(span=50,  adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI(14)
    d = df['close'].diff()
    g = d.where(d > 0, 0).rolling(14).mean()
    l = (-d.where(d < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + g / (l + 1e-9)))

    # MACD(12,26,9)
    df['macd']     = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_h']   = df['macd'] - df['macd_sig']

    # ATR(14) — in price units (dollars)
    hi_lo = df['high'] - df['low']
    hi_cl = (df['high'] - df['close'].shift()).abs()
    lo_cl = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hi_lo, hi_cl, lo_cl], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # 50-bar Donchian Channel (swing structure)
    df['dc_high'] = df['high'].rolling(50).max()
    df['dc_low']  = df['low'].rolling(50).min()
    df['dc_mid']  = (df['dc_high'] + df['dc_low']) / 2

    # Volume-adjusted momentum (if vol data exists)
    if 'tick_volume' in df.columns:
        df['vol_ma'] = df['tick_volume'].rolling(20).mean()

    return df


def get_h4_bias(dfh4, current_dt):
    """Returns H4 trend: BULL, BEAR, or RANGE."""
    sub = dfh4[dfh4['datetime'] <= current_dt].tail(H4_LOOKBACK)
    if len(sub) < 8:
        return 'RANGE'

    # H4 EMA check
    e21  = sub['close'].ewm(span=21,  adjust=False).mean().iloc[-1]
    e50  = sub['close'].ewm(span=50,  adjust=False).mean().iloc[-1]
    e200 = sub['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    price = sub.iloc[-1]['close']

    # Strong bull: price > e21 > e50, price above e200
    if price > e21 > e50 and price > e200 * 0.995:
        # Additional check: price made higher highs over last 10 bars
        highs = sub['high'].values[-10:]
        if highs[-1] >= highs[0]:
            return 'BULL'
        return 'BULL_WEAK'

    # Strong bear: price < e21 < e50, price below e200
    if price < e21 < e50 and price < e200 * 1.005:
        lows = sub['low'].values[-10:]
        if lows[-1] <= lows[0]:
            return 'BEAR'
        return 'BEAR_WEAK'

    return 'RANGE'


def score_signal(row, prev_rows, h4_bias):
    """Score a BUY or SELL signal. Returns (buy_score, sell_score)."""
    close  = row['close']
    open_  = row['open']
    high   = row['high']
    low    = row['low']
    rsi    = row['rsi']
    macd_h = row['macd_h']
    e9     = row['ema9']
    e21    = row['ema21']
    e50    = row['ema50']
    e200   = row['ema200']
    atr    = row['atr']

    bs = 0  # buy score
    ss = 0  # sell score

    # ─── H4 BIAS (most important, 35 pts) ───
    if   h4_bias == 'BULL':       bs += 35
    elif h4_bias == 'BULL_WEAK':  bs += 20
    elif h4_bias == 'BEAR':       ss += 35
    elif h4_bias == 'BEAR_WEAK':  ss += 20
    else:  # RANGE: both sides penalized
        bs -= 10; ss -= 10

    # ─── H1 EMA ALIGNMENT (20 pts) ───
    h1_bull = (e9 > e21 > e50)
    h1_bear = (e9 < e21 < e50)
    above200 = close > e200
    below200 = close < e200

    if h1_bull and above200:  bs += 20
    elif h1_bull:             bs += 10
    if h1_bear and below200:  ss += 20
    elif h1_bear:             ss += 10

    # ─── PULLBACK TO EMA21 (Value Zone, 20 pts) ───
    dist_e21 = abs(close - e21)
    if h4_bias in ('BULL', 'BULL_WEAK') and h1_bull:
        # Price pulling back INTO ema21 in uptrend = ideal long entry
        if dist_e21 <= atr * 0.5 and low < e21 * 1.003:
            bs += 20
        elif dist_e21 <= atr * 0.8:
            bs += 10
    if h4_bias in ('BEAR', 'BEAR_WEAK') and h1_bear:
        if dist_e21 <= atr * 0.5 and high > e21 * 0.997:
            ss += 20
        elif dist_e21 <= atr * 0.8:
            ss += 10

    # ─── RSI ZONE (15 pts) ───
    if   35 < rsi < 50 and h4_bias in ('BULL', 'BULL_WEAK'):  bs += 15  # oversold in uptrend
    elif 30 <= rsi <= 35:                                       bs += 20  # extreme oversold
    elif 50 < rsi < 65 and h4_bias in ('BEAR', 'BEAR_WEAK'):  ss += 15  # overbought in downtrend
    elif rsi >= 65:                                             ss += 20  # extreme overbought

    # ─── MACD MOMENTUM (10 pts) ───
    if macd_h > 0:   bs += 10
    elif macd_h < 0: ss += 10

    # ─── CANDLESTICK PATTERNS (10 pts) ───
    body      = abs(close - open_)
    up_wick   = high - max(close, open_)
    dn_wick   = min(close, open_) - low
    rng       = high - low + 0.01

    # Hammer / Bullish pin bar
    if dn_wick > body * 2 and dn_wick > up_wick * 1.5 and rng > 0:
        bs += 10
    # Shooting star / Bearish pin bar
    if up_wick > body * 2 and up_wick > dn_wick * 1.5 and rng > 0:
        ss += 10
    # Bullish engulf
    if len(prev_rows) >= 1:
        pr = prev_rows.iloc[-1]
        if close > open_ and pr['close'] < pr['open'] and close > pr['open'] and open_ < pr['close']:
            bs += 8
        if close < open_ and pr['close'] > pr['open'] and close < pr['open'] and open_ > pr['close']:
            ss += 8

    # ─── GUARD: No counter-trend trades ───
    if h4_bias == 'BULL':  ss = max(0, ss - 20)
    if h4_bias == 'BEAR':  bs = max(0, bs - 20)

    return max(0, bs), max(0, ss)


def run_v3_backtest():
    print("=" * 72)
    print("  SMART TREND SNIPER — LOADING REAL MT5 DATA (1 YEAR)...")
    if not mt5.initialize():
        print("❌ MT5 failed"); return

    dt_from = datetime(2025, 9, 20, 0, 0)
    dt_to   = datetime(2026, 9, 30, 23, 59)
    h1r = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, dt_from, dt_to)
    h4r = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H4, dt_from, dt_to)
    mt5.shutdown()

    df   = compute_indicators_gold(pd.DataFrame(h1r))
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df   = df.dropna().reset_index(drop=True)

    dfh4 = compute_indicators_gold(pd.DataFrame(h4r))
    dfh4['datetime'] = pd.to_datetime(dfh4['time'], unit='s')
    dfh4 = dfh4.dropna().reset_index(drop=True)

    print(f"  ✅ H1: {len(df):,} bars | H4: {len(dfh4):,} bars")
    print(f"  📅 Period: {df['datetime'].iloc[0].strftime('%d %b %Y')} → {df['datetime'].iloc[-1].strftime('%d %b %Y')}")
    print()

    # ─── Simulation ───
    capital      = INITIAL_CAPITAL
    peak_cap     = INITIAL_CAPITAL
    max_dd_amt   = 0.0
    max_dd_pct   = 0.0

    pos          = None
    all_trades   = []
    monthly      = defaultdict(lambda: {'pnl': 0.0, 'trades': 0, 'wins': 0, 'start_bal': 0.0, 'peak': 0.0, 'max_dd': 0.0})
    daily_pnl    = defaultdict(float)

    start_sim    = pd.Timestamp("2025-10-01")
    start_idx    = df[df['datetime'] >= start_sim].index[0]

    for i in range(start_idx, len(df)):
        row      = df.iloc[i]
        dt       = row['datetime']
        month_k  = dt.strftime('%Y-%m')
        day_k    = dt.strftime('%Y-%m-%d')
        hour     = dt.hour
        cur_p    = row['close']
        cur_h    = row['high']
        cur_l    = row['low']
        atr      = row['atr']

        # Init monthly start balance
        if monthly[month_k]['start_bal'] == 0.0:
            monthly[month_k]['start_bal'] = capital
            monthly[month_k]['peak']      = capital

        # ─── Position Management ───
        if pos is not None:
            ptype   = pos['type']
            entry   = pos['entry']
            sl_now  = pos['sl']
            tp1     = pos['tp1']
            tp2     = pos['tp2']
            lot_now = pos['lot']
            partial = pos['partial']

            realized = 0.0
            reason   = None

            # 1. TP1 partial close (50% → $0.025 lot hits TP1)
            if not partial:
                tp1_hit = (ptype == 'BUY' and cur_h >= tp1) or (ptype == 'SELL' and cur_l <= tp1)
                if tp1_hit:
                    half_lot = LOT_HALF
                    tp1_pnl  = (abs(tp1 - entry) - SPREAD) * half_lot * 100.0
                    realized += tp1_pnl
                    capital  += tp1_pnl
                    daily_pnl[day_k] += tp1_pnl
                    # Move SL to entry + buffer (breakeven + spread)
                    be_buf = SPREAD + 0.50  # $0.50 cushion
                    pos['sl'] = (entry + be_buf) if ptype == 'BUY' else (entry - be_buf)
                    pos['partial'] = True
                    pos['trail_sl'] = tp1 - atr * ATR_TRAIL if ptype == 'BUY' else tp1 + atr * ATR_TRAIL
                    pos['lot']  = LOT_HALF   # Now only runner

            # 2. Trailing stop on runner
            if partial:
                if ptype == 'BUY':
                    new_trail = cur_h - atr * ATR_TRAIL
                    if new_trail > pos.get('trail_sl', -1e9):
                        pos['trail_sl'] = new_trail
                    if cur_l <= pos['trail_sl']:
                        reason = 'Trail Stop'
                        exit_p = pos['trail_sl']
                        realized = (exit_p - entry - SPREAD) * LOT_HALF * 100.0
                else:
                    new_trail = cur_l + atr * ATR_TRAIL
                    if new_trail < pos.get('trail_sl', 1e9):
                        pos['trail_sl'] = new_trail
                    if cur_h >= pos['trail_sl']:
                        reason = 'Trail Stop'
                        exit_p = pos['trail_sl']
                        realized = (entry - exit_p - SPREAD) * LOT_HALF * 100.0

            # 3. TP2 full close runner
            if partial and reason is None:
                tp2_hit = (ptype == 'BUY' and cur_h >= tp2) or (ptype == 'SELL' and cur_l <= tp2)
                if tp2_hit:
                    reason = 'TP2 (Runner)'
                    exit_p = tp2
                    realized = (abs(tp2 - entry) - SPREAD) * LOT_HALF * 100.0

            # 4. Stop Loss
            if reason is None:
                sl_hit = (ptype == 'BUY' and cur_l <= sl_now) or (ptype == 'SELL' and cur_h >= sl_now)
                if sl_hit:
                    reason = 'Stop Loss'
                    exit_p = sl_now
                    if not partial:
                        # Full loss
                        realized = (exit_p - entry if ptype == 'BUY' else entry - exit_p) * LOT_FULL * 100.0
                        realized -= SPREAD * LOT_FULL * 100.0
                    else:
                        # Runner stopped at breakeven area
                        realized = (exit_p - entry if ptype == 'BUY' else entry - exit_p) * LOT_HALF * 100.0
                        realized -= SPREAD * LOT_HALF * 100.0

            # Close position
            if reason is not None:
                total_pnl = realized
                capital       += total_pnl
                daily_pnl[day_k] += total_pnl
                monthly[month_k]['pnl']    += total_pnl
                monthly[month_k]['trades'] += 1
                if total_pnl > 0: monthly[month_k]['wins'] += 1

                all_trades.append({
                    'month': month_k,
                    'type': ptype,
                    'reason': reason,
                    'pnl': round(total_pnl, 2),
                    'win': total_pnl > 0,
                    'h4': pos['h4_bias'],
                    'score': pos['score'],
                    'partial': partial,
                    'capital': round(capital, 2)
                })
                pos = None

                if capital > peak_cap: peak_cap = capital
                dd = peak_cap - capital
                dd_pct = dd / peak_cap * 100 if peak_cap > 0 else 0
                if dd > max_dd_amt: max_dd_amt = dd
                if dd_pct > max_dd_pct: max_dd_pct = dd_pct

                if capital > monthly[month_k]['peak']:
                    monthly[month_k]['peak'] = capital
                mdd = monthly[month_k]['peak'] - capital
                if mdd > monthly[month_k]['max_dd']:
                    monthly[month_k]['max_dd'] = mdd
            continue

        # ─── Entry Signal ───
        # Session filter
        if hour not in SESSION_HOURS: continue

        # ATR volatility guard
        if atr < ATR_MIN or atr > ATR_MAX: continue

        # Daily loss limit
        if daily_pnl.get(day_k, 0.0) <= -(capital * DAILY_DD_PCT / 100.0): continue

        # H4 bias (skip ranging markets)
        h4_bias = get_h4_bias(dfh4, dt)
        if h4_bias == 'RANGE': continue

        # Score signal
        prev_slice = df.iloc[max(0, i-5):i]
        bs, ss = score_signal(row, prev_slice, h4_bias)

        trade_type = None
        score = 0
        if bs >= MIN_SCORE and bs > ss and h4_bias in ('BULL', 'BULL_WEAK'):
            trade_type = 'BUY'; score = bs
        elif ss >= MIN_SCORE and ss > bs and h4_bias in ('BEAR', 'BEAR_WEAK'):
            trade_type = 'SELL'; score = ss

        if trade_type is None: continue

        # Calculate levels
        sl_dist  = atr * ATR_SL_MULT
        tp1_dist = atr * ATR_TP1_MULT
        tp2_dist = atr * ATR_TP2_MULT

        # Minimum SL: $8 (in price units for XAUUSD)
        sl_dist = max(sl_dist, 8.0)

        # Enforce R:R ≥ 1.8
        if tp1_dist / sl_dist < 1.8: continue

        if trade_type == 'BUY':
            entry = cur_p + SPREAD / 2
            sl    = entry - sl_dist
            tp1   = entry + tp1_dist
            tp2   = entry + tp2_dist
        else:
            entry = cur_p - SPREAD / 2
            sl    = entry + sl_dist
            tp1   = entry - tp1_dist
            tp2   = entry - tp2_dist

        pos = {
            'type':     trade_type,
            'entry':    entry,
            'sl':       sl,
            'tp1':      tp1,
            'tp2':      tp2,
            'lot':      LOT_FULL,
            'partial':  False,
            'trail_sl': None,
            'h4_bias':  h4_bias,
            'score':    score,
            'open_dt':  dt
        }

    # ─── Print Report ───
    total  = len(all_trades)
    wins   = [t for t in all_trades if t['win']]
    losses = [t for t in all_trades if not t['win']]
    wr     = len(wins) / total * 100 if total > 0 else 0
    net    = capital - INITIAL_CAPITAL
    net_p  = net / INITIAL_CAPITAL * 100
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))
    pf     = round(gp / gl, 2) if gl > 0 else 99.0
    num_m  = len([m for m in monthly.values() if m['trades'] > 0])
    avg_m  = net_p / num_m if num_m else 0

    from collections import Counter
    exit_cnts = Counter(t['reason'] for t in all_trades)
    h4_cnts   = Counter(t['h4'] for t in all_trades)

    print("=" * 72)
    print("  🏆 SMART TREND SNIPER V3 — 1-YEAR BACKTEST RESULTS 🏆")
    print(f"  XAUUSD.iux | H1 Entry + H4 Bias | Lot 0.05 | Capital $1,000")
    print("=" * 72)
    print(f"💵 Initial Capital:        ${INITIAL_CAPITAL:,.2f} USD")
    print(f"💰 Final Balance:          ${capital:,.2f} USD")
    print(f"📈 Total Net Return:       ${net:+,.2f} USD ({net_p:+.2f}%)")
    print(f"🔥 Avg Monthly Return:     {avg_m:+.2f}%")
    print(f"📊 Profit Factor:          {pf}")
    print(f"🎯 Total Trades:           {total} ({total//12 if total>0 else 0}/month avg)")
    print(f"✅ Winners:                {len(wins)} ({wr:.1f}%)")
    print(f"❌ Losers:                 {len(losses)} ({100-wr:.1f}%)")
    print(f"🛡️ Max Drawdown:           ${max_dd_amt:,.2f} ({max_dd_pct:.2f}%)")
    print()
    print("EXIT BREAKDOWN:")
    for r, c in exit_cnts.most_common():
        rp = sum(t['pnl'] for t in all_trades if t['reason'] == r)
        print(f"  {r:<25}: {c:>3} trades | Net ${rp:+,.2f}")
    print()
    print("H4 BIAS BREAKDOWN:")
    for b, c in h4_cnts.most_common():
        bp = sum(t['pnl'] for t in all_trades if t['h4'] == b)
        print(f"  {b:<15}: {c:>3} trades | Net ${bp:+,.2f}")
    print("=" * 72)
    print("MONTH-BY-MONTH BREAKDOWN:")
    print(f"  {'Month':<13} | {'PnL ($)':>9} | {'Return%':>8} | {'Trades':>7} | {'WR%':>6} | {'MaxDD($)':>9}")
    print("  " + "-" * 60)

    month_labels = {
        '2025-10': 'Oct 2025', '2025-11': 'Nov 2025', '2025-12': 'Dec 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026',
        '2026-04': 'Apr 2026', '2026-05': 'May 2026', '2026-06': 'Jun 2026',
        '2026-07': 'Jul 2026', '2026-08': 'Aug 2026', '2026-09': 'Sep 2026',
    }

    for mk in sorted(monthly.keys()):
        md = monthly[mk]
        if md['trades'] == 0: continue
        m_ret = md['pnl'] / md['start_bal'] * 100 if md['start_bal'] > 0 else 0
        m_wr  = md['wins'] / md['trades'] * 100  if md['trades']   > 0 else 0
        label = month_labels.get(mk, mk)
        flag  = ' ✅' if m_ret >= 15 else (' 🟡' if m_ret >= 0 else ' ❌')
        print(f"  {label:<13} | ${md['pnl']:>8.2f} | {m_ret:>+7.2f}% | {md['trades']:>6}  | {m_wr:>5.1f}% | ${md['max_dd']:>7.2f}{flag}")

    # Verdict
    months_pos    = sum(1 for mk,md in monthly.items() if md['pnl'] > 0)
    months_target = sum(1 for mk,md in monthly.items() if md['trades'] > 0 and (md['pnl'] / (md['start_bal'] or 1)) * 100 >= 15)
    print("=" * 72)
    print(f"\n📋 FINAL VERDICT:")
    print(f"   Profitable months:   {months_pos}/{num_m}")
    print(f"   Hit 15%+ target:     {months_target}/{num_m} months")
    print(f"   Portfolio survived:  {'✅ YES — Portfolio INTACT' if capital > 500 else '❌ BLOWN'}")
    print(f"   Max DD < 20%:        {'✅ SAFE' if max_dd_pct < 20 else '⚠️  EXCEEDED'}")
    print(f"   Max DD < 30%:        {'✅ SAFE' if max_dd_pct < 30 else '⚠️  EXCEEDED'}")
    print("=" * 72)

if __name__ == '__main__':
    run_v3_backtest()
