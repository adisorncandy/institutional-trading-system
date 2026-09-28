"""
ADStrade.bot - LINE Messaging API Sender
Enables sending Institutional Signal, Daily Range Blueprint, and Performance Summary
directly to your LINE account or followers.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any
from line_flex_generator import LineFlexService

class LineBotDispatcher:
    def __init__(self, channel_access_token: str = None):
        # Read from argument, config file, or environment
        self.channel_access_token = channel_access_token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        if not self.channel_access_token:
            config_path = os.path.join(os.path.dirname(__file__), "line_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        self.channel_access_token = cfg.get("channel_access_token", "")
                except Exception:
                    pass

        self.broadcast_url = "https://api.line.me/v2/bot/message/broadcast"
        self.push_url = "https://api.line.me/v2/bot/message/push"

    def send_broadcast_flex(self, flex_payload: Dict[str, Any]) -> tuple:
        """Sends a flex message to all followers of ADStrade.bot."""
        if not self.channel_access_token:
            msg = "ยังไม่ได้ระบุ LINE Channel Access Token (กรุณาใส่ Token ในหน้าตั้งค่า LINE Alert)"
            try:
                print(f"[ERROR] {msg}")
            except Exception:
                pass
            return False, msg

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }

        body = {
            "messages": [flex_payload]
        }

        req = urllib.request.Request(
            self.broadcast_url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    msg = "ส่งสัญญาณผ่าน LINE (ADStrade.bot @733ajjvt) สำเร็จเรียบร้อย!"
                    try:
                        print(f"[OK] {msg}")
                    except Exception:
                        pass
                    return True, msg
                else:
                    msg = f"สถานะตอบกลับจาก LINE: {response.status}"
                    return False, msg
        except urllib.error.HTTPError as e:
            error_details = e.read().decode('utf-8')
            msg = f"LINE API Error ({e.code}): {error_details}"
            try:
                print(f"[ERROR] {msg}")
            except Exception:
                pass
            return False, msg
        except Exception as e:
            msg = f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {str(e)}"
            try:
                print(f"[ERROR] {msg}")
            except Exception:
                pass
            return False, msg

    def send_push_flex(self, user_id: str, flex_payload: Dict[str, Any]) -> bool:
        """Sends a flex message to a specific User ID."""
        if not self.channel_access_token:
            print("❌ กรุณาระบุ LINE_CHANNEL_ACCESS_TOKEN")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }

        body = {
            "to": user_id,
            "messages": [flex_payload]
        }

        req = urllib.request.Request(
            self.push_url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ ข้อผิดพลาด: {str(e)}")
            return False

if __name__ == "__main__":
    # Example execution:
    dispatcher = LineBotDispatcher(channel_access_token="YOUR_CHANNEL_ACCESS_TOKEN_HERE")
    test_signal = LineFlexService.create_signal_message(
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        entry_range="2,638.50 - 2,640.00",
        stop_loss="2,632.00 (-65 pips)",
        tp1="2,648.00 (+80 pips)",
        tp2="2,658.00 (+180 pips)",
        rr_ratio="1:2.8",
        confidence=92
    )
    print("Testing payload generation without sending:")
    print(json.dumps(test_signal, indent=2, ensure_ascii=False)[:300] + "...")
