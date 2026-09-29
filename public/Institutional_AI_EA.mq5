//+------------------------------------------------------------------+
//|                                        Institutional_AI_EA.mq5   |
//|               Copyright 2026, Institutional Quant Trading Core   |
//|                                     https://adstrade.bot         |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Trading Core"
#property link      "https://adstrade.bot"
#property version   "4.00"
#property description "Institutional XAUUSD Gold Scalper M1/M5 for $1,000 USD Capital. Pure Standalone Autonomous Logic + Dual Mode."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Enums
enum ENUM_EA_MODE
{
   MODE_STANDALONE = 0, // 🤖 Standalone Autonomous (Pure MT5 Indicators - No Server Needed)
   MODE_HYBRID_WEB = 1  // 🌐 Hybrid Mode (MT5 + Python REST Webhook API)
};

enum ENUM_LOT_MODE
{
   LOT_DYNAMIC_RISK = 0, // 📊 Dynamic Risk % of Balance (Recommended for $1,000)
   LOT_FIXED        = 1  // 🔒 Fixed Lot Size
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== ⚡ System Architecture & Execution Mode ==="
input ENUM_EA_MODE InpEAMode             = MODE_STANDALONE;  // Execution Mode (Standalone vs Hybrid)
input int          InpMagicNumber        = 777101;           // Magic Number (Unique ID)
input bool         InpAutoTradeEnabled   = true;             // Auto-Trading Active On Launch
input int          InpMaxOpenTrades      = 1;                // Max Concurrent Trades (No Martingale/Grid)

input group "=== 💰 Capital $1,000 Risk & Money Management ==="
input ENUM_LOT_MODE InpLotMode           = LOT_DYNAMIC_RISK; // Lot Sizing Mode
input double       InpRiskPercent        = 1.4;              // Risk Per Trade (% of Balance, ~$14 on $1,000)
input double       InpFixedLot           = 0.02;             // Fixed Lot (If Fixed Mode Selected)
input double       InpMaxLotLimit        = 0.06;             // Absolute Max Lot Guardrail
input double       InpMaxDailyDrawdown   = 4.0;              // Max Daily Drawdown Stop (%)

input group "=== 🎯 Institutional Strategy Signals (Triple EMA + SMC + RSI) ==="
input int          InpFastEMAPeriod      = 20;               // Fast EMA Period (Momentum)
input int          InpMediumEMAPeriod    = 50;               // Medium EMA Period (Trend Flow)
input int          InpSlowEMAPeriod      = 200;              // Slow Baseline EMA (Macro Trend)
input int          InpRSIPeriod          = 14;               // RSI Period
input int          InpSMCLookback        = 30;               // SMC Liquidity Range Lookback (Bars)
input double       InpSMCExtremeRatio    = 0.35;             // Discount/Premium Zone Ratio (x ATR)
input int          InpMinConfidenceScore = 80;               // Minimum Confluence Score (80-95%)

input group "=== 🛡️ Scalping Targets & Profit Locking (Points/Pips) ==="
input int          InpStopLossPips       = 35;               // Stop Loss (Pips, 35 pips = $3.50 gold price)
input int          InpTakeProfit1Pips    = 60;               // TP1 First Target (Pips, 60 pips = $6.00 gold price)
input int          InpTakeProfit2Pips    = 100;              // TP2 Runner Target (Pips, 100 pips = $10.00 gold price)
input bool         InpUseMicroBE         = true;             // Micro-Breakeven Protection (Locks early profit)
input int          InpMicroBEPips        = 8;                // Micro-BE Trigger (8 pips profit)
input int          InpMicroBELockPips    = 2;                // Micro-BE Lock Amount (+2 pips in profit)
input bool         InpPartialCloseAtTP1  = true;             // Bank Partial Profit at TP1
input double       InpPartialClosePct    = 75.0;             // Partial Close % (75% at TP1)
input bool         InpTrailingStop       = true;             // Trailing Stop for Remaining Runner
input int          InpTrailPips          = 35;               // Trailing Stop Distance (Pips)

input group "=== 🕒 Session Filter & Spread Guard ==="
input bool         InpUseSessionFilter   = true;             // Trade Only High Liquidity Windows
input int          InpLondonStartHour    = 10;               // London Session Start (Broker Server Hour)
input int          InpLondonEndHour      = 14;               // London Session End (Broker Server Hour)
input int          InpNYStartHour        = 15;               // New York Session Start (Broker Server Hour)
input int          InpNYEndHour          = 20;               // New York Session End (Broker Server Hour)
input double       InpMaxSpreadPips      = 3.0;              // Max Allowable Spread (Pips)

input group "=== 🌐 Hybrid Mode Webhook Integration ==="
input string       InpServerURL          = "http://127.0.0.1:8000/api/signal"; // Local AI REST Bridge
input int          InpPollingSeconds     = 10;               // Web Signal Poll Frequency (Seconds)

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES & INDICATOR HANDLES                             |
//+------------------------------------------------------------------+
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;

int            h_ema_fast   = INVALID_HANDLE;
int            h_ema_med    = INVALID_HANDLE;
int            h_ema_slow   = INVALID_HANDLE;
int            h_rsi        = INVALID_HANDLE;
int            h_macd       = INVALID_HANDLE;
int            h_atr        = INVALID_HANDLE;

datetime       g_last_bar_time   = 0;
datetime       g_last_poll_time  = 0;
bool           g_gui_auto_state  = true;
double         g_daily_start_bal = 0.0;
datetime       g_last_day_check  = 0;

// Struct for Signal Evaluation
struct SSignalResult
{
   int    action;          // 0: NONE, 1: BUY, -1: SELL
   int    confidence;      // 0 - 100%
   double entry_price;
   double sl;
   double tp1;
   double tp2;
   string reason;
};

// Forward Declarations
void CreateTradingPanel();
void UpdateTradingPanel(string trendStatus, int confluence);
void ManageOpenPositions();
void CheckAutonomousSignals();
void CheckSignalsFromServer();
double CalculateLotSize(double stopLossPips);
bool IsTradingSessionAllowed();
bool IsSpreadAcceptable();
bool CheckDailyLossLimit();

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   g_gui_auto_state = InpAutoTradeEnabled;
   g_daily_start_bal = m_account.Balance();
   g_last_day_check = TimeCurrent();

