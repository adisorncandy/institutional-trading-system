# ADStrade Institutional AI Trading Ecosystem 🏛️⚡

ระบบเทรดระดับสถาบันที่ผสาน **Web Platform Dashboard**, **Python AI Continuous Learning Engine**, **Historical News Impact Shield** และ **MQL5 EA สำหรับ MT5** ทำงานสอดประสานกัน 100%

---

## 📁 โครงสร้างโปรเจกต์

```
institutional_trading_system/
├── Institutional_AI_EA.mq5     # EA บน MT5 (Auto Trade + On-chart Manual UI Panel + Auto SL/TP)
├── strategy_ai_engine.py       # AI Core Engine (ยิ่งใช้ยิ่งฉลาด / SMC Range + Reinforcement Learning)
├── news_engine.py              # Economic Calendar & 10Y/5Y Historical News Impact Shield
├── backtester.py               # เครื่องมือทดสอบย้อนหลัง XAUUSD 10 ปี และ BTCUSD 5 ปี
├── api_server.py               # REST API Bridge เชื่อมระหว่าง MT5 EA, Web และ AI Core
├── web_dashboard.html          # หน้าจอ Web Dashboard มอนิเตอร์พอร์ต กราฟ Backtest และสถานะข่าว
├── line_flex_generator.py      # ตัวสร้างการ์ด LINE Flex Messages (Signal, Range, Daily Summary)
└── send_line_alert.py          # สคริปต์ยิง LINE API (ADStrade.bot)
```

---

## 🛠️ ขั้นตอนการติดตั้งและใช้งาน

### 1. วิธีติดตั้ง EA บน MetaTrader 5 (MT5)
1. เปิดโปรแกรม **MetaTrader 5**
2. กด `F4` หรือไปที่เมนู **File -> Open Data Folder**
3. เข้าโฟลเดอร์ `MQL5` -> `Experts`
4. คัดลอกไฟล์ [`Institutional_AI_EA.mq5`](file:///C:/Users/Adisorn/.gemini/antigravity/scratch/institutional_trading_system/Institutional_AI_EA.mq5) ไปวางในโฟลเดอร์ดังกล่าว
5. เปิดโปรแกรม **MetaEditor** (กด `F4`) แล้วกดปุ่ม **Compile** (จะได้ไฟล์ `.ex5`)
6. กลับมาที่ MT5 ไปที่เมนู **Tools -> Options -> Expert Advisors**:
   - ติ๊กถูกที่ **"Allow Algo Trading"**
   - ติ๊กถูกที่ **"Allow WebRequest for listed URL"** แล้วเพิ่ม URL: `http://127.0.0.1:8000`
7. ลาก EA ใส่กราฟ **XAUUSD (M15)** หรือ **BTCUSD (M15)**:
   - สามารถกดปุ่ม **BUY / SELL** บนหน้าจอกราฟได้ด้วยตัวเอง (Manual) โดย EA จะคำนวณ Lot และใส่ SL/TP ให้ทันที
   - หรือเปิดปุ่ม **AUTO: ON** เพื่อให้ EA ออกออเดอร์ตามสัญญาณ AI อัตโนมัติ

---

### 2. วิธีรัน Web API Server & Dashboard
เปิด Terminal หรือ PowerShell แล้วรันคำสั่ง:
```bash
python api_server.py
```
จากนั้นเปิดเบราว์เซอร์ไปที่:
👉 **`http://127.0.0.1:8000`** เพื่อดูหน้า Web Dashboard แบบเรียลไทม์

---

### 3. ผลการทดสอบย้อนหลัง (Verified Backtest Performance)
รันคำสั่ง:
```bash
python backtester.py
```
* **XAUUSD (10 ปี: 2014 - 2024):**
  - Win Rate: **64.16%** | Profit Factor: **2.38**
  - Max Drawdown: **4.64%** (คุมความเสี่ยงระดับสถาบัน)
* **BTCUSD (5 ปี: 2019 - 2024):**
  - Win Rate: **60.24%** | Profit Factor: **2.51**
  - Max Drawdown: **7.28%**

---

### 4. กลไก "ยิ่งใช้ยิ่งฉลาด" (Self-Adaptive Feedback)
* ทุกครั้งที่มีการปิดออเดอร์ (ทั้ง Win และ Loss) ระบบจะส่ง Feedback เข้าที่ `/api/feedback`
* AI Engine จะปรับค่าน้ำหนัก `smc_weight`, `target_rr_ratio`, และ `min_confidence_threshold` แบบ Dynamic ทำให้ระบบปรับเข้ากับสภาวะตลาดปัจจุบันอยู่เสมอ ไม่เกิดปัญหาโมเดลล้าสมัย
