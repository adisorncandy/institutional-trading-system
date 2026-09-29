import os
import json
import urllib.request
import urllib.error

WEB_URL = "https://institutional-trading-system.vercel.app/"

def setup_rich_menu():
    config_path = os.path.join(os.path.dirname(__file__), "line_config.json")
    if not os.path.exists(config_path):
        print("[ERROR] line_config.json not found")
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    token = cfg.get("channel_access_token", "")
    if not token:
        print("[ERROR] channel_access_token is empty")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Clean up old rich menus if any
    try:
        req_list = urllib.request.Request("https://api.line.me/v2/bot/richmenu/list", headers=headers)
        with urllib.request.urlopen(req_list) as resp:
            data = json.loads(resp.read().decode())
            old_menus = data.get("richmenus", [])
            for m in old_menus:
                m_id = m.get("richMenuId")
                del_req = urllib.request.Request(f"https://api.line.me/v2/bot/richmenu/{m_id}", headers=headers, method="DELETE")
                try:
                    urllib.request.urlopen(del_req)
                    print(f"[OK] Cleaned old rich menu: {m_id}")
                except Exception:
                    pass
    except Exception as e:
        print(f"[WARN] Failed to list old menus: {e}")

    # 2. Create New Rich Menu definition
    rich_menu_payload = {
        "size": {
            "width": 2500,
            "height": 843
        },
        "selected": True,
        "name": "Institutional Trading Web Portal",
        "chatBarText": "เมนูพอร์ตสด",
        "areas": [
            {
                "bounds": {
                    "x": 0,
                    "y": 0,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "uri",
                    "label": "Live Portfolio",
                    "uri": WEB_URL
                }
            },
            {
                "bounds": {
                    "x": 833,
                    "y": 0,
                    "width": 834,
                    "height": 843
                },
                "action": {
                    "type": "uri",
                    "label": "Trade Statement",
                    "uri": WEB_URL
                }
            },
            {
                "bounds": {
                    "x": 1667,
                    "y": 0,
                    "width": 833,
                    "height": 843
                },
                "action": {
                    "type": "uri",
                    "label": "AI Traders Council",
                    "uri": WEB_URL
                }
            }
        ]
    }

    req_create = urllib.request.Request(
        "https://api.line.me/v2/bot/richmenu",
        data=json.dumps(rich_menu_payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req_create) as resp:
            create_res = json.loads(resp.read().decode())
            rich_menu_id = create_res.get("richMenuId")
            print(f"[OK] Created Rich Menu ID: {rich_menu_id}")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to create rich menu ({e.code}): {e.read().decode()}")
        return False

    # 3. Upload Image
    image_path = os.path.join(os.path.dirname(__file__), "rich_menu_2500x843.png")
    if not os.path.exists(image_path):
        from generate_rich_menu_image import create_rich_menu_image
        create_rich_menu_image(image_path)

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "image/png",
        "Content-Length": str(len(img_bytes))
    }

    req_upload = urllib.request.Request(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        data=img_bytes,
        headers=upload_headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req_upload) as resp:
            print(f"[OK] Uploaded Rich Menu image successfully (Status: {resp.status})")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to upload rich menu image ({e.code}): {e.read().decode()}")
        return False

    # 4. Set as Default for all users
    req_default = urllib.request.Request(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req_default) as resp:
            print(f"[SUCCESS] Set Rich Menu as default for all users! (Status: {resp.status})")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to set default rich menu ({e.code}): {e.read().decode()}")
        return False

    # Save to config
    cfg["default_rich_menu_id"] = rich_menu_id
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    return True

if __name__ == "__main__":
    setup_rich_menu()