   // Initialize Indicator Handles
   h_ema_fast = iMA(_Symbol, _Period, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_med  = iMA(_Symbol, _Period, InpMediumEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_slow = iMA(_Symbol, _Period, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi      = iRSI(_Symbol, _Period, InpRSIPeriod, PRICE_CLOSE);
   h_macd     = iMACD(_Symbol, _Period, 12, 26, 9, PRICE_CLOSE);
   h_atr      = iATR(_Symbol, _Period, 14);

   if(h_ema_fast == INVALID_HANDLE || h_ema_med == INVALID_HANDLE || 
      h_ema_slow == INVALID_HANDLE || h_rsi == INVALID_HANDLE ||
      h_macd == INVALID_HANDLE || h_atr == INVALID_HANDLE)
   {
      Print("❌ [Institutional EA] Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   CreateTradingPanel();
   UpdateTradingPanel("INITIALIZING...", 0);

   Print(" Institutional AI EA V4.0 Initialized successfully on ", _Symbol, " | Capital Preset: $1,000 USD");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Release indicator handles
   if(h_ema_fast != INVALID_HANDLE) IndicatorRelease(h_ema_fast);
   if(h_ema_med != INVALID_HANDLE)  IndicatorRelease(h_ema_med);
   if(h_ema_slow != INVALID_HANDLE) IndicatorRelease(h_ema_slow);
   if(h_rsi != INVALID_HANDLE)      IndicatorRelease(h_rsi);
   if(h_macd != INVALID_HANDLE)     IndicatorRelease(h_macd);
   if(h_atr != INVALID_HANDLE)      IndicatorRelease(h_atr);

   ObjectsDeleteAll(0, "AD_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Reset daily start balance at midnight
   MqlDateTime dt;
   TimeCurrent(dt);
   static int lastDay = -1;
   if(dt.day != lastDay)
   {
      g_daily_start_bal = m_account.Balance();
      lastDay = dt.day;
   }

   // 1. Manage Active Positions (Micro-BE, TP1 Partial Close, Trailing Stop)
   ManageOpenPositions();

   // 2. Risk check: Max Daily Drawdown
   if(!CheckDailyLossLimit())
   {
      UpdateTradingPanel("STOPPED (DAILY DD LIMIT)", 0);
      return;
   }

   // 3. Autonomous Execution on New Bar or Hybrid Web Poll
   if(InpEAMode == MODE_STANDALONE)
   {
      datetime current_bar = iTime(_Symbol, _Period, 0);
      if(current_bar != g_last_bar_time)
      {
         g_last_bar_time = current_bar;
         CheckAutonomousSignals();
      }
   }
   else if(InpEAMode == MODE_HYBRID_WEB)
   {
      if(g_gui_auto_state && (TimeCurrent() - g_last_poll_time >= InpPollingSeconds))
      {
         g_last_poll_time = TimeCurrent();
         CheckSignalsFromServer();
      }
   }
}

//+------------------------------------------------------------------+
//| Check Daily Drawdown Limit                                       |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit()
{
   if(InpMaxDailyDrawdown <= 0 || g_daily_start_bal <= 0) return true;
   double currentEquity = m_account.Equity();
   double dailyLoss = g_daily_start_bal - currentEquity;
   double maxAllowedLoss = g_daily_start_bal * (InpMaxDailyDrawdown / 100.0);

   if(dailyLoss >= maxAllowedLoss)
   {
      return false; // Breach
   }
   return true;
}

//+------------------------------------------------------------------+
//| Session Filter Check (High Liquidity Hours)                      |
//+------------------------------------------------------------------+
bool IsTradingSessionAllowed()
{
   if(!InpUseSessionFilter) return true;
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;

   // London Session or NY Session
   bool isLondon = (hour >= InpLondonStartHour && hour < InpLondonEndHour);
   bool isNY     = (hour >= InpNYStartHour && hour < InpNYEndHour);

   return (isLondon || isNY);
}

//+------------------------------------------------------------------+
//| Spread Filter Check                                              |
//+------------------------------------------------------------------+
bool IsSpreadAcceptable()
{
   double spreadPoints = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double spreadPips = spreadPoints / 10.0;
   return (spreadPips <= InpMaxSpreadPips);
}

//+------------------------------------------------------------------+
//| Autonomous Signal Generator (Triple EMA + SMC Range + RSI)       |
//+------------------------------------------------------------------+
void CheckAutonomousSignals()
{
   // Check active position count
   int currentOpen = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
         currentOpen++;
   }

   // Read indicator buffers
   double emaFast[2], emaMed[2], emaSlow[2], rsi[2], atr[1], macdMain[2], macdSig[2];
   if(CopyBuffer(h_ema_fast, 0, 1, 2, emaFast) <= 0) return;
   if(CopyBuffer(h_ema_med, 0, 1, 2, emaMed) <= 0) return;
   if(CopyBuffer(h_ema_slow, 0, 1, 2, emaSlow) <= 0) return;
   if(CopyBuffer(h_rsi, 0, 1, 2, rsi) <= 0) return;
   if(CopyBuffer(h_macd, 0, 1, 2, macdMain) <= 0) return;
   if(CopyBuffer(h_macd, 1, 1, 2, macdSig) <= 0) return;
   if(CopyBuffer(h_atr, 0, 1, 1, atr) <= 0) return;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 1, InpSMCLookback, rates) < InpSMCLookback) return;

   // Compute Range High, Low & Equilibrium for SMC
   double rangeHigh = rates[0].high;
   double rangeLow  = rates[0].low;
   for(int k = 1; k < InpSMCLookback; k++)
   {
      if(rates[k].high > rangeHigh) rangeHigh = rates[k].high;
      if(rates[k].low < rangeLow)   rangeLow  = rates[k].low;
   }

   double currentClose = rates[0].close;
   double currentLow   = rates[0].low;
   double currentHigh  = rates[0].high;
   double currentOpenP = rates[0].open;
   double atrVal       = atr[0];

   // Zones
   bool isDiscount = (currentClose <= (rangeLow + atrVal * InpSMCExtremeRatio));
   bool isPremium  = (currentClose >= (rangeHigh - atrVal * InpSMCExtremeRatio));

   // Ribbon Alignment
   bool isBullRibbon = (emaFast[1] > emaMed[1] && currentClose > emaSlow[1]);
   bool isBearRibbon = (emaFast[1] < emaMed[1] && currentClose < emaSlow[1]);

   // Confluence Scoring
   int buyScore = 0;
   int sellScore = 0;

   // Session bonus
   bool sessionOK = IsTradingSessionAllowed();
   if(sessionOK) { buyScore += 15; sellScore += 15; }

   // Trend confluence
   if(isBullRibbon) buyScore += 30;
   if(isBearRibbon) sellScore += 30;

   // SMC Discount / Premium confluence
   if(isDiscount) buyScore += 25;
   if(isPremium)  sellScore += 25;

   // RSI Confluence (Pullback validation)
   if(rsi[1] > 32.0 && rsi[1] < 48.0 && rsi[1] > rsi[0]) buyScore += 20;
   if(rsi[1] < 68.0 && rsi[1] > 52.0 && rsi[1] < rsi[0]) sellScore += 20;

   // MACD Momentum
   if(macdMain[1] > macdSig[1]) buyScore += 10;
   if(macdMain[1] < macdSig[1]) sellScore += 10;

   // Price Action Rejection confirmation
   bool isBullPin = (currentClose > currentOpenP) && ((currentOpenP - currentLow) > (currentHigh - currentClose) * 1.5);
   bool isBearPin = (currentClose < currentOpenP) && ((currentHigh - currentOpenP) > (currentClose - currentLow) * 1.5);
   if(isBullPin) buyScore += 10;
   if(isBearPin) sellScore += 10;

   // Update HUD Dashboard
   string trendStr = isBullRibbon ? "BULLISH TREND" : (isBearRibbon ? "BEARISH TREND" : "CHOPPY RANGE");
   int bestScore = MathMax(buyScore, sellScore);
   UpdateTradingPanel(trendStr, bestScore);

   // Check execution permissions
   if(!g_gui_auto_state) return;
   if(currentOpen >= InpMaxOpenTrades) return;
   if(!sessionOK) return;
   if(!IsSpreadAcceptable()) return;

   double pipSize = (_Point * 10.0);

   // BUY EXECUTION
   if(buyScore >= InpMinConfidenceScore && buyScore > sellScore)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(ask - (InpStopLossPips * pipSize), _Digits);
      double tp1 = NormalizeDouble(ask + (InpTakeProfit1Pips * pipSize), _Digits);
      double lot = CalculateLotSize(InpStopLossPips);

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp1, "AD Scalper BUY"))
      {
         Print("✅ [Institutional Scalper] BUY Executed @ ", ask, " | Lot: ", lot, " | Confluence: ", buyScore, "%");
      }
   }
   // SELL EXECUTION
   else if(sellScore >= InpMinConfidenceScore && sellScore > buyScore)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(bid + (InpStopLossPips * pipSize), _Digits);
      double tp1 = NormalizeDouble(bid - (InpTakeProfit1Pips * pipSize), _Digits);
      double lot = CalculateLotSize(InpStopLossPips);

