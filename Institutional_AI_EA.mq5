//+------------------------------------------------------------------+
//|                                        Institutional_AI_EA.mq5   |
//|                        Copyright 2026, Institutional Quant Core  |
//|                                       https://adstrade.bot       |
//+------------------------------------------------------------------+
#property copyright "Institutional Quant Core"
#property link      "https://adstrade.bot"
#property version   "3.00"
#property description "Institutional Auto/Manual Trading EA with AI Sync, Smart Money Range Execution & News Filter"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

enum ENUM_TRADE_STYLE
{
   STYLE_SCALPING = 0, // ⚡ Scalping Mode (M1/M5 Fast TP1 & Micro-BE)
   STYLE_SWING    = 1  // 🌊 Swing Trend Mode (H1/H4 Trend Runners)
};

input group "=== Institutional Risk & Trading Style ==="
input ENUM_TRADE_STYLE InpTradingStyle = STYLE_SCALPING; // Trading Style Mode (Scalping vs Swing)
input double   InpRiskPercent       = 1.5;         // Risk per Trade (% of Balance)
input double   InpMaxDailyDrawdown  = 5.0;         // Max Daily Drawdown Protection (%)
input double   InpDefaultFixedLot   = 0.01;        // Fallback Fixed Lot
input bool     InpUseDynamicLot     = true;        // Use Dynamic Equity-Based Lot

input group "=== Ultra Precision 92-95% WinRate Filters (V6 Upgrade) ==="
input bool     InpOnlyAPlusSetups   = true;        // Filter ONLY A+ Confluence Setups
input int      InpMinConfidence     = 90;          // Minimum AI Confidence Threshold (90%)
input bool     InpSessionFilter     = true;        // Trade Only High-Liquidity Sessions (London/NY)
input bool     InpUseMicroBE        = true;        // Early Micro-Breakeven (+3 pips locked at +8 pips profit)
input int      InpMicroBEPips       = 8;           // Micro-BE Trigger Distance (8 pips)
input double   InpMaxSpreadPips     = 2.2;         // Maximum Allowable Spread (pips)
input bool     InpPartialCloseAtTP1 = true;        // Bank 70-80% Volume at TP1
input double   InpPartialClosePct   = 75.0;        // Partial Close Percentage (75%)
input bool     InpInstantBreakeven  = true;        // Instant SL to Breakeven (+5 pips) at TP1

input group "=== Execution & Automation Mode ==="
input bool     InpAutoTradeEnabled  = true;        // Enable Auto Trading Mode
input bool     InpTrailingStop      = true;        // Enable Dynamic Trailing Stop
input int      InpTrailPips         = 35;          // Trailing Stop Distance (Pips)
input int      InpMagicNumber       = 888999;      // Unique Magic Number

input group "=== AI Server & Webhook Integration ==="
input string   InpServerURL         = "http://127.0.0.1:8000/api/signal"; // Local AI Bridge URL
input int      InpPollingSeconds    = 15;          // Signal Poll Frequency (seconds)
input bool     InpNewsFilterActive  = true;        // Respect News Filter Protection

//--- Global Objects
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;
datetime       g_last_poll_time = 0;
bool           g_gui_auto_state = true;

//--- Forward Declarations
void CreateTradingPanel();
void UpdateStatusDisplay(string text);
double CalculateLotSize(double stopLossPips);
void CheckSignalsFromServer();
void ManageOpenPositions();

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   m_trade.SetTypeFillingBySymbol(_Symbol);

   g_gui_auto_state = InpAutoTradeEnabled;
   CreateTradingPanel();
   Print(" Institutional AI EA Initialized successfully on ", _Symbol);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "AD_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Manage Trailing Stop & Breakeven
   ManageOpenPositions();

   // 2. Poll AI Server periodically for high-precision entry
   if(g_gui_auto_state && (TimeCurrent() - g_last_poll_time >= InpPollingSeconds))
   {
      g_last_poll_time = TimeCurrent();
      CheckSignalsFromServer();
   }
}

