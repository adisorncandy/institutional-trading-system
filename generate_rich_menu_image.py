import os
import json
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont

WEB_URL = "https://institutional-trading-system.vercel.app/"

def create_rich_menu_image(output_path="rich_menu_2500x843.png"):
    width = 2500
    height = 843
    
    # Create base dark image with high aesthetic styling
    img = Image.new("RGB", (width, height), color=(8, 12, 20))
    draw = ImageDraw.Draw(img)
    
    # Draw background subtle gradients / panels
    # Column 1: 0 - 833
    # Column 2: 833 - 1667
    # Column 3: 1667 - 2500
    
    # Load fonts
    font_large = None
    font_sub = None
    font_tag = None
    font_btn = None
    font_icon = None
    
    for f_path in ["C:\\Windows\\Fonts\\leelawad.ttf", "C:\\Windows\\Fonts\\tahoma.ttf", "C:\\Windows\\Fonts\\arial.ttf"]:
        if os.path.exists(f_path):
            try:
                font_large = ImageFont.truetype(f_path, 68)
                font_sub = ImageFont.truetype(f_path, 38)
                font_tag = ImageFont.truetype(f_path, 32)
                font_btn = ImageFont.truetype(f_path, 42)
                font_icon = ImageFont.truetype("C:\\Windows\\Fonts\\seguiemj.ttf" if os.path.exists("C:\\Windows\\Fonts\\seguiemj.ttf") else f_path, 110)
                break
            except Exception:
                pass
                
    if not font_large:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_tag = ImageFont.load_default()
        font_btn = ImageFont.load_default()
        font_icon = ImageFont.load_default()

    cols = [
        {
            "x0": 25, "x1": 815,
            "tag": "🟢 REAL LIVE ACCOUNT",
            "tag_color": (52, 211, 153),
            "tag_bg": (4, 47, 46),
            "icon": "🟢",
            "title": "พอร์ตจริง IUX Markets",
            "sub": "#1287041 • ทุน $1,036.79 USD",
            "btn_text": "🟢 ดูพอร์ตจริงสด (Web)",
            "btn_bg": (16, 185, 129),
            "btn_fg": (6, 15, 10),
            "border": (16, 185, 129),
            "card_bg": (6, 26, 20)
        },
        {
            "x0": 845, "x1": 1655,
            "tag": "🧪 AI DEMO 4 FUNDS",
            "tag_color": (251, 191, 36),
            "tag_bg": (69, 26, 3),
            "icon": "🧪",
            "title": "พอร์ตจำลอง AI Demo",
            "sub": "4 กองทุนสถาบัน • ทุน $4,000 USD",
            "btn_text": "🧪 ดูพอร์ตจำลอง (Web)",
            "btn_bg": (245, 158, 11),
            "btn_fg": (20, 10, 0),
            "border": (245, 158, 11),
            "card_bg": (25, 20, 10)
        },
        {
            "x0": 1685, "x1": 2475,
            "tag": "📊 VERIFIED STATEMENT",
            "tag_color": (56, 189, 248),
            "tag_bg": (12, 44, 70),
            "icon": "📊",
            "title": "สเตตเมนต์ & เรดาร์ AI",
            "sub": "เช็คประวัติ 111+ ไม้ & สภานักเทรด",
            "btn_text": "📊 เปิดหน้าสเตตเมนต์",
            "btn_bg": (14, 165, 233),
            "btn_fg": (6, 15, 25),
            "border": (56, 189, 248),
            "card_bg": (12, 21, 38)
        }
    ]

    for c in cols:
        # Draw card background
        draw.rounded_rectangle([c["x0"], 20, c["x1"], height - 20], radius=28, fill=c["card_bg"], outline=(30, 41, 59), width=3)
        
        center_x = (c["x0"] + c["x1"]) // 2
        
        # Tag pill
        tag_w = len(c["tag"]) * 19
        tag_x0 = center_x - tag_w // 2
        draw.rounded_rectangle([tag_x0, 55, tag_x0 + tag_w, 115], radius=14, fill=c["tag_bg"], outline=c["tag_color"], width=2)
        draw.text((center_x, 85), c["tag"], fill=c["tag_color"], font=font_tag, anchor="mm")
        
        # Big Icon
        draw.text((center_x, 240), c["icon"], fill=(255, 255, 255), font=font_icon, anchor="mm")
        
        # Title
        draw.text((center_x, 410), c["title"], fill=(255, 255, 255), font=font_large, anchor="mm")
        
        # Subtitle
        draw.text((center_x, 490), c["sub"], fill=(148, 163, 184), font=font_sub, anchor="mm")
        
        # CTA Button
        btn_w = 700
        btn_h = 130
        btn_x0 = center_x - btn_w // 2
        btn_y0 = height - 85 - btn_h
        draw.rounded_rectangle([btn_x0, btn_y0, btn_x0 + btn_w, btn_y0 + btn_h], radius=22, fill=c["btn_bg"])
        draw.text((center_x, btn_y0 + btn_h // 2), c["btn_text"], fill=c["btn_fg"], font=font_btn, anchor="mm")

    # Save image
    img.save(output_path, format="PNG", optimize=True)
    print(f"[OK] Rich Menu image created successfully: {output_path} ({os.path.getsize(output_path)} bytes)")
    return output_path

if __name__ == "__main__":
    create_rich_menu_image()
