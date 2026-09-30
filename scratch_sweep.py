import MetaTrader5 as mt5
import pandas as pd

def run_parameter_sweep():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    sym = 'XAUUSD.iux' if mt5.symbol_info('XAUUSD.iux') else 'XAUUSD'
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 12000)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        return

    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    
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

    def simulate(tp1_pips, basket_tp_usd, step1, step2, hard_sl_pips, min_conf):
        capital = 1000.0
        peak = capital
        max_dd = 0.0
        LOT = 0.02
        SPREAD = 2.0
        positions = []
        trades = []
        start_idx = 250
        
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            cur_time = row['datetime']
            cur_p = row['close']
            cur_high = row['high']
            cur_low = row['low']
            hour = cur_time.hour

            if positions:
                pos_type = positions[0]['type']
                first_entry = positions[0]['entry']
                last_entry = positions[-1]['entry']
                num_layers = len(positions)

                # Scale-In additions
                if num_layers < 3:
                    req_step = step1 if num_layers == 1 else step2
                    if pos_type == 'BUY' and (last_entry - cur_p) >= (req_step * 0.10):
                        positions.append({'entry': cur_p, 'type': 'BUY'})
                    elif pos_type == 'SELL' and (cur_p - last_entry) >= (req_step * 0.10):
                        positions.append({'entry': cur_p, 'type': 'SELL'})

                # PnL
                basket_pnl = 0.0
                for p in positions:
                    diff = (cur_p - p['entry']) if p['type'] == 'BUY' else (p['entry'] - cur_p)
                    pips = diff / 0.10
                    basket_pnl += ((pips - SPREAD) * 0.20)

                is_exit = False
                if len(positions) >= 2:
                    if basket_pnl >= basket_tp_usd:
                        is_exit = True
                    # Hard SL
                    tot_sl = (step1 + step2 + hard_sl_pips) * 0.10
                    if (pos_type == 'BUY' and cur_low <= first_entry - tot_sl) or (pos_type == 'SELL' and cur_high >= first_entry + tot_sl):
                        is_exit = True
                else:
                    diff = (cur_p - first_entry) if pos_type == 'BUY' else (first_entry - cur_p)
                    if diff >= (tp1_pips * 0.10):
                        is_exit = True
                    elif (first_entry - cur_p if pos_type == 'BUY' else cur_p - first_entry) >= (step1 * 0.10 * 2.5):
                        is_exit = True

                if is_exit:
                    capital += basket_pnl
                    trades.append(basket_pnl)
                    positions = []

                if capital > peak: peak = capital
                dd = peak - capital
                if dd > max_dd: max_dd = dd
                continue

            if hour < 10 or hour > 20: continue

            close_p = prev['close']
            atr_v = prev['atr']
            smc_w = df.iloc[i-30:i]
            r_high = smc_w['high'].max()
            r_low = smc_w['low'].min()
            
            is_disc = close_p <= (r_low + atr_v * 0.35)
            is_prem = close_p >= (r_high - atr_v * 0.35)
            is_bull = (prev['ema_fast'] > prev['ema_med'] and close_p > prev['ema_slow'])
            is_bear = (prev['ema_fast'] < prev['ema_med'] and close_p < prev['ema_slow'])

            buy_s = 15; sell_s = 15
            if is_bull: buy_s += 30
            if is_bear: sell_s += 30
            if is_disc: buy_s += 25
            if is_prem: sell_s += 25
            if 32.0 < prev['rsi'] < 50.0: buy_s += 20
            if 50.0 < prev['rsi'] < 68.0: sell_s += 20
            if prev['macd'] > prev['macd_sig']: buy_s += 10
            if prev['macd'] < prev['macd_sig']: sell_s += 10

            is_b_pin = (close_p > prev['open']) and ((prev['open'] - prev['low']) > (prev['high'] - close_p) * 1.5)
            is_s_pin = (close_p < prev['open']) and ((prev['high'] - prev['open']) > (close_p - prev['low']) * 1.5)
            if is_b_pin: buy_s += 10
            if is_s_pin: sell_s += 10

            if buy_s >= min_conf and buy_s > sell_s:
                positions.append({'entry': cur_p, 'type': 'BUY'})
            elif sell_s >= min_conf and sell_s > buy_s:
                positions.append({'entry': cur_p, 'type': 'SELL'})

        wins = [t for t in trades if t > 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        net = capital - 1000.0
        return net, wr, len(trades), max_dd

    print("Running Backtest variations on real 12,000 candles...")
    for tp in [40, 50, 60]:
        for b_tp in [10.0, 14.0]:
            net, wr, count, max_dd = simulate(tp1_pips=tp, basket_tp_usd=b_tp, step1=40, step2=50, hard_sl_pips=40, min_conf=70)
            print(f"TP1={tp}p, BasketTP=${b_tp} | Net: +${net:.2f} ({net/10:.1f}%) | WR: {wr:.1f}% | Cycles: {count} | Max DD: ${max_dd:.2f}")

if __name__ == '__main__':
    run_parameter_sweep()