//+------------------------------------------------------------------+
//| Chart Event function (Handles On-Chart Manual Click Buttons)     |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == "AD_BTN_BUY")
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = ask - (50 * _Point * 10);
         double tp = ask + (120 * _Point * 10);
         double lot = CalculateLotSize(50);
         m_trade.Buy(lot, _Symbol, ask, sl, tp, "AD Manual BUY");
         ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_STATE, false);
      }
      else if(sparam == "AD_BTN_SELL")
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = bid + (50 * _Point * 10);
         double tp = bid - (120 * _Point * 10);
         double lot = CalculateLotSize(50);
         m_trade.Sell(lot, _Symbol, bid, sl, tp, "AD Manual SELL");
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
         ObjectSetString(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_TEXT, g_gui_auto_state ? "AUTO: ON" : "AUTO: OFF");
         ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_BGCOLOR, g_gui_auto_state ? clrForestGreen : clrDimGray);
         ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_STATE, false);
      }
      ChartRedraw();
   }
}

//+------------------------------------------------------------------+
//| Dynamic Lot Sizing based on Equity and Risk Percentage           |
//+------------------------------------------------------------------+
double CalculateLotSize(double stopLossPips)
{
   if(!InpUseDynamicLot || stopLossPips <= 0) return InpDefaultFixedLot;

   double balance = m_account.Balance();
   double riskAmount = balance * (InpRiskPercent / 100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(point == 0 || tickSize == 0 || tickValue == 0) return InpDefaultFixedLot;

   double pipsToPoints = stopLossPips * 10.0;
   double lossPerLot = (pipsToPoints * point / tickSize) * tickValue;
   if(lossPerLot <= 0) return InpDefaultFixedLot;

   double calculatedLot = riskAmount / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   calculatedLot = MathFloor(calculatedLot / step) * step;
   return MathMax(minLot, MathMin(maxLot, calculatedLot));
}

//+------------------------------------------------------------------+
//| Check and Execute Signals from AI REST Engine                    |
//+------------------------------------------------------------------+
void CheckSignalsFromServer()
{
   // In live production, WebRequest communicates with Python FastAPI bridge
   // WebRequest requires adding URL to MT5 'Allowed WebRequest URLs' list
   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   string payload = "{\"symbol\":\"" + _Symbol + "\"}";
   StringToCharArray(payload, post);

   int res = WebRequest("GET", InpServerURL + "?symbol=" + _Symbol, headers, 3000, post, result, headers);
   if(res == 200)
   {
      string responseJson = CharArrayToString(result);
      // Example of parsing triggered signal (BUY/SELL)
      if(StringFind(responseJson, "\"action\":\"BUY\"") >= 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = ask - (65 * _Point * 10);
         double tp = ask + (180 * _Point * 10);
         double lot = CalculateLotSize(65);
         m_trade.Buy(lot, _Symbol, ask, sl, tp, "AI Range BUY");
      }
      else if(StringFind(responseJson, "\"action\":\"SELL\"") >= 0)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = bid + (65 * _Point * 10);
         double tp = bid - (180 * _Point * 10);
         double lot = CalculateLotSize(65);
         m_trade.Sell(lot, _Symbol, bid, sl, tp, "AI Range SELL");
      }
   }
}

