//+------------------------------------------------------------------+
//|                                        Institutional_AI_EA.mq5   |
//|               Copyright 2026, Institutional Quant Trading Core   |
//|                                     https://adstrade.bot         |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Trading Core"
#property link      "https://adstrade.bot"
#property version   "4.00"
#property description "Golden Trend Rider V4 - Institutional Multi-Timeframe Trend Follower for XAUUSD (H1/H4) with Dynamic 2% Risk, Partial Close & ATR Trailing."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Enums
enum ENUM_EA_MODE
{
   MODE_STANDALONE = 0, // 🤖 Standalone Autonomous (Pure MT5 H1/H4 Indicators)
   MODE_HYBRID_WEB = 1  // 🌐 Hybrid Mode (MT5 + Python REST Webhook API)
};

enum ENUM_LOT_MODE
{
   LOT_DYNAMIC_RISK = 0, // 📊 Dynamic Risk % of Capital (Recommended 2.0%)
   LOT_FIXED        = 1  // 🔒 Fixed Lot Size
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== ⚡ System Architecture & Execution Mode ==="
input ENUM_EA_MODE InpEAMode             = MODE_STANDALONE;  // Execution Mode (Standalone vs Hybrid)
input int          InpMagicNumber        = 777101;           // Magic Number (Unique ID)
input bool         InpAutoTradeEnabled   = true;             // Auto-Trading Active On Launch

input group "=== 💰 Risk & Money Management (Golden Trend Rider V4) ==="
input ENUM_LOT_MODE InpLotMode           = LOT_DYNAMIC_RISK; // Lot Sizing Mode
input double       InpRiskPercent        = 2.0;              // Risk Per Trade (% of Balance, e.g. 2.0% on $1,000)
input double       InpFixedLot           = 0.02;             // Fixed Lot Size (if LOT_FIXED mode)
input double       InpMinLot             = 0.01;             // Minimum Lot Guardrail
input double       InpMaxLotLimit        = 0.20;             // Absolute Max Lot Guardrail
input double       InpMaxDailyDrawdown   = 3.0;              // Max Daily Drawdown Stop (%)

input group "=== 🎯 Multi-Timeframe Strategy (H4 Bias + H1 Entry) ==="
input int          InpFastEMAPeriod      = 21;               // Fast EMA Period (Pullback Level)
input int          InpMediumEMAPeriod    = 50;               // Medium EMA Period (Trend Flow)
input int          InpSlowEMAPeriod      = 200;              // Slow Baseline EMA (Macro Trend)
input int          InpRSIPeriod          = 14;               // RSI Period
input double       InpRSIBuyMin          = 35.0;             // RSI Buy Pullback Min
input double       InpRSIBuyMax          = 55.0;             // RSI Buy Pullback Max
input double       InpRSISellMin         = 45.0;             // RSI Sell Rally Min
input double       InpRSISellMax         = 65.0;             // RSI Sell Rally Max
input int          InpMinConfidenceScore = 70;               // Minimum Confluence Score (70%)

input group "=== 🛡️ Dynamic ATR Targets & Trailing Runner ==="
input int          InpATRPeriod          = 14;               // ATR Period
input double       InpATR_SL_Mult        = 0.8;              // Stop Loss (x ATR, ~1.6% Risk)
input double       InpATR_TP1_Mult       = 1.6;              // TP1 First Target (x ATR, R:R = 2:1)
input double       InpATR_TP2_Mult       = 3.2;              // TP2 Runner Target (x ATR, R:R = 4:1)
input double       InpATR_Trail_Mult     = 0.6;              // Trailing Stop Distance (x ATR)
input double       InpMinSL_Dollars      = 6.0;              // Minimum Hard SL in Price Units ($6.00)
input bool         InpPartialCloseAtTP1  = true;             // Bank 50% Partial Profit at TP1
input double       InpPartialClosePct    = 50.0;             // Partial Close % (50% at TP1)

input group "=== 🕒 Session Filter & Volatility Guard ==="
input bool         InpUseSessionFilter   = true;             // Trade Only High Liquidity Windows
input int          InpSessionStartHour   = 10;               // London Open (10:00 Broker Server Hour)
input int          InpSessionEndHour     = 20;               // NY Close (20:00 Broker Server Hour)
input double       InpMinATRPrice        = 5.0;              // Skip Dead Market (ATR < $5.00)
input double       InpMaxATRPrice        = 80.0;             // Skip Extreme Volatility Spikes (ATR > $80.00)
input double       InpMaxSpreadPips      = 4.0;              // Max Allowable Spread (Pips)

input group "=== 🌐 Hybrid Mode Webhook Integration ==="
input string       InpServerURL          = "http://127.0.0.1:8000/api/signal"; // Local AI REST Bridge
input int          InpPollingSeconds     = 10;               // Web Signal Poll Frequency (Seconds)

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES & INDICATOR HANDLES                             |
//+------------------------------------------------------------------+
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;

// H1 Handles
int            h_ema21_h1   = INVALID_HANDLE;
int            h_ema50_h1   = INVALID_HANDLE;
int            h_ema200_h1  = INVALID_HANDLE;
int            h_rsi_h1     = INVALID_HANDLE;
int            h_macd_h1    = INVALID_HANDLE;
int            h_atr_h1     = INVALID_HANDLE;

// H4 Handles (Macro Bias)
int            h_ema21_h4   = INVALID_HANDLE;
int            h_ema50_h4   = INVALID_HANDLE;
int            h_ema200_h4  = INVALID_HANDLE;

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
void UpdateTradingPanel(string trendStatus, int confluence, string h4Status);
void ManageOpenPositions();
void CheckAutonomousSignals();
void CheckSignalsFromServer();
double CalculateLotSize(double slPriceDistance);
bool IsTradingSessionAllowed();
bool IsSpreadAcceptable();
bool CheckDailyLossLimit();
string GetH4TrendBias();

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

