import MetaTrader5 as mt5
import pandas as pd

def run_realistic_ea_backtest():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    sym = 'XAUUSD.iux' if mt5.symbol_info('XAUUSD.iux') else 'XAUUSD'
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 12000)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("No rates fetched")
        return

    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    
    # Technical Indicators
    df['ema_fast'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_med']  = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()

    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()

    INITIAL_CAPITAL = 1000.0
    capital = INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    LOT_SIZE = 0.02
    SPREAD_PIPS = 2.0  # Real IUX average spread

    STEP1_PIPS = 40.0
    STEP2_PIPS = 50.0
    BASKET_SL_PIPS = 40.0
    BASKET_TP_USD = 14.0
    MIN_CONFIDENCE = 70

    MICRO_BE_TRIGGER = 8.0 # pips
    MICRO_BE_LOCK = 2.0 # pips

    positions = []
    closed_trades = []
    daily_pnl = {}
    
    start_idx = 250
    total_bars = len(df)

    for i in range(start_idx, total_bars):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        cur_time = row['datetime']
        cur_p = row['close']
        cur_high = row['high']
        cur_low = row['low']
        hour = cur_time.hour
        day_str = cur_time.strftime("%Y-%m-%d")

        if positions:
            pos_type = positions[0]['type']
            first_entry = positions[0]['entry']
            last_entry = positions[-1]['entry']
            num_layers = len(positions)

            # Micro-BE on Layer 1 before scaling in
            if num_layers == 1 and not positions[0].get('be_locked', False):
                profit_pips = ((cur_high - first_entry) if pos_type == 'BUY' else (first_entry - cur_low)) / 0.10
                if profit_pips >= MICRO_BE_TRIGGER:
                    positions[0]['be_locked'] = True
                    positions[0]['be_sl'] = first_entry + (MICRO_BE_LOCK * 0.10 if pos_type == 'BUY' else -MICRO_BE_LOCK * 0.10)

            # Scale-In check (only if BE not locked)
            if num_layers < 3 and not positions[0].get('be_locked', False):
                req_step = STEP1_PIPS if num_layers == 1 else STEP2_PIPS
                if pos_type == 'BUY':
                    if (last_entry - cur_p) >= (req_step * 0.10):
                        positions.append({'layer': num_layers + 1, 'type': 'BUY', 'entry': cur_p, 'lot': LOT_SIZE, 'time': cur_time})
                elif pos_type == 'SELL':
                    if (cur_p - last_entry) >= (req_step * 0.10):
                        positions.append({'layer': num_layers + 1, 'type': 'SELL', 'entry': cur_p, 'lot': LOT_SIZE, 'time': cur_time})

            # Check exits
            basket_pnl = 0.0
            for p in positions:
                diff = (cur_p - p['entry']) if p['type'] == 'BUY' else (p['entry'] - cur_p)
                pips = diff / 0.10
                p_pnl = (pips - SPREAD_PIPS) * (p['lot'] * 10.0)
                basket_pnl += p_pnl

            is_tp = False
            is_sl = False
            exit_type = ""

            if len(positions) >= 2:
                if basket_pnl >= BASKET_TP_USD:
                    is_tp = True
                    exit_type = "Basket TP"
                total_risk_dist = (STEP1_PIPS + STEP2_PIPS + BASKET_SL_PIPS) * 0.10
                if pos_type == 'BUY' and cur_low <= (first_entry - total_risk_dist):
                    is_sl = True
                    exit_type = "Basket Hard SL"
                elif pos_type == 'SELL' and cur_high >= (first_entry + total_risk_dist):
                    is_sl = True
                    exit_type = "Basket Hard SL"
            else:
                # 1 Layer: Check Micro-BE hit
                if positions[0].get('be_locked', False):
                    be_sl = positions[0]['be_sl']
                    if (pos_type == 'BUY' and cur_low <= be_sl) or (pos_type == 'SELL' and cur_high >= be_sl):
                        is_tp = True # Scratch profit (+2 pips)
                        exit_type = "Micro-BE Scratch"
                        diff = (be_sl - first_entry) if pos_type == 'BUY' else (first_entry - be_sl)
                        basket_pnl = ((diff / 0.10) - SPREAD_PIPS) * (LOT_SIZE * 10.0)
                
                # Check TP1: 60 pips
                diff = (cur_p - first_entry) if pos_type == 'BUY' else (first_entry - cur_p)
                if diff >= 6.0:
                    is_tp = True
                    exit_type = "TP1 Target"
                elif (first_entry - cur_p if pos_type == 'BUY' else cur_p - first_entry) >= 13.0:
                    is_sl = True
                    exit_type = "Hard SL"

            if is_tp or is_sl:
                capital += basket_pnl
                daily_pnl[day_str] = daily_pnl.get(day_str, 0.0) + basket_pnl
                closed_trades.append({
                    'time_open': positions[0]['time'],
                    'time_close': cur_time,
                    'type': pos_type,
                    'layers': len(positions),
                    'pnl': round(basket_pnl, 2),
                    'capital_after': round(capital, 2),
                    'win': basket_pnl > 0,
                    'exit': exit_type
                })
                positions = []

            if capital > peak_capital:
                peak_capital = capital
            dd_dollar = peak_capital - capital
            dd_pct = (dd_dollar / peak_capital) * 100.0 if peak_capital > 0 else 0
            if dd_dollar > max_drawdown_dollar:
                max_drawdown_dollar = dd_dollar
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

            continue

        # New entry filter
        if hour < 10 or hour > 20:
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

    total_trades = len(closed_trades)
    wins = [t for t in closed_trades if t['win']]
    losses = [t for t in closed_trades if not t['win']]
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    net_profit = capital - INITIAL_CAPITAL
    profit_pct = (net_profit / INITIAL_CAPITAL) * 100.0
    
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

    print("=" * 65)
    print("      REAL HISTORICAL BACKTEST REPORT (PAST 2 MONTHS)")
    print(f"      Period: {df['datetime'].iloc[start_idx].strftime('%Y-%m-%d')} to {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"      Symbol: XAUUSD | Timeframe: M5 | Real Candles: {total_bars}")
    print("=" * 65)
    print(f"Initial Capital:        ${INITIAL_CAPITAL:,.2f} USD")
    print(f"Final Balance:          ${capital:,.2f} USD")
    print(f"Net Profit:             +${net_profit:,.2f} USD (+{profit_pct:.2f}%)")
    print(f"Monthly Avg Return:     ~+{profit_pct/2:.2f}% / Month")
    print(f"Total Closed Cycles:    {total_trades}")
    print(f"Winning Cycles:         {len(wins)} ({win_rate:.1f}%)")
    print(f"Losing Cycles:          {len(losses)} ({100.0 - win_rate:.1f}%)")
    print(f"Profit Factor:          {profit_factor}")
    print(f"Max Drawdown:           ${max_drawdown_dollar:,.2f} ({max_drawdown_pct:.2f}%)")
    print("-" * 65)
    
    # Monthly breakdown
    aug_pnl = sum(v for k, v in daily_pnl.items() if '2026-08' in k)
    sep_pnl = sum(v for k, v in daily_pnl.items() if '2026-09' in k)
    print(f"August 2026 PnL:        +${aug_pnl:,.2f} USD (+{aug_pnl/10:.2f}%)")
    print(f"September 2026 PnL:     +${sep_pnl:,.2f} USD (+{sep_pnl/10:.2f}%)")
    print("=" * 65)

if __name__ == '__main__':
    run_realistic_ea_backtest()