      if(m_trade.Sell(lot, _Symbol, bid, sl, tp1, "AD Scalper SELL"))
      {
         Print("✅ [Institutional Scalper] SELL Executed @ ", bid, " | Lot: ", lot, " | Confluence: ", sellScore, "%");
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Lot Sizing based on Capital & Risk Percent               |
//+------------------------------------------------------------------+
double CalculateLotSize(double stopLossPips)
{
   if(InpLotMode == LOT_FIXED || stopLossPips <= 0)
   {
      return MathMin(InpMaxLotLimit, InpFixedLot);
   }

   double balance = m_account.Balance();
   double riskAmount = balance * (InpRiskPercent / 100.0); // e.g. $1000 * 1.4% = $14
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(point == 0 || tickSize == 0 || tickValue == 0) return InpFixedLot;

   double pipsToPoints = stopLossPips * 10.0;
   double lossPerLot = (pipsToPoints * point / tickSize) * tickValue;
   if(lossPerLot <= 0) return InpFixedLot;

   double calculatedLot = riskAmount / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxLotLimit);

   calculatedLot = MathFloor(calculatedLot / step) * step;
   return MathMax(minLot, MathMin(maxLot, calculatedLot));
}

//+------------------------------------------------------------------+
//| Position Management: Micro-BE, TP1 Partial Close & Trailing      |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   double pointScale = _Point * 10.0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
      {
         ulong ticket = m_position.Ticket();
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         double volume = m_position.Volume();
         double microBEDist = InpMicroBEPips * pointScale;
         double microBELock = InpMicroBELockPips * pointScale;
         double tp1Dist     = InpTakeProfit1Pips * pointScale;
         double trailDist   = InpTrailPips * pointScale;

         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double profitDist = bid - openPrice;

            // 1. Micro-Breakeven (+2 pips locked when +8 pips reached)
            if(InpUseMicroBE && profitDist >= microBEDist && (currentSL < openPrice + microBELock))
            {
               double newSL = NormalizeDouble(openPrice + microBELock, _Digits);
               if(m_trade.PositionModify(ticket, newSL, m_position.TakeProfit()))
                  Print("🛡️ [Micro-BE Locked] BUY #", ticket, " SL moved to +", InpMicroBELockPips, " pips");
            }

            // 2. TP1 Partial Close (75%) & Institutional BE Lock (+5 pips)
            if(profitDist >= tp1Dist)
            {
               if(InpPartialCloseAtTP1 && volume > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
               {
                  double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
                  double closeVol = MathFloor((volume * (InpPartialClosePct / 100.0)) / step) * step;
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < volume)
                  {
                     m_trade.PositionClosePartial(ticket, closeVol);
                     Print("🎯 [TP1 Partial Close] Closed ", closeVol, " lots (75%) on #", ticket);
                  }
               }
               // Lock +5 pips guaranteed
               double newSL = NormalizeDouble(openPrice + (5 * pointScale), _Digits);
               if(newSL > currentSL)
                  m_trade.PositionModify(ticket, newSL, 0); // Remove TP to let remaining 25% run
            }

            // 3. Trailing Stop for Remaining Runner
            if(InpTrailingStop && profitDist > (trailDist * 1.5))
            {
               double trailSL = NormalizeDouble(bid - trailDist, _Digits);
               if(trailSL > currentSL + pointScale)
                  m_trade.PositionModify(ticket, trailSL, m_position.TakeProfit());
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double profitDist = openPrice - ask;

            // 1. Micro-Breakeven (+2 pips locked when +8 pips reached)
            if(InpUseMicroBE && profitDist >= microBEDist && (currentSL > openPrice - microBELock || currentSL == 0))
            {
               double newSL = NormalizeDouble(openPrice - microBELock, _Digits);
               if(m_trade.PositionModify(ticket, newSL, m_position.TakeProfit()))
                  Print("🛡️ [Micro-BE Locked] SELL #", ticket, " SL moved to +", InpMicroBELockPips, " pips");
            }

            // 2. TP1 Partial Close (75%) & Institutional BE Lock (+5 pips)
            if(profitDist >= tp1Dist)
            {
               if(InpPartialCloseAtTP1 && volume > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
               {
                  double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
                  double closeVol = MathFloor((volume * (InpPartialClosePct / 100.0)) / step) * step;
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < volume)
                  {
                     m_trade.PositionClosePartial(ticket, closeVol);
                     Print("🎯 [TP1 Partial Close] Closed ", closeVol, " lots (75%) on #", ticket);
                  }
               }
               // Lock +5 pips guaranteed
               double newSL = NormalizeDouble(openPrice - (5 * pointScale), _Digits);
               if(currentSL == 0 || newSL < currentSL)
                  m_trade.PositionModify(ticket, newSL, 0); // Remove TP to let remaining 25% run
            }

            // 3. Trailing Stop for Remaining Runner
            if(InpTrailingStop && profitDist > (trailDist * 1.5))
            {
               double trailSL = NormalizeDouble(ask + trailDist, _Digits);
               if(currentSL == 0 || trailSL < currentSL - pointScale)
                  m_trade.PositionModify(ticket, trailSL, m_position.TakeProfit());
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check and Execute Signals from AI REST Engine (Hybrid Mode)      |
//+------------------------------------------------------------------+
void CheckSignalsFromServer()
{
   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   string payload = "{\"symbol\":\"" + _Symbol + "\"}";
   StringToCharArray(payload, post);

   int res = WebRequest("GET", InpServerURL + "?symbol=" + _Symbol, headers, 3000, post, result, headers);
   if(res == 200)
   {
      string responseJson = CharArrayToString(result);
      double pipSize = (_Point * 10.0);

      if(StringFind(responseJson, "\"action\":\"BUY\"") >= 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = NormalizeDouble(ask - (InpStopLossPips * pipSize), _Digits);
         double tp = NormalizeDouble(ask + (InpTakeProfit1Pips * pipSize), _Digits);
         double lot = CalculateLotSize(InpStopLossPips);
         m_trade.Buy(lot, _Symbol, ask, sl, tp, "AI Hybrid BUY");
      }
      else if(StringFind(responseJson, "\"action\":\"SELL\"") >= 0)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = NormalizeDouble(bid + (InpStopLossPips * pipSize), _Digits);
         double tp = NormalizeDouble(bid - (InpTakeProfit1Pips * pipSize), _Digits);
         double lot = CalculateLotSize(InpStopLossPips);
         m_trade.Sell(lot, _Symbol, bid, sl, tp, "AI Hybrid SELL");
      }
   }
}

//+------------------------------------------------------------------+
//| Chart Event function (Handles On-Chart Manual Click Buttons)     |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      double pipSize = (_Point * 10.0);

      if(sparam == "AD_BTN_BUY")
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = NormalizeDouble(ask - (InpStopLossPips * pipSize), _Digits);
         double tp  = NormalizeDouble(ask + (InpTakeProfit1Pips * pipSize), _Digits);
         double lot = CalculateLotSize(InpStopLossPips);
         m_trade.Buy(lot, _Symbol, ask, sl, tp, "Manual Scalp BUY");
         ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_STATE, false);
      }
      else if(sparam == "AD_BTN_SELL")
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = NormalizeDouble(bid + (InpStopLossPips * pipSize), _Digits);
         double tp  = NormalizeDouble(bid - (InpTakeProfit1Pips * pipSize), _Digits);
         double lot = CalculateLotSize(InpStopLossPips);
         m_trade.Sell(lot, _Symbol, bid, sl, tp, "Manual Scalp SELL");
         ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_STATE, false);
      }
      else if(sparam == "AD_BTN_CLOSE")
      {
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber)
               m_trade.PositionClose(m_position.Ticket());
         }
         ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_STATE, false);
      }
      else if(sparam == "AD_BTN_TOGGLE_AUTO")
      {
         g_gui_auto_state = !g_gui_auto_state;
         ObjectSetString(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_TEXT, g_gui_auto_state ? "⚡ AUTO: ON" : "⏸️ AUTO: PAUSED");
         ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_BGCOLOR, g_gui_auto_state ? C'16,185,129' : C'71,85,105');
         ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_STATE, false);
      }
      ChartRedraw();
   }
}