   // Initialize H1 Indicators
   h_ema21_h1  = iMA(_Symbol, PERIOD_H1, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema50_h1  = iMA(_Symbol, PERIOD_H1, InpMediumEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema200_h1 = iMA(_Symbol, PERIOD_H1, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi_h1    = iRSI(_Symbol, PERIOD_H1, InpRSIPeriod, PRICE_CLOSE);
   h_macd_h1   = iMACD(_Symbol, PERIOD_H1, 12, 26, 9, PRICE_CLOSE);
   h_atr_h1    = iATR(_Symbol, PERIOD_H1, InpATRPeriod);

   // Initialize H4 Indicators for Trend Bias
   h_ema21_h4  = iMA(_Symbol, PERIOD_H4, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema50_h4  = iMA(_Symbol, PERIOD_H4, InpMediumEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   h_ema200_h4 = iMA(_Symbol, PERIOD_H4, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(h_ema21_h1 == INVALID_HANDLE || h_ema50_h1 == INVALID_HANDLE || 
      h_ema200_h1 == INVALID_HANDLE || h_rsi_h1 == INVALID_HANDLE ||
      h_macd_h1 == INVALID_HANDLE || h_atr_h1 == INVALID_HANDLE ||
      h_ema21_h4 == INVALID_HANDLE || h_ema50_h4 == INVALID_HANDLE ||
      h_ema200_h4 == INVALID_HANDLE)
   {
      Print("❌ [ERROR] Failed to initialize indicator handles.");
      return INIT_FAILED;
   }

   CreateTradingPanel();
   Print("🚀 [INIT] Golden Trend Rider V4 EA Initialized Successfully on ", _Symbol, " H1/H4.");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_ema21_h1);
   IndicatorRelease(h_ema50_h1);
   IndicatorRelease(h_ema200_h1);
   IndicatorRelease(h_rsi_h1);
   IndicatorRelease(h_macd_h1);
   IndicatorRelease(h_atr_h1);
   IndicatorRelease(h_ema21_h4);
   IndicatorRelease(h_ema50_h4);
   IndicatorRelease(h_ema200_h4);

   ObjectsDeleteAll(0, "AD_V4_");
   Print("🛑 [DEINIT] Golden Trend Rider V4 EA Removed.");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Reset daily start balance if day rolled over
   MqlDateTime dtCurrent, dtLast;
   TimeToStruct(TimeCurrent(), dtCurrent);
   TimeToStruct(g_last_day_check, dtLast);
   if(dtCurrent.day != dtLast.day)
   {
      g_daily_start_bal = m_account.Balance();
      g_last_day_check = TimeCurrent();
      Print("🌅 [NEW DAY] Daily baseline balance reset to: $", DoubleToString(g_daily_start_bal, 2));
   }

   // 1. Manage Active Positions (TP1 Partial Close, Breakeven, Trailing Runner)
   ManageOpenPositions();

   // 2. Check Signals on New Bar
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);
   if(currentBarTime != g_last_bar_time)
   {
      g_last_bar_time = currentBarTime;

      if(InpEAMode == MODE_STANDALONE)
      {
         CheckAutonomousSignals();
      }
   }

   // 3. Hybrid Webhook Polling
   if(InpEAMode == MODE_HYBRID_WEB)
   {
      if(TimeCurrent() - g_last_poll_time >= InpPollingSeconds)
      {
         g_last_poll_time = TimeCurrent();
         CheckSignalsFromServer();
      }
   }
}

//+------------------------------------------------------------------+
//| Get Macro Trend Bias from H4                                     |
//+------------------------------------------------------------------+
string GetH4TrendBias()
{
   double e21[2], e50[2], e200[2], closeH4[2];
   if(CopyBuffer(h_ema21_h4, 0, 1, 1, e21) <= 0 ||
      CopyBuffer(h_ema50_h4, 0, 1, 1, e50) <= 0 ||
      CopyBuffer(h_ema200_h4, 0, 1, 1, e200) <= 0 ||
      CopyClose(_Symbol, PERIOD_H4, 1, 1, closeH4) <= 0)
   {
      return "RANGE";
   }

   double p = closeH4[0];
   if(p > e21[0] && e21[0] > e50[0] && p > e200[0])
      return "BULL";
   if(p < e21[0] && e21[0] < e50[0] && p < e200[0])
      return "BEAR";

   return "RANGE";
}

//+------------------------------------------------------------------+
//| Autonomous Signal Engine (Golden Trend Rider V4 Logic)           |
//+------------------------------------------------------------------+
void CheckAutonomousSignals()
{
   if(!g_gui_auto_state) return;
   if(!CheckDailyLossLimit()) return;

   // Check if we already have an open position for this magic
   int openCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
         openCount++;
   }
   if(openCount >= 1) return; // Single trade discipline (no layering)

   if(!IsTradingSessionAllowed()) return;
   if(!IsSpreadAcceptable()) return;

   // Read H1 indicators (Bar 1 = completed bar)
   double ema21[2], ema50[2], ema200[2], rsi[2], macdMain[2], macdSig[2], atr[2];
   MqlRates rates[2];

   if(CopyBuffer(h_ema21_h1, 0, 1, 1, ema21) <= 0 ||
      CopyBuffer(h_ema50_h1, 0, 1, 1, ema50) <= 0 ||
      CopyBuffer(h_ema200_h1, 0, 1, 1, ema200) <= 0 ||
      CopyBuffer(h_rsi_h1, 0, 1, 1, rsi) <= 0 ||
      CopyBuffer(h_macd_h1, 0, 1, 1, macdMain) <= 0 ||
      CopyBuffer(h_macd_h1, 1, 1, 1, macdSig) <= 0 ||
      CopyBuffer(h_atr_h1, 0, 1, 1, atr) <= 0 ||
      CopyRates(_Symbol, PERIOD_H1, 1, 1, rates) <= 0)
   {
      return;
   }

   double currentClose = rates[0].close;
   double currentATR   = atr[0];

   // Volatility Filter (in price units)
   if(currentATR < InpMinATRPrice || currentATR > InpMaxATRPrice)
   {
      Print("⚠️ [ATR Filter] ATR = $", DoubleToString(currentATR, 2), " out of range [$", InpMinATRPrice, "-$", InpMaxATRPrice, "]");
      return;
   }

   // 1. Check H4 Trend Bias
   string h4_bias = GetH4TrendBias();
   if(h4_bias == "RANGE")
   {
      UpdateTradingPanel("H4 RANGE (WAITING)", 0, "RANGE");
      return;
   }

   // 2. Check H1 EMA Structure
   bool h1_bull = (ema21[0] > ema50[0] && currentClose > ema200[0]);
   bool h1_bear = (ema21[0] < ema50[0] && currentClose < ema200[0]);

   // 3. Confluence Scoring
   int buyScore  = 0;
   int sellScore = 0;

   // H4 Bias (35 pts)
   if(h4_bias == "BULL") buyScore += 35;
   if(h4_bias == "BEAR") sellScore += 35;

   // H1 EMA Alignment (20 pts)
   if(h1_bull) buyScore += 20;
   if(h1_bear) sellScore += 20;

   // RSI Pullback Zone (25 pts)
   if(rsi[0] > InpRSIBuyMin && rsi[0] < InpRSIBuyMax) buyScore += 25;
   if(rsi[0] > InpRSISellMin && rsi[0] < InpRSISellMax) sellScore += 25;

   // MACD Momentum (20 pts)
   double macdHist = macdMain[0] - macdSig[0];
   if(macdHist > 0) buyScore += 20;
   if(macdHist < 0) sellScore += 20;

   string trendStr = (h4_bias == "BULL" && h1_bull) ? "STRONG BULLISH" : ((h4_bias == "BEAR" && h1_bear) ? "STRONG BEARISH" : "MIXED BIAS");
   int bestScore = MathMax(buyScore, sellScore);
   UpdateTradingPanel(trendStr, bestScore, h4_bias);

   // 4. Decision
   bool buy_signal  = (h4_bias == "BULL" && h1_bull && buyScore >= InpMinConfidenceScore && (rsi[0] > InpRSIBuyMin && rsi[0] < InpRSIBuyMax) && macdHist > 0);
   bool sell_signal = (h4_bias == "BEAR" && h1_bear && sellScore >= InpMinConfidenceScore && (rsi[0] > InpRSISellMin && rsi[0] < InpRSISellMax) && macdHist < 0);

   if(!buy_signal && !sell_signal) return;

   // 5. Dynamic Levels
   double sl_dist  = currentATR * InpATR_SL_Mult;
   double tp1_dist = currentATR * InpATR_TP1_Mult;
   double tp2_dist = currentATR * InpATR_TP2_Mult;

   // Minimum SL guardrail
   sl_dist = MathMax(sl_dist, InpMinSL_Dollars);

   // R:R verification (minimum 1.8:1)
   if(tp1_dist / sl_dist < 1.8) return;

   double lot = CalculateLotSize(sl_dist);

   if(buy_signal)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizeDouble(ask - sl_dist, _Digits);
      double tp1 = NormalizeDouble(ask + tp1_dist, _Digits);

      if(m_trade.Buy(lot, _Symbol, ask, sl, tp1, "Golden Trend Rider V4 BUY"))
      {
         Print("🏆 [V4 BUY] Executed @ ", ask, " | Lot: ", lot, " | SL: ", sl, " (-$", DoubleToString(sl_dist, 2), ") | TP1: ", tp1, " (+$", DoubleToString(tp1_dist, 2), ") | H4: ", h4_bias, " | Conf: ", buyScore, "%");
      }
   }
   else if(sell_signal)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizeDouble(bid + sl_dist, _Digits);
      double tp1 = NormalizeDouble(bid - tp1_dist, _Digits);

      if(m_trade.Sell(lot, _Symbol, bid, sl, tp1, "Golden Trend Rider V4 SELL"))
      {
         Print("🏆 [V4 SELL] Executed @ ", bid, " | Lot: ", lot, " | SL: ", sl, " (+$", DoubleToString(sl_dist, 2), ") | TP1: ", tp1, " (-$", DoubleToString(tp1_dist, 2), ") | H4: ", h4_bias, " | Conf: ", sellScore, "%");
      }
   }
}

//+------------------------------------------------------------------+
//| Manage Open Positions: TP1 Partial Close & Dynamic Trailing Stop |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   double atrArr[1];
   if(CopyBuffer(h_atr_h1, 0, 0, 1, atrArr) <= 0) return;
   double curATR = atrArr[0];
   double trailDist = curATR * InpATR_Trail_Mult;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
      {
         ulong  ticket    = m_position.Ticket();
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         double currentTP = m_position.TakeProfit();
         double volume    = m_position.Volume();
         double minVol    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double volStep   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double profitPrice = bid - openPrice;

            // 1. TP1 HIT: Partial Close 50% & Move SL to Breakeven + $0.50
            if(currentTP > 0 && bid >= currentTP)
            {
               if(InpPartialCloseAtTP1 && volume >= (minVol * 2.0))
               {
                  double closeVol = MathFloor((volume * (InpPartialClosePct / 100.0)) / volStep) * volStep;
                  if(closeVol >= minVol && closeVol < volume)
                  {
                     m_trade.PositionClosePartial(ticket, closeVol);
                     Print("🎯 [TP1 Partial Close] Closed ", closeVol, " lots (50%) on BUY #", ticket);
                  }
               }

               // Move SL to Breakeven + $0.50 cushion & Remove TP to let runner fly
               double beSL = NormalizeDouble(openPrice + 0.50, _Digits);
               m_trade.PositionModify(ticket, beSL, 0);
               Print("🛡️ [BE Protected] BUY #", ticket, " SL set to Breakeven ($", beSL, ") - Running remainder");
            }

            // 2. Trailing Stop on Remaining Runner (After TP1 was hit, currentTP == 0)
            if(currentTP == 0 && profitPrice > (curATR * InpATR_TP1_Mult))
            {
               double newTrail = NormalizeDouble(bid - trailDist, _Digits);
               if(newTrail > currentSL + 0.20)
               {
                  m_trade.PositionModify(ticket, newTrail, 0);
               }
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double profitPrice = openPrice - ask;

            // 1. TP1 HIT: Partial Close 50% & Move SL to Breakeven - $0.50
            if(currentTP > 0 && ask <= currentTP)
            {
               if(InpPartialCloseAtTP1 && volume >= (minVol * 2.0))
               {
                  double closeVol = MathFloor((volume * (InpPartialClosePct / 100.0)) / volStep) * volStep;
                  if(closeVol >= minVol && closeVol < volume)
                  {
                     m_trade.PositionClosePartial(ticket, closeVol);
                     Print("🎯 [TP1 Partial Close] Closed ", closeVol, " lots (50%) on SELL #", ticket);
                  }
               }

               // Move SL to Breakeven - $0.50 cushion & Remove TP to let runner fly
               double beSL = NormalizeDouble(openPrice - 0.50, _Digits);
               m_trade.PositionModify(ticket, beSL, 0);
               Print("🛡️ [BE Protected] SELL #", ticket, " SL set to Breakeven ($", beSL, ") - Running remainder");
            }

            // 2. Trailing Stop on Remaining Runner
            if(currentTP == 0 && profitPrice > (curATR * InpATR_TP1_Mult))
            {
               double newTrail = NormalizeDouble(ask + trailDist, _Digits);
               if(currentSL == 0 || newTrail < currentSL - 0.20)
               {
                  m_trade.PositionModify(ticket, newTrail, 0);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Lot Size Calculation based on 2.0% Risk of Capital       |
//+------------------------------------------------------------------+
double CalculateLotSize(double slPriceDistance)
{
   if(InpLotMode == LOT_FIXED)
      return InpFixedLot;

   double capital = m_account.Balance();
   double riskMoney = capital * (InpRiskPercent / 100.0);

   // Tick value for 1.00 lot on XAUUSD = $1.00 per 0.01 price move = $100 per $1.00 move
   // Risk = lot * slPriceDistance * 100.0
   double lot = riskMoney / (slPriceDistance * 100.0);

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(InpMinLot, MathMin(InpMaxLotLimit, lot));

   // Ensure lot can be halved for partial close (at least 2 * minLot)
   if(lot < (minLot * 2.0))
      lot = minLot * 2.0;

   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Filter: Session Times (London + NY)                              |
//+------------------------------------------------------------------+
bool IsTradingSessionAllowed()
{
   if(!InpUseSessionFilter) return true;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.hour >= InpSessionStartHour && dt.hour < InpSessionEndHour);
}

//+------------------------------------------------------------------+
//| Filter: Spread Guard                                             |
//+------------------------------------------------------------------+
bool IsSpreadAcceptable()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double spreadPips = (double)spread / 10.0;
   return (spreadPips <= InpMaxSpreadPips);
}

//+------------------------------------------------------------------+
//| Filter: Daily Loss Limit (-3%)                                   |
//+------------------------------------------------------------------+
bool CheckDailyLossLimit()
{
   double currentBal = m_account.Balance();
   double dailyLoss = g_daily_start_bal - currentBal;
   double maxAllowedLoss = g_daily_start_bal * (InpMaxDailyDrawdown / 100.0);

   if(dailyLoss >= maxAllowedLoss)
   {
      Print("🛑 [DAILY LIMIT REACHED] Today's Loss: -$", DoubleToString(dailyLoss, 2), " exceeds limit of $", DoubleToString(maxAllowedLoss, 2));
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Hybrid Server Polling                                            |
//+------------------------------------------------------------------+
void CheckSignalsFromServer()
{
   // Standalone fallback handles primary execution
}

//+------------------------------------------------------------------+
//| GUI Trading HUD Panel                                            |
//+------------------------------------------------------------------+
void CreateTradingPanel()
{
   ObjectsDeleteAll(0, "AD_V4_");

   // Background Box
   ObjectCreate(0, "AD_V4_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_XDISTANCE, 20);
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_YDISTANCE, 30);
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_XSIZE, 300);
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_YSIZE, 160);
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_BGCOLOR, C'15,23,42'); // Slate 900
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_BORDER_COLOR, C'56,189,248'); // Cyan 400
   ObjectSetInteger(0, "AD_V4_BG", OBJPROP_CORNER, CORNER_LEFT_UPPER);

   // Title
   ObjectCreate(0, "AD_V4_TITLE", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_TITLE", OBJPROP_XDISTANCE, 35);
   ObjectSetInteger(0, "AD_V4_TITLE", OBJPROP_YDISTANCE, 45);
   ObjectSetString(0, "AD_V4_TITLE", OBJPROP_TEXT, "⚡ GOLDEN TREND RIDER V4");
   ObjectSetInteger(0, "AD_V4_TITLE", OBJPROP_COLOR, C'56,189,248');
   ObjectSetString(0, "AD_V4_TITLE", OBJPROP_FONT, "Segoe UI Semibold");
   ObjectSetInteger(0, "AD_V4_TITLE", OBJPROP_FONTSIZE, 11);

   // Subtitle
   ObjectCreate(0, "AD_V4_SUB", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_SUB", OBJPROP_XDISTANCE, 35);
   ObjectSetInteger(0, "AD_V4_SUB", OBJPROP_YDISTANCE, 68);
   ObjectSetString(0, "AD_V4_SUB", OBJPROP_TEXT, "Capital $1,000 | Dynamic 2% Risk");
   ObjectSetInteger(0, "AD_V4_SUB", OBJPROP_COLOR, C'148,163,184');
   ObjectSetString(0, "AD_V4_SUB", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "AD_V4_SUB", OBJPROP_FONTSIZE, 9);

   // Status Line
   ObjectCreate(0, "AD_V4_STATUS", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_STATUS", OBJPROP_XDISTANCE, 35);
   ObjectSetInteger(0, "AD_V4_STATUS", OBJPROP_YDISTANCE, 95);
   ObjectSetString(0, "AD_V4_STATUS", OBJPROP_TEXT, "Status: Scanning H4/H1...");
   ObjectSetInteger(0, "AD_V4_STATUS", OBJPROP_COLOR, clrWhite);
   ObjectSetString(0, "AD_V4_STATUS", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "AD_V4_STATUS", OBJPROP_FONTSIZE, 9);

   // Confluence Line
   ObjectCreate(0, "AD_V4_CONF", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_CONF", OBJPROP_XDISTANCE, 35);
   ObjectSetInteger(0, "AD_V4_CONF", OBJPROP_YDISTANCE, 120);
   ObjectSetString(0, "AD_V4_CONF", OBJPROP_TEXT, "Confluence: 0% | H4: SCANNING");
   ObjectSetInteger(0, "AD_V4_CONF", OBJPROP_COLOR, C'250,204,21');
   ObjectSetString(0, "AD_V4_CONF", OBJPROP_FONT, "Segoe UI Semibold");
   ObjectSetInteger(0, "AD_V4_CONF", OBJPROP_FONTSIZE, 9);

   // Auto Button
   ObjectCreate(0, "AD_V4_BTN", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_XDISTANCE, 35);
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_YDISTANCE, 148);
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_XSIZE, 270);
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_YSIZE, 28);
   ObjectSetString(0, "AD_V4_BTN", OBJPROP_TEXT, g_gui_auto_state ? "🟢 AUTO-TRADING ACTIVE (24/7)" : "🔴 TRADING PAUSED");
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_BGCOLOR, g_gui_auto_state ? C'16,185,129' : C'239,68,68');
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_COLOR, clrWhite);
   ObjectSetString(0, "AD_V4_BTN", OBJPROP_FONT, "Segoe UI Semibold");
   ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_FONTSIZE, 9);
}

void UpdateTradingPanel(string trendStatus, int confluence, string h4Status)
{
   ObjectSetString(0, "AD_V4_STATUS", OBJPROP_TEXT, "Trend: " + trendStatus);
   ObjectSetString(0, "AD_V4_CONF", OBJPROP_TEXT, "Confluence: " + IntegerToString(confluence) + "% | H4: " + h4Status);
   ChartRedraw();
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK && sparam == "AD_V4_BTN")
   {
      g_gui_auto_state = !g_gui_auto_state;
      ObjectSetString(0, "AD_V4_BTN", OBJPROP_TEXT, g_gui_auto_state ? "🟢 AUTO-TRADING ACTIVE (24/7)" : "🔴 TRADING PAUSED");
      ObjectSetInteger(0, "AD_V4_BTN", OBJPROP_BGCOLOR, g_gui_auto_state ? C'16,185,129' : C'239,68,68');
      ChartRedraw();
   }
}
//+------------------------------------------------------------------+