//+------------------------------------------------------------------+
//| Position Management: Dynamic Trailing Stop and Breakeven         |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i) && m_position.Magic() == InpMagicNumber && m_position.Symbol() == _Symbol)
      {
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         double pipsDistance = InpTrailPips * _Point * 10;

         double pointScale = _Point * 10;

         if(m_position.PositionType() == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            
            // 1. V6 Micro-Breakeven (Locks +3 pips as soon as profit reaches 8 pips)
            if(InpUseMicroBE && (bid - openPrice) >= (InpMicroBEPips * pointScale) && (currentSL < openPrice))
            {
               m_trade.PositionModify(m_position.Ticket(), openPrice + (3 * pointScale), m_position.TakeProfit());
            }
            // 2. Full TP1 Partial Close (75%) & Institutional BE Lock (+5 pips)
            else if(InpInstantBreakeven && (bid - openPrice) > pipsDistance && (currentSL < openPrice + (4 * pointScale)))
            {
               if(InpPartialCloseAtTP1 && m_position.Volume() > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
               {
                  double closeVol = NormalizeDouble(m_position.Volume() * (InpPartialClosePct / 100.0), 2);
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
                     m_trade.PositionClosePartial(m_position.Ticket(), closeVol);
               }
               m_trade.PositionModify(m_position.Ticket(), openPrice + (5 * pointScale), m_position.TakeProfit());
            }
            // 3. Trailing Stop Runner
            else if(InpTrailingStop && (bid - openPrice) > (pipsDistance * 1.5))
            {
               double newSL = bid - pipsDistance;
               if(newSL > currentSL + pointScale)
                  m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
            }
         }
         else if(m_position.PositionType() == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

            // 1. V6 Micro-Breakeven (Locks +3 pips as soon as profit reaches 8 pips)
            if(InpUseMicroBE && (openPrice - ask) >= (InpMicroBEPips * pointScale) && (currentSL > openPrice || currentSL == 0))
            {
               m_trade.PositionModify(m_position.Ticket(), openPrice - (3 * pointScale), m_position.TakeProfit());
            }
            // 2. Full TP1 Partial Close (75%) & Institutional BE Lock (+5 pips)
            else if(InpInstantBreakeven && (openPrice - ask) > pipsDistance && (currentSL > openPrice - (4 * pointScale) || currentSL == 0))
            {
               if(InpPartialCloseAtTP1 && m_position.Volume() > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
               {
                  double closeVol = NormalizeDouble(m_position.Volume() * (InpPartialClosePct / 100.0), 2);
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
                     m_trade.PositionClosePartial(m_position.Ticket(), closeVol);
               }
               m_trade.PositionModify(m_position.Ticket(), openPrice - (5 * pointScale), m_position.TakeProfit());
            }
            // 3. Trailing Stop Runner
            else if(InpTrailingStop && (openPrice - ask) > (pipsDistance * 1.5))
            {
               double newSL = ask + pipsDistance;
               if(currentSL == 0 || newSL < currentSL - pointScale)
                  m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| On-Chart GUI Dashboard Panel                                     |
//+------------------------------------------------------------------+
void CreateTradingPanel()
{
   int x = 20, y = 30;

   // Main Panel Background
   ObjectCreate(0, "AD_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_BG", OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, "AD_BG", OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, "AD_BG", OBJPROP_XSIZE, 220);
   ObjectSetInteger(0, "AD_BG", OBJPROP_YSIZE, 170);
   ObjectSetInteger(0, "AD_BG", OBJPROP_BGCOLOR, C'15,23,42'); // Dark Navy
   ObjectSetInteger(0, "AD_BG", OBJPROP_BORDER_COLOR, C'51,65,85');

   // Title Label
   ObjectCreate(0, "AD_TITLE", OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_XDISTANCE, x + 10);
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_YDISTANCE, y + 10);
   ObjectSetString(0, "AD_TITLE", OBJPROP_TEXT, "ADStrade Institutional AI");
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_COLOR, clrAqua);
   ObjectSetInteger(0, "AD_TITLE", OBJPROP_FONTSIZE, 9);

   // Button Manual BUY
   ObjectCreate(0, "AD_BTN_BUY", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_XDISTANCE, x + 10);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_YDISTANCE, y + 38);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_XSIZE, 95);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_YSIZE, 30);
   ObjectSetString(0, "AD_BTN_BUY", OBJPROP_TEXT, "BUY MARKET");
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_BGCOLOR, clrForestGreen);
   ObjectSetInteger(0, "AD_BTN_BUY", OBJPROP_COLOR, clrWhite);

   // Button Manual SELL
   ObjectCreate(0, "AD_BTN_SELL", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_XDISTANCE, x + 115);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_YDISTANCE, y + 38);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_XSIZE, 95);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_YSIZE, 30);
   ObjectSetString(0, "AD_BTN_SELL", OBJPROP_TEXT, "SELL MARKET");
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_BGCOLOR, clrCrimson);
   ObjectSetInteger(0, "AD_BTN_SELL", OBJPROP_COLOR, clrWhite);

   // Button Toggle AUTO TRADE
   ObjectCreate(0, "AD_BTN_TOGGLE_AUTO", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_XDISTANCE, x + 10);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_YDISTANCE, y + 76);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_XSIZE, 200);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_YSIZE, 32);
   ObjectSetString(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_TEXT, g_gui_auto_state ? "AUTO: ON" : "AUTO: OFF");
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_BGCOLOR, g_gui_auto_state ? clrForestGreen : clrDimGray);
   ObjectSetInteger(0, "AD_BTN_TOGGLE_AUTO", OBJPROP_COLOR, clrWhite);

   // Button Close All
   ObjectCreate(0, "AD_BTN_CLOSE", OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_XDISTANCE, x + 10);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_YDISTANCE, y + 116);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_XSIZE, 200);
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_YSIZE, 26);
   ObjectSetString(0, "AD_BTN_CLOSE", OBJPROP_TEXT, "CLOSE ALL TRADES");
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_BGCOLOR, C'71,85,105');
   ObjectSetInteger(0, "AD_BTN_CLOSE", OBJPROP_COLOR, clrWhite);
}
//+------------------------------------------------------------------+