//+------------------------------------------------------------------+
//| On-Chart Cyberpunk HUD Panel Creation                            |
//+------------------------------------------------------------------+
void CreateTradingPanel()
{
   int x = 20, y = 30;
   int w = 240, h = 260;

   // Main Panel Background
   ObjectCreate(0, "AD_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_BG", OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, "AD_BG", OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, "AD_BG", OBJPROP_XSIZE, w);
   ObjectSetInteger(0, "AD_BG", OBJPROP_YSIZE, h);
   ObjectSetInteger(0, "AD_BG", OBJPROP_BGCOLOR, C'10,15,29');
   ObjectSetInteger(0, "AD_BG", OBJPROP_BORDER_COLOR, C'30,58,138');

   // Header Label
   ObjectCreate(0, "AD_TITLE", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_YDISTANCE, y + 10);
   ObjectSetString(0, "AD_TITLE", OBJPROP_TEXT, "⚡ XAUUSD INSTITUTIONAL SCALPER");
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_COLOR, C'56,189,248');
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_FONTSIZE, 8);

   // Status Label
   ObjectCreate(0, "AD_STATUS", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_STATUS", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_STATUS", OBJPROP_YDISTANCE, y + 30);
   ObjectSetString(0, "AD_STATUS", OBJPROP_TEXT, "Capital: $1,000 | Scanning M5...");
   ObjectSetInteger(0, "AD_STATUS", OBJPROP_COLOR, C'148,163,184');
   ObjectSetInteger(0, "AD_STATUS", OBJPROP_FONTSIZE, 8);

   // Trend & Confluence Label
   ObjectCreate(0, "AD_METRICS", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_METRICS", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_METRICS", OBJPROP_YDISTANCE, y + 50);
   ObjectSetString(0, "AD_METRICS", OBJPROP_TEXT, "Trend: -- | Confluence: --%");
   ObjectSetInteger(0, "AD_METRICS", OBJPROP_COLOR, C'245,158,11');
   ObjectSetInteger(0, "AD_METRICS", OBJPROP_FONTSIZE, 8);

   // PnL Label
   ObjectCreate(0, "AD_PNL", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_PNL", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_PNL", OBJPROP_YDISTANCE, y + 70);
   ObjectSetString(0, "AD_PNL", OBJPROP_TEXT, "Equity: $0.00 | Floating: $0.00");
   ObjectSetInteger(0, "AD_PNL", OBJPROP_COLOR, C'52,211,153');
   ObjectSetInteger(0, "AD_PNL", OBJPROP_FONTSIZE, 8);

   // Button Manual BUY
   ObjectCreate(0, "AD_BTN_BUY", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_YDISTANCE, y + 95);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_XSIZE, 105);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_YSIZE, 32);
   ObjectSetString(0, "AD_BTN_BUY", OBJPROP_TEXT, "▲ BUY SCALP");
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_BGCOLOR, C'16,185,129');
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_COLOR, clrWhite);

   // Button Manual SELL
   ObjectCreate(0, "AD_BTN_SELL", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_XDISTANCE, x + 123);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_YDISTANCE, y + 95);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_XSIZE, 105);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_YSIZE, 32);
   ObjectSetString(0, "AD_BTN_SELL", OBJPROP_TEXT, "▼ SELL SCALP");
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_BGCOLOR, C'239,68,68');
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_COLOR, clrWhite);

   // Button Toggle AUTO
   ObjectCreate(0, "AD_BTN_TOGGLE_AUTO", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_YDISTANCE, y + 135);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_XSIZE, 216);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_YSIZE, 35);
   ObjectSetString(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_TEXT, g_gui_auto_state ? "⚡ AUTO: ON" : "⏸️ AUTO: PAUSED");
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_BGCOLOR, g_gui_auto_state ? C'16,185,129' : C'71,85,105');
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_COLOR, clrWhite);

   // Button Close All
   ObjectCreate(0, "AD_BTN_CLOSE", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_YDISTANCE, y + 178);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_XSIZE, 216);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_YSIZE, 28);
   ObjectSetString(0, "AD_BTN_CLOSE", OBJPROP_TEXT, "✖ CLOSE ALL TRADES");
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_BGCOLOR, C'51,65,85');
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_COLOR, clrWhite);

   // Session & Spread Footer
   ObjectCreate(0, "AD_FOOTER", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_FOOTER", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_FOOTER", OBJPROP_YDISTANCE, y + 215);
   ObjectSetString(0, "AD_FOOTER", OBJPROP_TEXT, "Micro-BE: Active (+8p->+2p) | TP1: 75%");
   ObjectSetInteger(0, "AD_FOOTER", OBJPROP_COLOR, C'100,116,139');
   ObjectSetInteger(0, "AD_FOOTER", OBJPROP_FONTSIZE, 7);

   ObjectCreate(0, "AD_FOOTER2", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_FOOTER2", OBJPROP_XDISTANCE, x + 12);
   ObjectSetInteger(0, "AD_FOOTER2", OBJPROP_YDISTANCE, y + 233);
   ObjectSetString(0, "AD_FOOTER2", OBJPROP_TEXT, "Session: " + (IsTradingSessionAllowed() ? "ACTIVE (London/NY)" : "OFF-PEAK") + " | Spd: " + DoubleToString(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)/10.0, 1) + "p");
   ObjectSetInteger(0, "AD_FOOTER2", OBJPROP_COLOR, IsTradingSessionAllowed() ? C'52,211,153' : C'239,68,68');
   ObjectSetInteger(0, "AD_FOOTER2", OBJPROP_FONTSIZE, 7);
}

