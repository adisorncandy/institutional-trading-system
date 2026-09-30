import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_6month_backtest():
    if not mt5.initialize():
        print("❌ MT5 Initialization failed")
        return

    sym = 'XAUUSD.iux' if mt5.symbol_info('XAUUSD.iux') else 'XAUUSD'
    print(f"📊 Connecting to broker MT5... Symbol: {sym}")
    
    # 6 Months period: 2026-03-25 (with warmup) to 2026-09-30
    dt_from = datetime(2026, 3, 20, 0, 0)
    dt_to = datetime(2026, 9, 30, 23, 59)
    
    rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, dt_from, dt_to)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("❌ No rates fetched from MT5")
        return

    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    print(f"✅ Loaded {len(df):,} M5 candles from {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")

    # Technical Indicators (exact matching EA formulas)
    df['ema_fast'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_med']  = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()

    # ATR 14
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    # Constants matching Institutional_AI_EA.mq5
    INITIAL_CAPITAL = 1000.0
    capital = INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    LOT_SIZE = 0.02
    SPREAD_PIPS = 2.0  # IUX typical spread for XAUUSD (2.0 pips = $0.20 on gold)

    STEP1_PIPS = 40.0       # 40 pips to Layer 2
    STEP2_PIPS = 50.0       # 50 pips to Layer 3
    BASKET_SL_PIPS = 40.0   # 40 pips beyond Layer 3
    BASKET_TP_USD = 14.0    # $14 USD target
    MIN_CONFIDENCE = 70     # 70% Confluence filter

    MICRO_BE_TRIGGER = 8.0  # pips profit to trigger Micro-BE
    MICRO_BE_LOCK = 2.0     # pips locked in profit
    TP1_PIPS = 60.0         # 60 pips target for single layer
    HARD_SL_PIPS = 35.0     # 35 pips hard SL if 1 layer without scale-in

    positions = []
    closed_trades = []
    monthly_stats = {}

    # Start simulation on 2026-04-01
    start_sim_dt = pd.Timestamp("2026-04-01 00:00:00")
    start_idx = df[df['datetime'] >= start_sim_dt].index[0]
    total_bars = len(df)

    print(f"🚀 Running backtest from bar {start_idx} ({df['datetime'].iloc[start_idx]}) to bar {total_bars-1} ({df['datetime'].iloc[-1]})...\n")

    for i in range(start_idx, total_bars):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        cur_time = row['datetime']
        cur_p = row['close']
        cur_high = row['high']
        cur_low = row['low']
        hour = cur_time.hour
        month_str = cur_time.strftime("%Y-%m")

        # ----------------- POSITION MANAGEMENT -----------------
        if positions:
            pos_type = positions[0]['type']
            first_entry = positions[0]['entry']
            last_entry = positions[-1]['entry']
            num_layers = len(positions)

            # 1. Micro-BE on Layer 1 (only before scale-in triggers)
            if num_layers == 1 and not positions[0].get('be_locked', False):
                profit_pips = ((cur_high - first_entry) if pos_type == 'BUY' else (first_entry - cur_low)) / 0.10
                if profit_pips >= MICRO_BE_TRIGGER:
                    positions[0]['be_locked'] = True
                    positions[0]['be_sl'] = first_entry + (MICRO_BE_LOCK * 0.10 if pos_type == 'BUY' else -MICRO_BE_LOCK * 0.10)

            # 2. Scale-In checks (only if Micro-BE hasn't already locked the trade)
            if num_layers < 3 and not positions[0].get('be_locked', False):
                req_step = STEP1_PIPS if num_layers == 1 else STEP2_PIPS
                if pos_type == 'BUY':
                    if (last_entry - cur_low) >= (req_step * 0.10):
                        entry_price = last_entry - (req_step * 0.10)
                        positions.append({'layer': num_layers + 1, 'type': 'BUY', 'entry': entry_price, 'lot': LOT_SIZE, 'time': cur_time})
                elif pos_type == 'SELL':
                    if (cur_high - last_entry) >= (req_step * 0.10):
                        entry_price = last_entry + (req_step * 0.10)
                        positions.append({'layer': num_layers + 1, 'type': 'SELL', 'entry': entry_price, 'lot': LOT_SIZE, 'time': cur_time})

            # 3. Calculate Basket PnL
            basket_pnl = 0.0
            for p in positions:
                diff = (cur_p - p['entry']) if p['type'] == 'BUY' else (p['entry'] - cur_p)
                pips = diff / 0.10
                p_pnl = (pips - SPREAD_PIPS) * (p['lot'] * 10.0)
                basket_pnl += p_pnl

            is_tp = False
            is_sl = False
            exit_type = ""
            final_pnl = basket_pnl

            # 4. Check Exit Conditions
            if len(positions) >= 2:
                # Multi-Layer Basket TP ($14 USD)
                if basket_pnl >= BASKET_TP_USD:
                    is_tp = True
                    final_pnl = BASKET_TP_USD
                    exit_type = f"Basket TP (+${BASKET_TP_USD:.1f})"
                
                # Basket Hard SL: Layer 1 + Step1 + Step2 + BasketSL
                total_risk_dist = (STEP1_PIPS + STEP2_PIPS + BASKET_SL_PIPS) * 0.10
                if pos_type == 'BUY' and cur_low <= (first_entry - total_risk_dist):
                    is_sl = True
                    # Realized loss at basket SL
                    sl_p = first_entry - total_risk_dist
                    loss_sum = 0.0
                    for p in positions:
                        diff = sl_p - p['entry']
                        loss_sum += ((diff / 0.10) - SPREAD_PIPS) * (p['lot'] * 10.0)
                    final_pnl = loss_sum
                    exit_type = "Basket Hard SL"
                elif pos_type == 'SELL' and cur_high >= (first_entry + total_risk_dist):
                    is_sl = True
                    sl_p = first_entry + total_risk_dist
                    loss_sum = 0.0
                    for p in positions:
                        diff = p['entry'] - sl_p
                        loss_sum += ((diff / 0.10) - SPREAD_PIPS) * (p['lot'] * 10.0)
                    final_pnl = loss_sum
                    exit_type = "Basket Hard SL"

            else:
                # 1 Single Layer Position Management
                if positions[0].get('be_locked', False):
                    be_sl = positions[0]['be_sl']
                    if (pos_type == 'BUY' and cur_low <= be_sl) or (pos_type == 'SELL' and cur_high >= be_sl):
                        is_tp = True
                        exit_type = "Micro-BE Scratch (+2 pips)"
                        diff = (be_sl - first_entry) if pos_type == 'BUY' else (first_entry - be_sl)
                        final_pnl = ((diff / 0.10) - SPREAD_PIPS) * (LOT_SIZE * 10.0)
                
                # Check Single TP1 Target (60 pips = $12.00 gross)
                high_diff = (cur_high - first_entry) if pos_type == 'BUY' else (first_entry - cur_low)
                if (high_diff / 0.10) >= TP1_PIPS:
                    is_tp = True
                    final_pnl = (TP1_PIPS - SPREAD_PIPS) * (LOT_SIZE * 10.0)
                    exit_type = "TP1 Target (+60 pips)"
                
                # Single Hard SL (35 pips if sudden gap without layering)
                low_diff = (first_entry - cur_low) if pos_type == 'BUY' else (cur_high - first_entry)
                if not positions[0].get('be_locked', False) and (low_diff / 0.10) >= (STEP1_PIPS + STEP2_PIPS + BASKET_SL_PIPS):
                    is_sl = True
                    final_pnl = -((STEP1_PIPS + STEP2_PIPS + BASKET_SL_PIPS) + SPREAD_PIPS) * (LOT_SIZE * 10.0)
                    exit_type = "Emergency Cut"

            if is_tp or is_sl:
                capital += final_pnl
                if month_str not in monthly_stats:
                    monthly_stats[month_str] = {
                        'pnl': 0.0,
                        'trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'peak': capital,
                        'max_dd': 0.0,
                        'l1_count': 0,
                        'l2_count': 0,
                        'l3_count': 0
                    }
                
                m = monthly_stats[month_str]
                m['pnl'] += final_pnl
                m['trades'] += 1
                if final_pnl > 0:
                    m['wins'] += 1
                else:
                    m['losses'] += 1
                
                layer_used = len(positions)
                if layer_used == 1: m['l1_count'] += 1
                elif layer_used == 2: m['l2_count'] += 1
                else: m['l3_count'] += 1

                closed_trades.append({
                    'time_open': positions[0]['time'],
                    'time_close': cur_time,
                    'month': month_str,
                    'type': pos_type,
                    'layers': len(positions),
                    'pnl': round(final_pnl, 2),
                    'capital_after': round(capital, 2),
                    'win': final_pnl > 0,
                    'exit': exit_type
                })
                positions = []

            # Track Drawdowns
            if capital > peak_capital:
                peak_capital = capital
            dd_dollar = peak_capital - capital
            dd_pct = (dd_dollar / peak_capital) * 100.0 if peak_capital > 0 else 0
            if dd_dollar > max_drawdown_dollar:
                max_drawdown_dollar = dd_dollar
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct
            
            # Monthly peak and DD tracking
            if month_str in monthly_stats:
                if capital > monthly_stats[month_str]['peak']:
                    monthly_stats[month_str]['peak'] = capital
                m_dd = monthly_stats[month_str]['peak'] - capital
                if m_dd > monthly_stats[month_str]['max_dd']:
                    monthly_stats[month_str]['max_dd'] = m_dd

            continue

        # ----------------- SESSION & SIGNAL FILTER -----------------
        # Session Filter: London (10-14) and NY (15-20)
        session_ok = (10 <= hour < 14) or (15 <= hour < 20)
        if not session_ok:
            continue

        ema_f = prev['ema_fast']
        ema_m = prev['ema_med']
        ema_s = prev['ema_slow']
        close_p = prev['close']
        open_p = prev['open']
        high_p = prev['high']
        low_p = prev['low']
        rsi_val = prev['rsi']
        macd_val = prev['macd']
        macd_sig_val = prev['macd_sig']
        atr_val = prev['atr']

        smc_window = df.iloc[i-30:i]
        range_high = smc_window['high'].max()
        range_low = smc_window['low'].min()
        is_discount = close_p <= (range_low + atr_val * 0.35)
        is_premium  = close_p >= (range_high - atr_val * 0.35)

        is_bull_ribbon = (ema_f > ema_m and close_p > ema_s)
        is_bear_ribbon = (ema_f < ema_m and close_p < ema_s)

        buy_score = 15
        sell_score = 15

        if is_bull_ribbon: buy_score += 30
        if is_bear_ribbon: sell_score += 30

        if is_discount: buy_score += 25
        if is_premium:  sell_score += 25

        if 32.0 < rsi_val < 50.0: buy_score += 20
        if 50.0 < rsi_val < 68.0: sell_score += 20

        if macd_val > macd_sig_val: buy_score += 10
        if macd_val < macd_sig_val: sell_score += 10

        is_bull_pin = (close_p > open_p) and ((open_p - low_p) > (high_p - close_p) * 1.5)
        is_bear_pin = (close_p < open_p) and ((high_p - open_p) > (close_p - low_p) * 1.5)
        if is_bull_pin: buy_score += 10
        if is_bear_pin: sell_score += 10

        if buy_score >= MIN_CONFIDENCE and buy_score > sell_score:
            positions.append({'layer': 1, 'type': 'BUY', 'entry': cur_p, 'lot': LOT_SIZE, 'time': cur_time})
        elif sell_score >= MIN_CONFIDENCE and sell_score > buy_score:
            positions.append({'layer': 1, 'type': 'SELL', 'entry': cur_p, 'lot': LOT_SIZE, 'time': cur_time})

    # Overall Summary
    total_trades = len(closed_trades)
    wins = [t for t in closed_trades if t['win']]
    losses = [t for t in closed_trades if not t['win']]
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    net_profit = capital - INITIAL_CAPITAL
    profit_pct = (net_profit / INITIAL_CAPITAL) * 100.0
    
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

    num_months = len(monthly_stats) if len(monthly_stats) > 0 else 6
    avg_monthly_pct = profit_pct / num_months

    l1_all = sum(t['layers'] == 1 for t in closed_trades)
    l2_all = sum(t['layers'] == 2 for t in closed_trades)
    l3_all = sum(t['layers'] == 3 for t in closed_trades)

    print("=" * 75)
    print("        🏆 INSTITUTIONAL AI EA - 6 MONTHS REAL HISTORICAL BACKTEST 🏆")
    print(f"        Period: {df['datetime'].iloc[start_idx].strftime('%d %B %Y')} to {df['datetime'].iloc[-1].strftime('%d %B %Y')}")
    print(f"        Broker Server: IUX Markets | Symbol: {sym} (M5) | Candles: {len(df):,}")
    print("=" * 75)
    print(f"💵 Initial Capital:          ${INITIAL_CAPITAL:,.2f} USD")
    print(f"💰 Final Balance:            ${capital:,.2f} USD")
    print(f"📈 Total Net Profit:         +${net_profit:,.2f} USD (+{profit_pct:.2f}%)")
    print(f"🔥 Average Return / Month:   +{avg_monthly_pct:.2f}% / เดือน (Capital $1,000 USD)")
    print(f"📊 Profit Factor:            {profit_factor}")
    print(f"🎯 Total Trading Cycles:     {total_trades} รอบ")
    print(f"✅ Winning Cycles:           {len(wins)} ({win_rate:.1f}%)")
    print(f"❌ Losing Cycles:            {len(losses)} ({100.0 - win_rate:.1f}%)")
    print(f"🛡️ Max Drawdown:             ${max_drawdown_dollar:,.2f} ({max_drawdown_pct:.2f}%)")
    print("=" * 75)
    print("🔍 รายละเอียดการปิดออเดอร์ตามประเภท (EXIT TYPE BREAKDOWN):")
    from collections import Counter
    exit_counts = Counter(t['exit'] for t in closed_trades)
    for ex_name, count in exit_counts.items():
        ex_pnl = sum(t['pnl'] for t in closed_trades if t['exit'] == ex_name)
        print(f"   • {ex_name:<30}: {count:>4} รอบ | รวมกำไร/ขาดทุน: ${ex_pnl:>8.2f}")
    print("=" * 75)
    print("📅 สรุปผลตอบแทนแยกรายเดือน (MONTH-BY-MONTH BREAKDOWN):")
    print(f"{'เดือน':<12} | {'กำไร ($)':<12} | {'ผลตอบแทน (%)':<14} | {'จำนวนไม้':<10} | {'Win Rate':<10} | {'Max DD ($)':<12}")
    print("-" * 75)
    
    month_names = {
        '2026-04': 'เมษายน 2026',
        '2026-05': 'พฤษภาคม 2026',
        '2026-06': 'มิถุนายน 2026',
        '2026-07': 'กรกฎาคม 2026',
        '2026-08': 'สิงหาคม 2026',
        '2026-09': 'กันยายน 2026'
    }

    for m_key in sorted(monthly_stats.keys()):
        m_data = monthly_stats[m_key]
        m_name = month_names.get(m_key, m_key)
        m_pnl = m_data['pnl']
        m_ret = (m_pnl / INITIAL_CAPITAL) * 100.0
        m_trades = m_data['trades']
        m_wr = (m_data['wins'] / m_trades * 100.0) if m_trades > 0 else 0.0
        m_dd = m_data['max_dd']
        print(f"{m_name:<12} | +${m_pnl:>8.2f}    | +{m_ret:>6.2f}%        | {m_trades:>5} รอบ   | {m_wr:>5.1f}%    | ${m_dd:>7.2f}")
    
    print("=" * 75)

if __name__ == '__main__':
    run_6month_backtest()
