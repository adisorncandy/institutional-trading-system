"""
Institutional Trading System - Live MT5 & IUX Markets Synchronizer
Features:
1. Connects directly to IUX Markets MT5 Terminal via MetaTrader5 API.
2. Synchronizes real balance, equity, margin, and live floating profit.
3. Synchronizes real open positions (e.g. XAUUSD.iux) to Web Dashboard.
4. Detects real-time events:
   - Order Opened: Broadcasts beautiful LINE Flex Card.
   - Order Closed (TP/SL/Manual): Broadcasts LINE Flex Card with realized profit/loss.
   - Periodic / Manual Account Pulse Status to LINE.
5. Saves authoritative state to `ai_active_positions.json` and updates local/web storage.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.parse

# Ensure stdout and stderr handle utf-8 safely on Windows
try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import MetaTrader5 as mt5
from send_line_alert import LineBotDispatcher
from line_flex_generator import LineFlexService

TERMINAL_PATH = r"C:\Program Files\IUX Markets MT5 Terminal\terminal64.exe"
WEB_URL = "https://institutional-trading-system.vercel.app/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "ai_active_positions.json")
API_STATE_FILE = os.path.join(SCRIPT_DIR, "api", "ai_active_positions.json")
TRACKER_FILE = os.path.join(SCRIPT_DIR, "mt5_ticket_tracker.json")
NOTIF_SETTINGS_FILE = os.path.join(SCRIPT_DIR, "notification_settings.json")

def get_notification_settings() -> Dict[str, Any]:
    defaults = {
        "notify_real_trades": True,
        "notify_demo_trades": True,
        "notify_signals": True
    }
    if os.path.exists(NOTIF_SETTINGS_FILE):
        try:
            with open(NOTIF_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

line_dispatcher = LineBotDispatcher()

class MT5LiveSynchronizer:
    def __init__(self, terminal_path: str = TERMINAL_PATH):
        self.terminal_path = terminal_path
        self.is_connected = False
        self.last_known_tickets: Dict[int, Dict[str, Any]] = {}
        self.last_status_alert_time = 0
        self.load_ticket_tracker()

    def connect(self) -> bool:
        """Initializes connection to MT5 terminal and configured account."""
        cfg_file = os.path.join(SCRIPT_DIR, "iux_account_config.json")
        login_kwargs = {}
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if "login" in cfg and "password" in cfg and "server" in cfg:
                    login_kwargs = {
                        "login": int(cfg["login"]),
                        "password": str(cfg["password"]),
                        "server": str(cfg["server"])
                    }
            except Exception as e:
                print(f"⚠️ [MT5 Sync] Warning reading config: {e}")

        if login_kwargs:
            if not mt5.initialize(path=self.terminal_path, timeout=5000, **login_kwargs):
                if not mt5.initialize(timeout=5000, **login_kwargs):
                    print(f"❌ [MT5 Sync] Failed to initialize MT5 with login {login_kwargs.get('login')}: {mt5.last_error()}")
                    self.is_connected = False
                    return False
        else:
            if not mt5.initialize(timeout=5000):
                if not mt5.initialize(path=self.terminal_path, timeout=5000):
                    print(f"❌ [MT5 Sync] Failed to initialize MT5: {mt5.last_error()}")
                    self.is_connected = False
                    return False

        acc = mt5.account_info()
        if acc is None:
            print("❌ [MT5 Sync] Failed to get account info.")
            self.is_connected = False
            return False

        self.is_connected = True
        print(f"✅ [MT5 Sync Connected] Account: {acc.login} ({acc.name}) | Server: {acc.server} | Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f}")
        return True

    def load_ticket_tracker(self):
        """Loads previously tracked tickets to prevent duplicate notifications on restart."""
        if os.path.exists(TRACKER_FILE):
            try:
                with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_known_tickets = {int(k): v for k, v in data.items()}
            except Exception as e:
                print(f"⚠️ [MT5 Sync] Error loading tracker: {e}")

    def save_ticket_tracker(self):
        """Saves known tickets to disk."""
        try:
            with open(TRACKER_FILE, "w", encoding="utf-8") as f:
                json.dump(self.last_known_tickets, f, indent=2)
        except Exception:
            pass

    def get_account_data(self) -> Optional[Dict[str, Any]]:
        """Fetches live MT5 account details."""
        if not self.is_connected and not self.connect():
            return None
        
        acc = mt5.account_info()
        if not acc:
            return None

        return {
            "login": acc.login,
            "name": acc.name,
            "server": acc.server,
            "company": acc.company,
            "currency": acc.currency,
            "leverage": acc.leverage,
            "balance": round(acc.balance, 2),
            "equity": round(acc.equity, 2),
            "profit": round(acc.profit, 2),
            "margin": round(acc.margin, 2),
            "margin_free": round(acc.margin_free, 2),
            "margin_level": round(acc.margin_level, 2) if acc.margin > 0 else 0.0,
            "timestamp": datetime.now().isoformat()
        }

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Retrieves and standardizes active MT5 positions."""
        if not self.is_connected and not self.connect():
            return []

        raw_positions = mt5.positions_get()
        if raw_positions is None:
            return []

        results = []
        for p in raw_positions:
            is_buy = (p.type == 0)
            symbol_clean = p.symbol.replace(".iux", "").replace("_iux", "").upper()
            open_dt = datetime.fromtimestamp(p.time)
            
            # Estimate pip calculation for XAUUSD or BTCUSD
            point_mult = 10.0 if "XAU" in symbol_clean else 1.0
            pips_gain = (p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)
            pips_val = round(pips_gain * point_mult, 1)

            acc_login = 1287041
            acc_server = "IUXMarkets-Live2"
            try:
                cur_acc = mt5.account_info()
                if cur_acc:
                    acc_login = cur_acc.login
                    acc_server = cur_acc.server
            except Exception:
                pass

            pos_dict = {
                "id": p.ticket,
                "ticket": p.ticket,
                "symbol": symbol_clean,
                "raw_symbol": p.symbol,
                "type": "BUY" if is_buy else "SELL",
                "style": "scalping",
                "portfolioId": "xau_scalp" if "XAU" in symbol_clean else "btc_scalp",
                "portfolioName": f"🟡 พอร์ตจริง IUX Markets #{acc_login} ({symbol_clean})",
                "broker": f"IUX Markets ({acc_server})",
                "accountLogin": acc_login,
                "accountServer": acc_server,
                "lot": round(p.volume, 2),
                "riskPct": 2.0,
                "riskDollar": round(p.volume * 35.0, 2),
                "entry": round(p.price_open, 2),
                "currentPrice": round(p.price_current, 2),
                "sl": round(p.sl, 2),
                "tp1": round(p.tp, 2),
                "tp2": round(p.tp, 2),
                "pnl": round(p.profit, 2),
                "pips": pips_val,
                "timeOpen": open_dt.strftime("%H:%M:%S"),
                "dateOpen": open_dt.strftime("%Y-%m-%d"),
                "tp1Hit": False,
                "breakevenLocked": p.sl > 0 and ((p.sl >= p.price_open and is_buy) or (p.sl <= p.price_open and not is_buy)),
                "reason": f"คำสั่งจริงบน MT5 IUX Markets #{p.ticket}",
                "evalScore": "Real MT5 Trade (Live)",
                "evalStatus": f"🟢 ไม้สดใน MT5 IUX กำไร {p.profit:+.2f} USD"
            }
            results.append(pos_dict)

        return results

    def create_iux_account_status_flex(self, acc: Dict[str, Any], positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creates an ultra-premium LINE Flex Message representing the real IUX account."""
        login = acc.get("login", 1287041)
        name = acc.get("name", "Adisorn RAMTHIP")
        server = acc.get("server", "IUXMarkets-Live2")
        bal = acc.get("balance", 0.0)
        eq = acc.get("equity", 0.0)
        float_pnl = acc.get("profit", 0.0)
        free_margin = acc.get("margin_free", 0.0)
        margin = acc.get("margin", 0.0)

        pnl_str = f"+${float_pnl:,.2f}" if float_pnl >= 0 else f"-${abs(float_pnl):,.2f}"
        pnl_color = "#34D399" if float_pnl >= 0 else "#F87171"

        # Build position rows
        pos_contents = []
        if not positions:
            pos_contents.append({
                "type": "text",
                "text": "ไม่มีออเดอร์ค้าง (พอร์ตปลอดภัย 100%)",
                "color": "#94A3B8",
                "size": "xs",
                "align": "center",
                "margin": "sm"
            })
        else:
            for p in positions[:5]: # show up to 5
                p_pnl = p["pnl"]
                p_pnl_str = f"+${p_pnl:.2f}" if p_pnl >= 0 else f"-${abs(p_pnl):.2f}"
                p_pnl_col = "#34D399" if p_pnl >= 0 else "#F87171"
                action_bg = "#059669" if p["type"] == "BUY" else "#DC2626"
                pos_contents.append({
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": action_bg,
                            "cornerRadius": "4px",
                            "paddingStart": "5px",
                            "paddingEnd": "5px",
                            "paddingTop": "2px",
                            "paddingBottom": "2px",
                            "contents": [{"type": "text", "text": p["type"], "color": "#FFFFFF", "size": "xxs", "weight": "bold"}]
                        },
                        {
                            "type": "text",
                            "text": f" {p['symbol']} ({p['lot']} lot)",
                            "color": "#E2E8F0",
                            "size": "xs",
                            "weight": "bold",
                            "flex": 4,
                            "gravity": "center"
                        },
                        {
                            "type": "text",
                            "text": p_pnl_str,
                            "color": p_pnl_col,
                            "size": "xs",
                            "weight": "bold",
                            "align": "end",
                            "flex": 3,
                            "gravity": "center"
                        }
                    ]
                })

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "18px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "🟢 IUX MARKETS MT5 (พอร์ตจริง)", "color": "#10B981", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": "⚡ SYNC REAL-TIME", "color": "#38BDF8", "size": "xxs", "weight": "bold", "align": "end"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"พอร์ตคุณ: {name}",
                        "color": "#FFFFFF",
                        "size": "md",
                        "weight": "bold",
                        "margin": "xs"
                    },
                    {
                        "type": "text",
                        "text": f"Login: {login} | Server: {server}",
                        "color": "#94A3B8",
                        "size": "xxs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#080C14",
                "paddingAll": "16px",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#101932",
                        "borderColor": "#1E2B48",
                        "borderWidth": "1px",
                        "cornerRadius": "10px",
                        "paddingAll": "14px",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "Account Balance:", "color": "#94A3B8", "size": "xs"},
                                    {"type": "text", "text": f"${bal:,.2f} USD", "color": "#FFFFFF", "size": "sm", "weight": "bold", "align": "end"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "margin": "xs",
                                "contents": [
                                    {"type": "text", "text": "Equity ปัจจุบัน:", "color": "#94A3B8", "size": "xs"},
                                    {"type": "text", "text": f"${eq:,.2f} USD", "color": "#38BDF8", "size": "sm", "weight": "bold", "align": "end"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "margin": "xs",
                                "contents": [
                                    {"type": "text", "text": "กำไรค้างท่อ (Floating):", "color": "#94A3B8", "size": "xs"},
                                    {"type": "text", "text": pnl_str, "color": pnl_color, "size": "sm", "weight": "bold", "align": "end"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "margin": "xs",
                                "contents": [
                                    {"type": "text", "text": "Free Margin:", "color": "#64748B", "size": "xxs"},
                                    {"type": "text", "text": f"${free_margin:,.2f} USD", "color": "#94A3B8", "size": "xxs", "align": "end"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#101932",
                        "borderColor": "#1E2B48",
                        "borderWidth": "1px",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"📊 ออเดอร์ที่กำลังถืออยู่ ({len(positions)} ไม้):",
                                "color": "#FBBF24",
                                "size": "xxs",
                                "weight": "bold"
                            },
                            {"type": "separator", "color": "#1E2B48", "margin": "sm"},
                            *pos_contents
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "14px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "📊 ดูสถานะพอร์ตจริงบนเว็บ",
                            "uri": WEB_URL
                        },
                        "style": "primary",
                        "color": "#0284C7",
                        "height": "sm"
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"🟢 [IUX Markets] สรุปพอร์ตจริง: Equity ${eq:,.2f} ({pnl_str})", "contents": flex_bubble}

    def sync_to_storage_and_web(self, acc: Dict[str, Any], positions: List[Dict[str, Any]]):
        """Saves MT5 live account and positions to the local files and web API."""
        bal = acc["balance"]
        eq = acc["equity"]
        profit = acc["profit"]

        # 1. Update ai_active_positions.json
        payload = {
            "account": acc,
            "positions": positions,
            "portfolios": {
                "xau_scalp": {
                    "id": "xau_scalp",
                    "name": "🟡 พอร์ตจริง IUX Markets (XAUUSD)",
                    "symbol": "XAUUSD",
                    "style": "scalping",
                    "broker": "IUX Markets",
                    "accountLogin": acc["login"],
                    "initialBalance": 1036.79,
                    "balance": bal,
                    "equity": eq,
                    "floatingProfit": profit
                },
                "xau_swing": {
                    "id": "xau_swing",
                    "name": "🟡 ทองคำ เทรดยาว (H1 Swing)",
                    "symbol": "XAUUSD",
                    "style": "swing",
                    "initialBalance": 1000.0,
                    "balance": 1000.0
                },
                "btc_scalp": {
                    "id": "btc_scalp",
                    "name": "🟠 บิตคอยน์ เทรดสั้น (M5 Scalp)",
                    "symbol": "BTCUSD",
                    "style": "scalping",
                    "initialBalance": 1000.0,
                    "balance": 1000.0
                },
                "btc_swing": {
                    "id": "btc_swing",
                    "name": "🟠 บิตคอยน์ เทรดยาว (H1 Swing)",
                    "symbol": "BTCUSD",
                    "style": "swing",
                    "initialBalance": 1000.0,
                    "balance": 1000.0
                }
            },
            "total_balance": bal,
            "balance": bal,
            "equity": eq,
            "floating_profit": profit,
            "total_active": len(positions),
            "updated_at": datetime.now().isoformat()
        }

        for path in [STATE_FILE, API_STATE_FILE]:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        # 2. Inform local API server if running
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/positions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                pass
        except Exception:
            pass

    def check_and_notify_events(self, acc: Dict[str, Any], current_positions: List[Dict[str, Any]]):
        """Detects new orders and closed deals and triggers LINE notifications."""
        current_ticket_map = {p["ticket"]: p for p in current_positions}

        # 1. Detect New Orders Opened
        for ticket, pos in current_ticket_map.items():
            if ticket not in self.last_known_tickets:
                print(f"⚡ [Event: Order Opened] Ticket #{ticket} {pos['symbol']} {pos['type']} {pos['lot']} lot @ {pos['entry']}")
                self.last_known_tickets[ticket] = pos
                self.save_ticket_tracker()
                
                # Send LINE notification
                notif_cfg = get_notification_settings()
                if not notif_cfg.get("notify_real_trades", True):
                    print(f"⏸️ [LINE Real Trade Open Alert Skipped: notify_real_trades is OFF]")
                else:
                    try:
                        pos["isReal"] = True
                        pos["broker"] = "IUX Markets"
                        pos["accountType"] = "REAL"
                        pos["accountLogin"] = acc.get("login", 1287041)
                        pos["balance"] = acc.get("balance", 1036.79)
                        pos["equity"] = acc.get("equity", 1036.79)
                        flex = LineFlexService.create_order_open_message(pos)
                        ok, msg = line_dispatcher.send_broadcast_flex(flex)
                        print(f"📲 [LINE Order Open Alert]: {msg}")
                    except Exception as e:
                        print(f"❌ [LINE Order Open Error]: {e}")

        # 2. Detect Closed Orders
        closed_tickets = [t for t in self.last_known_tickets if t not in current_ticket_map]
        if closed_tickets:
            # Check deals in MT5 to get actual exit price and profit
            from_time = datetime.now() - timedelta(hours=2)
            to_time = datetime.now() + timedelta(hours=1)
            deals = mt5.history_deals_get(from_time, to_time)
            deals_by_pos = {}
            if deals:
                for d in deals:
                    if d.entry == 1: # Deal out (close)
                        deals_by_pos[d.position_id] = d

            for ticket in closed_tickets:
                cached_pos = self.last_known_tickets.pop(ticket)
                self.save_ticket_tracker()
                
                deal = deals_by_pos.get(ticket)
                realized_pnl = round(deal.profit, 2) if deal else cached_pos.get("pnl", 0.0)
                exit_price = round(deal.price, 2) if deal else cached_pos.get("currentPrice", 0.0)
                
                print(f"🎯 [Event: Order Closed] Ticket #{ticket} Realized PnL: ${realized_pnl:+.2f}")

                # Format closed trade payload
                closed_trade = {
                    "ticket": ticket,
                    "symbol": cached_pos.get("symbol", "XAUUSD"),
                    "type": cached_pos.get("type", "BUY"),
                    "lot": cached_pos.get("lot", 0.03),
                    "entry": cached_pos.get("entry", 0.0),
                    "exit": exit_price,
                    "pnl": realized_pnl,
                    "win": realized_pnl > 0,
                    "reason": "ปิดออเดอร์บน MT5 IUX Markets",
                    "timeOpen": cached_pos.get("timeOpen", ""),
                    "timeClose": datetime.now().strftime("%H:%M:%S"),
                    "isReal": True,
                    "broker": "IUX Markets",
                    "accountType": "REAL",
                    "accountLogin": acc.get("login", 1287041),
                    "balance": acc.get("balance", 1036.79),
                    "accountBalance": acc.get("balance", 1036.79),
                    "equity": acc.get("equity", 1036.79)
                }

                # Send LINE notification
                notif_cfg = get_notification_settings()
                if not notif_cfg.get("notify_real_trades", True):
                    print(f"⏸️ [LINE Real Trade Close Alert Skipped: notify_real_trades is OFF]")
                else:
                    try:
                        flex = LineFlexService.create_order_close_message(closed_trade)
                        ok, msg = line_dispatcher.send_broadcast_flex(flex)
                        print(f"📲 [LINE Order Close Alert]: {msg}")
                    except Exception as e:
                        print(f"❌ [LINE Order Close Error]: {e}")

    def run_cycle(self):
        """Runs a single sync cycle."""
        acc = self.get_account_data()
        if not acc:
            return

        positions = self.get_active_positions()
        self.sync_to_storage_and_web(acc, positions)
        self.check_and_notify_events(acc, positions)

    def send_status_pulse_to_line(self) -> bool:
        """Sends an immediate full IUX account summary card to LINE."""
        acc = self.get_account_data()
        if not acc:
            print("❌ Cannot send status: MT5 not connected.")
            return False

        positions = self.get_active_positions()
        flex = self.create_iux_account_status_flex(acc, positions)
        ok, msg = line_dispatcher.send_broadcast_flex(flex)
        print(f"📲 [LINE Status Pulse]: {msg}")
        return ok

def main():
    parser = argparse.ArgumentParser(description="IUX Markets MT5 Live Sync Service")
    parser.add_argument("--status", action="store_true", help="Send instantaneous account status to LINE")
    parser.add_argument("--once", action="store_true", help="Run sync once and exit")
    parser.add_argument("--interval", type=int, default=3, help="Polling interval in seconds (default: 3)")
    args = parser.parse_args()

    syncer = MT5LiveSynchronizer()
    if not syncer.connect():
        print("❌ Cannot start sync: MT5 connection failed.")
        sys.exit(1)

    if args.status:
        syncer.send_status_pulse_to_line()
        mt5.shutdown()
        return

    if args.once:
        syncer.run_cycle()
        print("✅ Single sync cycle completed.")
        mt5.shutdown()
        return

    print(f"🚀 [MT5 Live Sync Service Started] Polling every {args.interval} seconds... (Press Ctrl+C to stop)")
    try:
        while True:
            syncer.run_cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n🛑 Stopping MT5 Sync Service...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
