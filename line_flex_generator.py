"""
Institutional Trading System - LINE Flex Message Generator for ADStrade.bot
Provides production-ready JSON payloads for:
1. Real-time Action Signals (BUY / SELL with Entry, SL, TP1, TP2, R:R)
2. Daily Range Trading Blueprint (Range High/Low, Pivot, Bias)
3. Daily Performance Summary (Winrate, Profit %, Pip count, AI status)
"""

import json
from typing import Dict, Any, List

class LineFlexService:
    @staticmethod
    def create_signal_message(
        symbol: str = "XAUUSD",
        order_type: str = "BUY LIMIT",  # BUY, SELL, BUY LIMIT, SELL LIMIT
        entry_range: str = "2,638.50 - 2,640.00",
        stop_loss: str = "2,632.00 (-65 pips)",
        tp1: str = "2,648.00 (+80 pips)",
        tp2: str = "2,658.00 (+180 pips)",
        rr_ratio: str = "1:2.8",
        confidence: int = 92,
        timeframe: str = "M15 Institutional",
        rationale: str = "H1 Bullish Order Block + Fair Value Gap",
        news_status: str = "ไม่มีข่าวแดงกระทบใน 90 นาที",
        lot_recommendation: str = "0.03 Lot (ความเสี่ยง 2% / $1,000)"
    ) -> Dict[str, Any]:
        """Creates an Institutional Signal Flex Message Card."""
        is_buy = "BUY" in order_type.upper()
        header_color = "#059669" if is_buy else "#DC2626"
        badge_text = "🟢 BUY SIGNAL" if is_buy else "🔴 SELL SIGNAL"
        badge_color = "#10B981" if is_buy else "#EF4444"

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "paddingAll": "18px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{timeframe} Signal",
                                "color": "#ECFDF5",
                                "size": "xxs",
                                "weight": "bold"
                            },
                            {
                                "type": "text",
                                "text": f"AI CONFIDENCE: {confidence}%",
                                "color": "#A7F3D0",
                                "size": "xxs",
                                "align": "end",
                                "weight": "bold"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{symbol} {order_type}",
                                "color": "#FFFFFF",
                                "size": "xl",
                                "weight": "bold",
                                "flex": 4
                            },
                            {
                                "type": "text",
                                "text": f"R:R {rr_ratio}",
                                "color": "#FFFFFF",
                                "size": "xs",
                                "align": "end",
                                "weight": "bold",
                                "flex": 2
                            }
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "16px",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🎯 Entry (เข้าซื้อ):", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": entry_range, "color": "#FFFFFF", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🛑 Stop Loss (SL):", "color": "#F87171", "size": "xs", "flex": 5},
                                    {"type": "text", "text": stop_loss, "color": "#FCA5A5", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🏁 TP 1 (50% Out):", "color": "#34D399", "size": "xs", "flex": 5},
                                    {"type": "text", "text": tp1, "color": "#6EE7B7", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🏆 TP 2 (Runner):", "color": "#34D399", "size": "xs", "flex": 5},
                                    {"type": "text", "text": tp2, "color": "#6EE7B7", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"💡 Confluence: {rationale}",
                                "color": "#38BDF8",
                                "size": "xxs",
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": f"📰 ข่าวเศรษฐกิจ: {news_status}",
                                "color": "#FCD34D",
                                "size": "xxs",
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": f"⚖️ Money Management: {lot_recommendation}",
                                "color": "#CBD5E1",
                                "size": "xxs",
                                "wrap": True
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "backgroundColor": "#0F172A",
                "paddingAll": "12px",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#10B981" if is_buy else "#EF4444",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "⚡ Execute MT5 Auto",
                            "uri": "https://adstrade.bot/execute"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "📊 ดูบทวิเคราะห์",
                            "uri": "https://adstrade.bot/chart"
                        }
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"[{order_type}] {symbol} Signal Alert", "contents": flex_bubble}

    @staticmethod
    def create_range_message(
        symbol: str = "XAUUSD",
        date_str: str = "27 Sep 2026",
        range_high: str = "2,662.00 - 2,668.00 (Sell Zone)",
        pivot_equi: str = "2,646.00 - 2,648.00 (Equilibrium)",
        range_low: str = "2,632.00 - 2,638.00 (Buy Zone)",
        bias: str = "SIDEWAY / MEAN REVERSION",
        guidelines: List[str] = None,
        key_news_time: str = "Core PCE เวลา 19:30 (ระวังผันผวน)"
    ) -> Dict[str, Any]:
        """Creates Daily Range Blueprint Flex Message."""
        if guidelines is None:
            guidelines = [
                "• ชนกรอบบน 2,665 รอแท่ง Rejection เข้าดัก Sell",
                "• ย่อลงกรอบล่าง 2,635 เข้าหาจังหวะดัก Buy ตาม Order Block",
                "• หลีกเลี่ยงการถือข้ามช่วงประกาศข่าวสำคัญ"
            ]

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1E40AF",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "Daily Market Blueprint", "color": "#93C5FD", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": date_str, "color": "#BFDBFE", "size": "xxs", "align": "end"}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"{symbol} แผนเทรดในกรอบ",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold",
                        "margin": "xs"
                    },
                    {
                        "type": "text",
                        "text": f"BIAS: {bias}",
                        "color": "#FDE047",
                        "size": "xs",
                        "weight": "bold",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "14px",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🔴 กรอบบน (Sell):", "color": "#F87171", "size": "xs", "flex": 4},
                                    {"type": "text", "text": range_high, "color": "#FECACA", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⚖️ จุดสมดุล Pivot:", "color": "#FBBF24", "size": "xs", "flex": 4},
                                    {"type": "text", "text": pivot_equi, "color": "#FDE68A", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🟢 กรอบล่าง (Buy):", "color": "#34D399", "size": "xs", "flex": 4},
                                    {"type": "text", "text": range_low, "color": "#A7F3D0", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": "🧭 คำแนะนำการเข้าทำกำไร:", "color": "#38BDF8", "size": "xs", "weight": "bold"}
                        ] + [{"type": "text", "text": g, "color": "#CBD5E1", "size": "xxs", "wrap": True} for g in guidelines]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#1E1B4B",
                        "cornerRadius": "6px",
                        "paddingAll": "8px",
                        "contents": [
                            {"type": "text", "text": f"⏰ ปฏิทินข่าว: {key_news_time}", "color": "#C7D2FE", "size": "xxs", "wrap": True}
                        ]
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"[{symbol}] แผนเทรดในกรอบประจำวัน", "contents": flex_bubble}

    @staticmethod
    def create_daily_summary_message(
        date_str: str = "27 Sep 2026",
        net_profit_usd: float = 248.50,
        net_profit_pct: float = 2.48,
        win_rate: float = 83.3,
        win_loss: str = "5W / 1L",
        total_pips: int = 290,
        max_drawdown: float = 0.74,
        trade_items: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Creates Daily Performance Report Flex Message."""
        if trade_items is None:
            trade_items = [
                {"text": "🟢 XAUUSD BUY (10:15)", "res": "+85 pips (+$85.00)", "color": "#34D399"},
                {"text": "🔴 XAUUSD SELL (14:30)", "res": "-35 pips (-$35.00)", "color": "#F87171"},
                {"text": "🟢 BTCUSD BUY (16:40)", "res": "+240 pips (+$198.50)", "color": "#34D399"}
            ]

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#581C87",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "Daily Performance Report", "color": "#E9D5FF", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": date_str, "color": "#DDD6FE", "size": "xxs", "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "contents": [
                                    {"type": "text", "text": "กำไรสุทธิวันนี้ (Net Profit)", "color": "#CBD5E1", "size": "xxs"},
                                    {
                                        "type": "text",
                                        "text": f"+${net_profit_usd:,.2f} (+{net_profit_pct}%)",
                                        "color": "#34D399",
                                        "size": "xl",
                                        "weight": "bold"
                                    }
                                ]
                            },
                            {
                                "type": "text",
                                "text": "PROFIT DAY 🔥",
                                "color": "#A7F3D0",
                                "size": "xs",
                                "align": "end",
                                "weight": "bold"
                            }
                        ]
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "14px",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#1E293B",
                                "cornerRadius": "8px",
                                "paddingAll": "8px",
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "Win Rate", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": f"{win_rate}%", "color": "#34D399", "size": "sm", "weight": "bold"},
                                    {"type": "text", "text": win_loss, "color": "#64748B", "size": "xxs"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#1E293B",
                                "cornerRadius": "8px",
                                "paddingAll": "8px",
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "Total Pips", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": f"+{total_pips}", "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                    {"type": "text", "text": "XAU/BTC", "color": "#64748B", "size": "xxs"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": "#1E293B",
                                "cornerRadius": "8px",
                                "paddingAll": "8px",
                                "alignItems": "center",
                                "contents": [
                                    {"type": "text", "text": "Max DD", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": f"{max_drawdown}%", "color": "#38BDF8", "size": "sm", "weight": "bold"},
                                    {"type": "text", "text": "Safe Guard", "color": "#64748B", "size": "xxs"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": item["text"], "color": "#CBD5E1", "size": "xxs", "flex": 6},
                                    {"type": "text", "text": item["res"], "color": item["color"], "size": "xxs", "weight": "bold", "align": "end", "flex": 5}
                                ]
                            } for item in trade_items
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#022C22",
                        "cornerRadius": "6px",
                        "paddingAll": "8px",
                        "contents": [
                            {"type": "text", "text": "🧠 AI Model Retrained: Synced with today's volatility (v4.2)", "color": "#6EE7B7", "size": "xxs"}
                        ]
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"สรุปผลการเทรดประจำวัน {date_str}", "contents": flex_bubble}

    @staticmethod
    def create_order_open_message(pos: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a Flex Message Card when a new order is opened."""
        symbol = pos.get("symbol", "XAUUSD")
        action = pos.get("type", "BUY")
        style_name = pos.get("styleName", "⚡ เทรดสั้น (M5 Scalp)")
        lot = float(pos.get("lot", 0.02))
        ticket = pos.get("ticket", "000000")
        entry = float(pos.get("entry", 0.0))
        sl = float(pos.get("sl", 0.0))
        tp1 = float(pos.get("tp1", 0.0))
        tp2 = float(pos.get("tp2", 0.0))
        reason = pos.get("reason", "Institutional Setup")
        eval_score = pos.get("evalScore", "95% Confluence")
        time_open = pos.get("timeOpen", "")

        is_buy = "BUY" in str(action).upper()
        header_color = "#059669" if is_buy else "#DC2626"

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "⚡ 24/7 AUTO-TRADING", "color": "#ECFDF5", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": f"LOT {lot:.2f}", "color": "#FEF08A", "size": "xxs", "weight": "bold", "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "sm",
                        "contents": [
                            {"type": "text", "text": f"{symbol} {action}", "color": "#FFFFFF", "size": "xl", "weight": "bold", "flex": 4},
                            {"type": "text", "text": f"#{ticket}", "color": "#E2E8F0", "size": "xs", "weight": "bold", "align": "end", "flex": 3}
                        ]
                    },
                    {
                        "type": "text",
                        "text": style_name,
                        "color": "#D1FAE5" if is_buy else "#FFE4E6",
                        "size": "xs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "16px",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🎯 ราคาเข้า (Entry):", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${entry:,.2f}" if "XAU" in symbol else f"${entry:,.1f}", "color": "#FFFFFF", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🛑 Stop Loss (SL):", "color": "#F87171", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${sl:,.2f}" if "XAU" in symbol else f"${sl:,.1f}", "color": "#FCA5A5", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🏁 เป้าหมาย TP 1:", "color": "#34D399", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${tp1:,.2f}" if "XAU" in symbol else f"${tp1:,.1f}", "color": "#6EE7B7", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🏆 เป้าหมาย TP 2:", "color": "#38BDF8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${tp2:,.2f}" if "XAU" in symbol else f"${tp2:,.1f}", "color": "#7DD3FC", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"💡 Confluence: {reason}", "color": "#38BDF8", "size": "xxs", "wrap": True},
                            {"type": "text", "text": f"🧠 AI Score: {eval_score}", "color": "#A7F3D0", "size": "xxs", "wrap": True},
                            {"type": "text", "text": f"⏱️ เวลาเปิด: {time_open} (ทุน $1,000)", "color": "#94A3B8", "size": "xxs"}
                        ]
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"🚀 เปิดออเดอร์ใหม่: {symbol} {action} (Lot {lot:.2f}) #{ticket}", "contents": flex_bubble}

    @staticmethod
    def create_order_close_message(trade: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a Flex Message Card when an order is closed (TP/SL/BE/Manual)."""
        symbol = trade.get("symbol", "XAUUSD")
        action = trade.get("type", "BUY")
        style_name = trade.get("styleName", "⚡ เทรดสั้น (M5 Scalp)")
        lot = float(trade.get("lot", 0.02))
        ticket = trade.get("ticket", "000000")
        entry = float(trade.get("entry", 0.0))
        exit_p = float(trade.get("exit", 0.0))
        pnl = float(trade.get("pnl", 0.0))
        pnl_pct = trade.get("pnlPct", 0.0)
        win = trade.get("win", False)
        reason = trade.get("reason", "ปิดออเดอร์")
        ai_feedback = trade.get("aiFeedback", "")
        time_open = trade.get("timeOpen", "")
        time_close = trade.get("timeClose", "")

        is_be = "Breakeven" in reason or "กันทุน" in reason
        if win:
            header_color = "#059669"
            status_text = "🎯 ปิดทำกำไรสำเร็จ (TAKE PROFIT)"
        elif is_be:
            header_color = "#D97706"
            status_text = "🛡️ ปิดเสมอตัว (BREAKEVEN กันทุน)"
        else:
            header_color = "#DC2626"
            status_text = "🛑 ตัดขาดทุนคุมความเสี่ยง (STOP LOSS)"

        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        pnl_color = "#34D399" if pnl >= 0 else "#F87171"

        reason_display = reason.split('[')[-1].replace(']', '') if '[' in reason else reason

        flex_bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": status_text, "color": "#FFFFFF", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": f"#{ticket}", "color": "#FEF08A", "size": "xxs", "weight": "bold", "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "sm",
                        "contents": [
                            {"type": "text", "text": f"{symbol} {action} ({lot:.2f} Lot)", "color": "#FFFFFF", "size": "lg", "weight": "bold", "flex": 5},
                            {"type": "text", "text": pnl_str, "color": "#FFFFFF", "size": "lg", "weight": "bold", "align": "end", "flex": 4}
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"ผลตอบแทน: {pnl_pct}% ของพอร์ต ($1,000)",
                        "color": "#E2E8F0",
                        "size": "xxs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F172A",
                "paddingAll": "16px",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🎯 ราคาเข้า (Entry):", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${entry:,.2f}" if "XAU" in symbol else f"${entry:,.1f}", "color": "#FFFFFF", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🏁 ราคาปิด (Exit):", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"${exit_p:,.2f}" if "XAU" in symbol else f"${exit_p:,.1f}", "color": pnl_color, "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏱️ ช่วงเวลาถือไม้:", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": f"{time_open} - {time_close}", "color": "#CBD5E1", "size": "xs", "align": "end", "flex": 6}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📌 เงื่อนไขปิดไม้:", "color": "#94A3B8", "size": "xs", "flex": 5},
                                    {"type": "text", "text": reason_display, "color": "#FCD34D", "size": "xs", "weight": "bold", "align": "end", "flex": 6}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#1E293B",
                        "cornerRadius": "8px",
                        "paddingAll": "10px",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": "🧠 AI Learning Update:", "color": "#A78BFA", "size": "xxs", "weight": "bold"},
                            {"type": "text", "text": ai_feedback or "บันทึกข้อมูลเข้า Neural Store เรียบร้อย", "color": "#E2E8F0", "size": "xxs", "wrap": True}
                        ]
                    }
                ]
            }
        }
        return {"type": "flex", "altText": f"📊 ปิดออเดอร์ #{ticket} {symbol} ({pnl_str})", "contents": flex_bubble}


if __name__ == "__main__":
    signal = LineFlexService.create_signal_message()
    print("Signal JSON payload created successfully. Keys:", signal.keys())