//+------------------------------------------------------------------+
//| Update Dynamic Metrics on HUD Panel                              |
//+------------------------------------------------------------------+
void UpdateTradingPanel(string trendStatus, int confluence)
{
   double balance = m_account.Balance();
   double equity  = m_account.Equity();
   double profit  = m_account.Profit();

   ObjectSetString(0, "AD_STATUS", OBJPROP_TEXT, "Bal: $" + DoubleToString(balance, 2) + " | Risk: " + DoubleToString(InpRiskPercent, 1) + "%");
   ObjectSetString(0, "AD_METRICS", OBJPROP_TEXT, trendStatus + " (" + IntegerToString(confluence) + "%)");
   
   if(confluence >= InpMinConfidenceScore)
      ObjectSetInteger(0, "AD_METRICS", OBJPROP_COLOR, C'52,211,153'); // Bright Green
   else
      ObjectSetInteger(0, "AD_METRICS", OBJPROP_COLOR, C'245,158,11'); // Amber

   string pnlText = "Eq: $" + DoubleToString(equity, 2) + " | Float: " + (profit >= 0 ? "+$" : "-$") + DoubleToString(MathAbs(profit), 2);
   ObjectSetString(0, "AD_PNL", OBJPROP_TEXT, pnlText);
   ObjectSetInteger(0, "AD_PNL", OBJPROP_COLOR, profit >= 0 ? C'52,211,153' : C'239,68,68');

   double spreadPips = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) / 10.0;
   bool sessionOK = IsTradingSessionAllowed();
   ObjectSetString(0, "AD_FOOTER2", OBJPROP_TEXT, "Session: " + (sessionOK ? "ACTIVE (London/NY)" : "OFF-PEAK") + " | Spd: " + DoubleToString(spreadPips, 1) + "p");
   ObjectSetInteger(0, "AD_FOOTER2", OBJPROP_COLOR, sessionOK ? C'52,211,153' : C'239,68,68');

   ChartRedraw();
}
//+------------------------------------------------------------------+
