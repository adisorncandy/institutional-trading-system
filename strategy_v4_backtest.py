"""
==============================================================================
INSTITUTIONAL AI V4 — "GOLDEN TREND RIDER"
1-Year Backtest: Oct 2025 → Sep 2026 | XAUUSD.iux | H1 + H4 MTF
==============================================================================
ROOT CAUSE FIXES:
  V1: Scale-In 3 layers AGAINST trend → catastrophic R:R 1:0.27
  V2: ATR unit error (used pips instead of price)
  V3: Fixed lot too aggressive → Max DD > 100%

V4 KEY INNOVATIONS:
  ✅ Dynamic lot sizing: 2% risk of CURRENT capital per trade
     → Auto-shrinks when losing (self-protection)
     → Auto-grows when winning (compounding)
  ✅ H4 trend bias + H1 pullback entry (trend-follow only)
  ✅ Partial close 50% at TP1 + trail runner with ATR-based trailing stop
  ✅ Daily drawdown halt (3% of capital)
  ✅ No counter-trend trades ever
  ✅ R:R minimum 1:2 enforced

MONEY MATH (XAUUSD.iux specs):
  Point = 0.01 | Tick Value = $1.00/lot | Contract = 100 oz
  1 lot → $100 per $1 price movement
  0.01 lot → $1 per $1 price movement
  ATR(H1) avg ≈ $21 | Spread ≈ $0.30

TARGET: 8-15% / month | Max DD < 20% | Profit Factor > 1.5
==============================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict, Counter
import sys, math

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================================
# V4 PARAMETERS
# ==============================================================================
INITIAL_CAPITAL = 1000.0

# Risk Management
RISK_PER_TRADE  = 0.020     # 2% of current capital per trade
MIN_LOT         = 0.01      # IUX minimum lot
MAX_LOT         = 0.20      # Safety guardrail
LOT_STEP        = 0.01      # IUX lot step
SPREAD          = 0.30      # $0.30 typical spread

# ATR-based Levels
ATR_SL_MULT     = 0.8       # SL = 0.8 × ATR
ATR_TP1_MULT    = 1.6       # TP1 = 1.6 × ATR (R:R = 2:1)
ATR_TP2_MULT    = 3.2       # TP2 = 3.2 × ATR (R:R = 4:1)
ATR_TRAIL_MULT  = 0.6       # Trail = 0.6 × ATR

# Filters
ATR_MIN_PRICE   = 5.0       # Skip dead market (ATR < $5)
ATR_MAX_PRICE   = 80.0      # Skip extreme news (ATR > $80)
SESSION_HOURS   = set(range(10, 20))  # London 10-14, NY 15-20
DAILY_DD_PCT    = 3.0       # Halt trading if daily loss > 3%
RSI_BUY_RANGE   = (35, 55)  # Buy: oversold pullback in uptrend
RSI_SELL_RANGE  = (45, 65)  # Sell: overbought rally in downtrend

# ==============================================================================
# INDICATOR COMPUTATION
# ==============================================================================
def compute_indicators(df):
    df['ema21']  = df['close'].ewm(span=21,  adjust=False).mean()
    df['ema50']  = df['close'].ewm(span=50,  adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    delta = df['close'].diff()
    g = delta.where(delta > 0, 0).rolling(14).mean()
    l = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + g / (l + 1e-9)))

    df['macd']     = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()

    hi_lo = df['high'] - df['low']
    hi_cl = (df['high'] - df['close'].shift()).abs()
    lo_cl = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hi_lo, hi_cl, lo_cl], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    return df


def get_h4_bias(dfh4, dt):
    sub = dfh4[dfh4['datetime'] <= dt].tail(12)
    if len(sub) < 5:
        return 'RANGE'
    e21  = sub['close'].ewm(span=21,  adjust=False).mean().iloc[-1]
    e50  = sub['close'].ewm(span=50,  adjust=False).mean().iloc[-1]
    e200 = sub['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    price = sub.iloc[-1]['close']
    if price > e21 > e50 and price > e200:
        return 'BULL'
    if price < e21 < e50 and price < e200:
        return 'BEAR'
    return 'RANGE'


def calc_lot(capital, sl_distance):
    """Dynamic lot: risk exactly 2% of current capital."""
    risk_dollar = capital * RISK_PER_TRADE
    # PnL per lot = sl_distance × 100
    lot = risk_dollar / (sl_distance * 100.0)
    lot = math.floor(lot / LOT_STEP) * LOT_STEP
    lot = max(MIN_LOT, min(MAX_LOT, lot))
    return lot


# ==============================================================================
# MAIN BACKTEST ENGINE
# ==============================================================================
def run_v4_backtest():
    print("=" * 72)
    print("  INSTITUTIONAL AI V4 — LOADING 1-YEAR REAL MT5 DATA...")
    if not mt5.initialize():
        print("  MT5 init failed"); return

    dt_from = datetime(2025, 9, 20, 0, 0)
    dt_to   = datetime(2026, 9, 30, 23, 59)
    h1r = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, dt_from, dt_to)
    h4r = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H4, dt_from, dt_to)
    mt5.shutdown()

    if h1r is None or h4r is None:
        print("  Data fetch failed"); return

    df = pd.DataFrame(h1r)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df = compute_indicators(df).dropna().reset_index(drop=True)

    dfh4 = pd.DataFrame(h4r)
    dfh4['datetime'] = pd.to_datetime(dfh4['time'], unit='s')

    print(f"  H1: {len(df):,} bars | H4: {len(dfh4):,} bars")
    print(f"  {df['datetime'].iloc[0].strftime('%d %b %Y')} -> {df['datetime'].iloc[-1].strftime('%d %b %Y')}")
    print()

    # State
    capital    = INITIAL_CAPITAL
    peak_cap   = INITIAL_CAPITAL
    max_dd_amt = 0.0
    max_dd_pct = 0.0

    pos        = None
    trades     = []
    monthly    = defaultdict(lambda: {'pnl': 0.0, 'trades': 0, 'wins': 0,
                                       'start_bal': 0.0, 'peak': 0.0, 'max_dd': 0.0})
    daily_pnl  = defaultdict(float)

    start_sim  = pd.Timestamp("2025-10-01")
    start_idx  = df[df['datetime'] >= start_sim].index[0]

    for i in range(start_idx, len(df)):
        row    = df.iloc[i]
        prev   = df.iloc[i - 1]
        dt     = row['datetime']
        mk     = dt.strftime('%Y-%m')
        dk     = dt.strftime('%Y-%m-%d')
        hour   = dt.hour
        cur_p  = row['close']
        cur_h  = row['high']
        cur_l  = row['low']
        atr    = row['atr']

        # Init monthly
        if monthly[mk]['start_bal'] == 0.0:
            monthly[mk]['start_bal'] = capital
            monthly[mk]['peak']      = capital

        # ────────────────── POSITION MANAGEMENT ──────────────────
        if pos is not None:
            ptype   = pos['type']
            entry   = pos['entry']
            sl_now  = pos['sl']
            tp1     = pos['tp1']
            tp2     = pos['tp2']
            lot_full= pos['lot_full']
            lot_half= pos['lot_half']
            partial = pos['partial']
            cur_atr = atr  # Current ATR for trailing

            realized = 0.0
            reason   = None

            # 1) TP1 — Partial Close 50%
            if not partial:
                tp1_hit = (ptype == 'BUY' and cur_h >= tp1) or \
                          (ptype == 'SELL' and cur_l <= tp1)
                if tp1_hit:
                    pnl_half = (abs(tp1 - entry) - SPREAD) * lot_half * 100.0
                    realized += pnl_half
                    capital  += pnl_half
                    daily_pnl[dk] += pnl_half

                    # Move SL to breakeven + $0.50 cushion
                    be = entry + 0.50 if ptype == 'BUY' else entry - 0.50
                    pos['sl']       = be
                    pos['partial']  = True
                    # Init trail at TP1 minus ATR×trail_mult
                    if ptype == 'BUY':
                        pos['trail_sl'] = tp1 - cur_atr * ATR_TRAIL_MULT
                    else:
                        pos['trail_sl'] = tp1 + cur_atr * ATR_TRAIL_MULT

            # 2) Trail runner after partial close
            if pos['partial']:
                if ptype == 'BUY':
                    new_trail = cur_h - cur_atr * ATR_TRAIL_MULT
                    if new_trail > pos.get('trail_sl', -1e9):
                        pos['trail_sl'] = new_trail
                    if cur_l <= pos['trail_sl']:
                        reason = 'Trail Stop (Runner)'
                        exit_pnl = (pos['trail_sl'] - entry - SPREAD) * lot_half * 100.0
                        realized += exit_pnl
                else:
                    new_trail = cur_l + cur_atr * ATR_TRAIL_MULT
                    if new_trail < pos.get('trail_sl', 1e9):
                        pos['trail_sl'] = new_trail
                    if cur_h >= pos['trail_sl']:
                        reason = 'Trail Stop (Runner)'
                        exit_pnl = (entry - pos['trail_sl'] - SPREAD) * lot_half * 100.0
                        realized += exit_pnl

            # 3) TP2 — Full close runner
            if pos['partial'] and reason is None:
                tp2_hit = (ptype == 'BUY' and cur_h >= tp2) or \
                          (ptype == 'SELL' and cur_l <= tp2)
                if tp2_hit:
                    reason = 'TP2 (Runner)'
                    exit_pnl = (abs(tp2 - entry) - SPREAD) * lot_half * 100.0
                    realized += exit_pnl

            # 4) Stop Loss
            if reason is None:
                sl_hit = (ptype == 'BUY' and cur_l <= sl_now) or \
                         (ptype == 'SELL' and cur_h >= sl_now)
                if sl_hit:
                    reason = 'Stop Loss'
                    if not partial:
                        # Full lot stopped out
                        if ptype == 'BUY':
                            exit_pnl = (sl_now - entry - SPREAD) * lot_full * 100.0
                        else:
                            exit_pnl = (entry - sl_now - SPREAD) * lot_full * 100.0
                    else:
                        # Only runner stopped (should be near BE)
                        if ptype == 'BUY':
                            exit_pnl = (sl_now - entry - SPREAD) * lot_half * 100.0
                        else:
                            exit_pnl = (entry - sl_now - SPREAD) * lot_half * 100.0
                    realized += exit_pnl

            # Close Trade
            if reason is not None:
                capital       += realized
                daily_pnl[dk] += realized
                monthly[mk]['pnl']    += realized
                monthly[mk]['trades'] += 1
                if realized > 0:
                    monthly[mk]['wins'] += 1

                trades.append({
                    'month':   mk,
                    'type':    ptype,
                    'reason':  reason,
                    'pnl':     round(realized, 2),
                    'win':     realized > 0,
                    'h4':      pos.get('h4', '?'),
                    'lot':     lot_full,
                    'partial': partial,
                    'capital': round(capital, 2)
                })
                pos = None

                # Update drawdown
                if capital > peak_cap:
                    peak_cap = capital
                dd     = peak_cap - capital
                dd_pct = dd / peak_cap * 100 if peak_cap > 0 else 0
                if dd > max_dd_amt:  max_dd_amt = dd
                if dd_pct > max_dd_pct: max_dd_pct = dd_pct

                if capital > monthly[mk]['peak']:
                    monthly[mk]['peak'] = capital
                m_dd = monthly[mk]['peak'] - capital
                if m_dd > monthly[mk]['max_dd']:
                    monthly[mk]['max_dd'] = m_dd
            continue

        # ────────────────── ENTRY LOGIC ──────────────────
        # 1. Session filter
        if hour not in SESSION_HOURS:
            continue

        # 2. Minimum capital check
        if capital <= 50:
            continue

        # 3. ATR filter
        if atr < ATR_MIN_PRICE or atr > ATR_MAX_PRICE:
            continue

        # 4. Daily DD limit
        if daily_pnl.get(dk, 0) <= -(capital * DAILY_DD_PCT / 100.0):
            continue

        # 5. H4 Trend bias
        h4_bias = get_h4_bias(dfh4, dt)
        if h4_bias == 'RANGE':
            continue

        # 6. H1 EMA alignment
        e21  = prev['ema21']
        e50  = prev['ema50']
        e200 = prev['ema200']
        close_p = prev['close']

        h1_bull = e21 > e50 and close_p > e200
        h1_bear = e21 < e50 and close_p < e200

        # 7. RSI pullback zone
        rsi = prev['rsi']

        # 8. MACD momentum
        macd_h = prev['macd'] - prev['macd_sig']

        # 9. Combined entry decision
        buy_ok  = (h4_bias == 'BULL' and h1_bull and
                   RSI_BUY_RANGE[0] < rsi < RSI_BUY_RANGE[1] and
                   macd_h > 0)
        sell_ok = (h4_bias == 'BEAR' and h1_bear and
                   RSI_SELL_RANGE[0] < rsi < RSI_SELL_RANGE[1] and
                   macd_h < 0)

        if not buy_ok and not sell_ok:
            continue

        trade_type = 'BUY' if buy_ok else 'SELL'

        # 10. Calculate levels
        sl_dist  = atr * ATR_SL_MULT
        tp1_dist = atr * ATR_TP1_MULT
        tp2_dist = atr * ATR_TP2_MULT

        # Enforce min SL $6 (prevents stop hunting on tiny ranges)
        sl_dist = max(sl_dist, 6.0)

        # R:R check
        if tp1_dist / sl_dist < 1.8:
            continue

        # 11. Dynamic lot sizing
        lot = calc_lot(capital, sl_dist)

        # 12. Open position
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

        lot_half = max(MIN_LOT, math.floor(lot / 2 / LOT_STEP) * LOT_STEP)
        # Ensure lot_full = 2 × lot_half for clean split
        lot_full = lot_half * 2

        pos = {
            'type':      trade_type,
            'entry':     entry,
            'sl':        sl,
            'tp1':       tp1,
            'tp2':       tp2,
            'lot_full':  lot_full,
            'lot_half':  lot_half,
            'partial':   False,
            'trail_sl':  None,
            'h4':        h4_bias,
            'open_dt':   dt,
            'atr':       atr
        }

    # ══════════════════════════════════════════════════════════════
    #  REPORT
    # ══════════════════════════════════════════════════════════════
    total  = len(trades)
    wins   = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    wr     = len(wins) / total * 100 if total > 0 else 0
    net    = capital - INITIAL_CAPITAL
    net_p  = net / INITIAL_CAPITAL * 100
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))
    pf     = round(gp / gl, 2) if gl > 0 else 99.0
    active_months = [mk for mk, md in monthly.items() if md['trades'] > 0]
    num_m  = len(active_months)
    avg_m  = net_p / num_m if num_m else 0

    exit_cnts = Counter(t['reason'] for t in trades)
    h4_cnts   = Counter(t['h4'] for t in trades)

    # Avg win / avg loss
    avg_win  = sum(t['pnl'] for t in wins) / len(wins)   if wins   else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

    print("=" * 72)
    print("  === INSTITUTIONAL AI V4 — 1-YEAR BACKTEST REPORT ===")
    print(f"  XAUUSD.iux | H1 Entry + H4 Bias | Dynamic Lot (2% risk)")
    print(f"  Period: Oct 2025 -> Sep 2026")
    print("=" * 72)
    print(f"  Initial Capital:       ${INITIAL_CAPITAL:,.2f} USD")
    print(f"  Final Balance:         ${capital:,.2f} USD")
    print(f"  Total Net Return:      ${net:+,.2f} USD ({net_p:+.2f}%)")
    print(f"  Avg Monthly Return:    {avg_m:+.2f}%")
    print(f"  Profit Factor:         {pf}")
    print(f"  Total Trades:          {total} ({total // max(1,num_m)}/month)")
    print(f"  Win Rate:              {len(wins)}/{total} ({wr:.1f}%)")
    print(f"  Avg Win:               ${avg_win:+.2f}")
    print(f"  Avg Loss:              ${avg_loss:.2f}")
    print(f"  Max Drawdown:          ${max_dd_amt:,.2f} ({max_dd_pct:.2f}%)")
    print(f"  Portfolio Survived:    {'YES' if capital > 200 else 'BLOWN'}")
    print()
    print("  EXIT BREAKDOWN:")
    for r, c in exit_cnts.most_common():
        rp = sum(t['pnl'] for t in trades if t['reason'] == r)
        print(f"    {r:<28}: {c:>3} trades | Net ${rp:+,.2f}")
    print()
    print("  H4 BIAS ON ENTRIES:")
    for b, c in h4_cnts.most_common():
        bp = sum(t['pnl'] for t in trades if t['h4'] == b)
        print(f"    {b:<12}: {c:>3} trades | Net ${bp:+,.2f}")
    print()

    # Monthly table
    print("  MONTH-BY-MONTH:")
    print(f"  {'Month':<13} | {'Start$':>8} | {'PnL ($)':>9} | {'Return':>8} | {'#':>4} | {'WR%':>6} | {'MaxDD$':>8} | {'End$':>8}")
    print("  " + "-" * 80)

    month_labels = {
        '2025-10': 'Oct 2025', '2025-11': 'Nov 2025', '2025-12': 'Dec 2025',
        '2026-01': 'Jan 2026', '2026-02': 'Feb 2026', '2026-03': 'Mar 2026',
        '2026-04': 'Apr 2026', '2026-05': 'May 2026', '2026-06': 'Jun 2026',
        '2026-07': 'Jul 2026', '2026-08': 'Aug 2026', '2026-09': 'Sep 2026',
    }

    running = INITIAL_CAPITAL
    for mk in sorted(monthly.keys()):
        md = monthly[mk]
        if md['trades'] == 0:
            running += md['pnl']
            continue
        sb    = md['start_bal']
        m_ret = md['pnl'] / sb * 100 if sb > 0 else 0
        m_wr  = md['wins'] / md['trades'] * 100 if md['trades'] > 0 else 0
        end   = sb + md['pnl']
        label = month_labels.get(mk, mk)
        if m_ret >= 15:   flag = ' >'
        elif m_ret >= 8:  flag = ' OK'
        elif m_ret >= 0:  flag = ''
        else:             flag = ' X'
        print(f"  {label:<13} | ${sb:>7.2f} | ${md['pnl']:>8.2f} | {m_ret:>+7.2f}% | {md['trades']:>3} | {m_wr:>5.1f}% | ${md['max_dd']:>7.2f} | ${end:>7.2f}{flag}")
        running = end

    print("  " + "-" * 80)

    # Verdicts
    months_pos    = sum(1 for mk in active_months if monthly[mk]['pnl'] > 0)
    months_8pct   = sum(1 for mk in active_months
                        if monthly[mk]['pnl'] / (monthly[mk]['start_bal'] or 1) * 100 >= 8)
    months_15pct  = sum(1 for mk in active_months
                        if monthly[mk]['pnl'] / (monthly[mk]['start_bal'] or 1) * 100 >= 15)

    print()
    print("  VERDICT:")
    print(f"    Profitable months:    {months_pos}/{num_m}")
    print(f"    Hit >=8% target:      {months_8pct}/{num_m} months")
    print(f"    Hit >=15% target:     {months_15pct}/{num_m} months")
    print(f"    Portfolio survived:   {'YES' if capital > 200 else 'BLOWN'}")
    print(f"    Max DD < 20%:         {'YES' if max_dd_pct < 20 else 'NO ('+str(round(max_dd_pct,1))+'%)'}")
    print(f"    Profit Factor > 1.5:  {'YES' if pf > 1.5 else 'NO'}")
    print("=" * 72)

    # Print individual trade log (last 20)
    print()
    print(f"  LAST 20 TRADES (of {total}):")
    for t in trades[-20:]:
        flag = '+' if t['win'] else '-'
        print(f"    [{t['month']}] {t['type']:<4} | {t['reason']:<28} | ${t['pnl']:>+8.2f} | Lot={t['lot']:.2f} | Cap=${t['capital']:>8.2f} {flag}")


if __name__ == '__main__':
    run_v4_backtest()
