//+------------------------------------------------------------------+
//|                                          ARGOS_GoldTrend_H1.mq5  |
//|  Estrategia tendencial para XAUUSD en H1: EMA 200 + RSI 14 + ATR |
//|                                                                  |
//|  Reglas (solo velas H1 CERRADAS, evaluadas una vez por vela):    |
//|   BUY : cierre[1] > EMA200[1]  y  RSI14[1] > 55                  |
//|   SELL: cierre[1] < EMA200[1]  y  RSI14[1] < 45                  |
//|   45 <= RSI <= 55: no se abre nada.                              |
//|   SL = 2 x ATR14[1]; TP = 2 x distancia del SL (ratio 1:2).      |
//|   Volumen: riesgo = 0,5 % de la equidad si se alcanza el SL.     |
//|   Sin trailing, sin martingala, sin grid, sin cierre por señal.  |
//|                                                                  |
//|  SEGURIDAD: por defecto SOLO opera en el Strategy Tester. Para   |
//|  cuentas demo o reales hay que activarlo de forma expresa.       |
//|  Una compilación correcta NO es evidencia de rentabilidad.       |
//+------------------------------------------------------------------+
#property copyright   "ARGOS / PACO OS"
#property version     "1.00"
#property description "ARGOS Gold Trend H1: EMA200 + RSI14 + ATR14 en XAUUSD H1. Laboratorio: por defecto solo Strategy Tester."

//--- Parámetros -------------------------------------------------------
input group "Identificación"
input ulong   InpMagicNumber            = 20261010;  // Magic Number (único para este EA)
input string  InpExpectedSymbol         = "XAUUSD";  // Símbolo previsto (prefijo: admite XAUUSD., XAUUSDm...)
input bool    InpBlockOnSymbolMismatch  = true;      // Impedir operar si el símbolo no empieza por el previsto

input group "Estrategia (velas H1 cerradas)"
input int     InpEmaPeriod              = 200;       // EMA (cierre)
input int     InpRsiPeriod              = 14;        // RSI (cierre)
input int     InpAtrPeriod              = 14;        // ATR
input double  InpRsiBuyLevel            = 55.0;      // BUY si RSI > este nivel
input double  InpRsiSellLevel           = 45.0;      // SELL si RSI < este nivel
input int     InpMinHistoryBars         = 600;       // Barras H1 mínimas en el historial (calentamiento de la EMA)

input group "Riesgo y salidas"
input double  InpRiskPercent            = 0.5;       // Riesgo por operación (% de la equidad)
input double  InpSlAtrMultiplier        = 2.0;       // SL = multiplicador x ATR
input double  InpRewardRiskRatio        = 2.0;       // TP = ratio x distancia del SL
input double  InpCommissionPerLot       = 0.0;       // Comisión ida y vuelta por lote (divisa de la cuenta) sumada al riesgo
input int     InpMaxSpreadPoints        = 35;        // Spread máximo para NUEVAS entradas, en puntos (SYMBOL_POINT)
input int     InpMaxDeviationPoints     = 20;        // Desviación máxima de precio admitida al ejecutar (puntos)

input group "Registro"
input bool    InpLogEveryBar            = false;     // Registrar también las velas sin señal

input group "Seguridad de cuenta"
input bool    InpAllowDemoTrading       = false;     // Permitir operar en cuentas DEMO/CONCURSO (fuera del Tester)
input bool    InpAllowRealTrading       = false;     // Permitir operar en cuentas REALES (fuera del Tester)

//--- Estado -----------------------------------------------------------
#define EA_NAME "ARGOS_GoldTrend_H1"
const ENUM_TIMEFRAMES SIGNAL_TF = PERIOD_H1;          // las señales SIEMPRE se calculan en H1

int      g_hEma = INVALID_HANDLE;
int      g_hRsi = INVALID_HANDLE;
int      g_hAtr = INVALID_HANDLE;
datetime g_lastProcessedBar = 0;                      // apertura de la vela H1 ya evaluada
datetime g_lastWaitLogBar   = 0;                      // para no repetir el aviso de "datos no listos" en cada tick
bool     g_symbolOk = true;

enum SignalType { SIGNAL_NONE = 0, SIGNAL_BUY = 1, SIGNAL_SELL = -1 };

//+------------------------------------------------------------------+
//| Registro                                                         |
//+------------------------------------------------------------------+
void Log(const string level, const string msg)
  {
   PrintFormat("[%s][%s][%s] %s", EA_NAME, level, _Symbol, msg);
  }

//+------------------------------------------------------------------+
//| Liberación de recursos                                           |
//+------------------------------------------------------------------+
void ReleaseIndicators()
  {
   if(g_hEma != INVALID_HANDLE) { IndicatorRelease(g_hEma); g_hEma = INVALID_HANDLE; }
   if(g_hRsi != INVALID_HANDLE) { IndicatorRelease(g_hRsi); g_hRsi = INVALID_HANDLE; }
   if(g_hAtr != INVALID_HANDLE) { IndicatorRelease(g_hAtr); g_hAtr = INVALID_HANDLE; }
  }

//+------------------------------------------------------------------+
//| Textos de cuenta                                                 |
//+------------------------------------------------------------------+
string AccountModeText()
  {
   switch((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE))
     {
      case ACCOUNT_TRADE_MODE_DEMO:    return "DEMO";
      case ACCOUNT_TRADE_MODE_CONTEST: return "CONCURSO";
      case ACCOUNT_TRADE_MODE_REAL:    return "REAL";
     }
   return "DESCONOCIDA";
  }

string MarginModeText(const ENUM_ACCOUNT_MARGIN_MODE mm)
  {
   if(mm == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "hedging";
   if(mm == ACCOUNT_MARGIN_MODE_RETAIL_NETTING) return "netting";
   if(mm == ACCOUNT_MARGIN_MODE_EXCHANGE)       return "exchange (netting)";
   return "desconocido";
  }

//+------------------------------------------------------------------+
//| Precio con los dígitos del símbolo, para el registro             |
//+------------------------------------------------------------------+
string Px(const double v) { return DoubleToString(v, _Digits); }

//+------------------------------------------------------------------+
//| Validación de parámetros                                         |
//+------------------------------------------------------------------+
bool ValidateInputs()
  {
   bool ok = true;
   if(InpEmaPeriod < 2 || InpRsiPeriod < 2 || InpAtrPeriod < 1)
     { Log("ERROR", "Periodos de indicadores no válidos."); ok = false; }
   if(!(InpRsiSellLevel < InpRsiBuyLevel) || InpRsiSellLevel <= 0.0 || InpRsiBuyLevel >= 100.0)
     { Log("ERROR", "Niveles RSI no válidos: se exige 0 < venta < compra < 100."); ok = false; }
   if(InpRiskPercent <= 0.0 || InpRiskPercent > 5.0)
     { Log("ERROR", "InpRiskPercent debe estar en (0, 5]."); ok = false; }
   if(InpSlAtrMultiplier <= 0.0 || InpRewardRiskRatio <= 0.0)
     { Log("ERROR", "Multiplicador de SL y ratio de TP deben ser positivos."); ok = false; }
   if(InpCommissionPerLot < 0.0 || InpMaxSpreadPoints < 0 || InpMaxDeviationPoints < 0)
     { Log("ERROR", "Comisión, spread máximo y desviación no pueden ser negativos."); ok = false; }
   int needed = MathMax(InpEmaPeriod, MathMax(InpRsiPeriod, InpAtrPeriod)) + 2;
   if(InpMinHistoryBars < needed)
     { Log("ERROR", StringFormat("InpMinHistoryBars debe ser >= %d.", needed)); ok = false; }
   return ok;
  }

//+------------------------------------------------------------------+
//| Inicialización                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;

   if(StringLen(InpExpectedSymbol) > 0 && StringFind(_Symbol, InpExpectedSymbol) != 0)
     {
      g_symbolOk = false;
      Log("AVISO", StringFormat("El símbolo del gráfico (%s) no empieza por '%s'.", _Symbol, InpExpectedSymbol));
      if(InpBlockOnSymbolMismatch)
        {
         Log("ERROR", "Símbolo no previsto y InpBlockOnSymbolMismatch = true: el EA no se inicia.");
         return INIT_PARAMETERS_INCORRECT;
        }
     }
   if(_Period != SIGNAL_TF)
      Log("AVISO", "El gráfico no está en H1. Las señales se calculan igualmente con velas H1 (no con las del gráfico).");

   g_hEma = iMA(_Symbol, SIGNAL_TF, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_hRsi = iRSI(_Symbol, SIGNAL_TF, InpRsiPeriod, PRICE_CLOSE);
   g_hAtr = iATR(_Symbol, SIGNAL_TF, InpAtrPeriod);
   if(g_hEma == INVALID_HANDLE || g_hRsi == INVALID_HANDLE || g_hAtr == INVALID_HANDLE)
     {
      Log("ERROR", StringFormat("No se pudieron crear los indicadores (error %d).", GetLastError()));
      ReleaseIndicators();
      return INIT_FAILED;
     }

   // La vela en curso al iniciar NO se evalúa: la primera evaluación será en la próxima vela H1 nueva.
   g_lastProcessedBar = iTime(_Symbol, SIGNAL_TF, 0);

   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   Log("INFO", StringFormat("Iniciado. Magic=%I64u, cuenta %s, modo %s, Tester=%s. Punto=%.10g, dígitos=%d.",
                            InpMagicNumber, AccountModeText(), MarginModeText(mm),
                            MQLInfoInteger(MQL_TESTER) ? "sí" : "no",
                            SymbolInfoDouble(_Symbol, SYMBOL_POINT), (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Desinicialización                                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ReleaseIndicators();
   Log("INFO", StringFormat("Detenido (motivo %d).", reason));
  }

//+------------------------------------------------------------------+
//| ¿Se permite operar en este entorno?                              |
//+------------------------------------------------------------------+
bool EnvironmentAllowsTrading(string &why)
  {
   if(!g_symbolOk && InpBlockOnSymbolMismatch) { why = "símbolo no previsto"; return false; }
   if(!MQLInfoInteger(MQL_TESTER))
     {
      ENUM_ACCOUNT_TRADE_MODE am = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
      if(am == ACCOUNT_TRADE_MODE_REAL && !InpAllowRealTrading)
        { why = "cuenta REAL y InpAllowRealTrading = false"; return false; }
      if((am == ACCOUNT_TRADE_MODE_DEMO || am == ACCOUNT_TRADE_MODE_CONTEST) && !InpAllowDemoTrading)
        { why = "cuenta DEMO/CONCURSO y InpAllowDemoTrading = false"; return false; }
      if(am != ACCOUNT_TRADE_MODE_REAL && am != ACCOUNT_TRADE_MODE_DEMO && am != ACCOUNT_TRADE_MODE_CONTEST)
        { why = "tipo de cuenta desconocido"; return false; }
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) { why = "trading algorítmico desactivado en el terminal"; return false; }
     }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))           { why = "el EA no tiene permiso de trading"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))   { why = "la cuenta no permite operar"; return false; }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))    { why = "la cuenta no permite operar a expertos"; return false; }
   return true;
  }

//+------------------------------------------------------------------+
//| Lectura de un valor de un indicador en la vela CERRADA (shift 1) |
//+------------------------------------------------------------------+
bool ReadClosedBarValue(const int handle, double &value)
  {
   double buf[];
   ResetLastError();
   if(CopyBuffer(handle, 0, 1, 1, buf) != 1)
      return false;
   value = buf[0];
   return (value != EMPTY_VALUE && MathIsValidNumber(value));
  }

//+------------------------------------------------------------------+
//| Datos de la última vela H1 completada                            |
//+------------------------------------------------------------------+
struct BarData
  {
   datetime time;
   double   close;
   double   ema;
   double   rsi;
   double   atr;
  };

bool LoadClosedBar(BarData &bar, string &why)
  {
   if(!SeriesInfoInteger(_Symbol, SIGNAL_TF, SERIES_SYNCHRONIZED)) { why = "historial H1 no sincronizado"; return false; }
   int bars = Bars(_Symbol, SIGNAL_TF);
   if(bars < InpMinHistoryBars) { why = StringFormat("historial insuficiente (%d < %d barras H1)", bars, InpMinHistoryBars); return false; }
   int need = MathMax(InpEmaPeriod, MathMax(InpRsiPeriod, InpAtrPeriod)) + 2;
   if(BarsCalculated(g_hEma) < need || BarsCalculated(g_hRsi) < need || BarsCalculated(g_hAtr) < need)
     { why = "indicadores aún sin calcular"; return false; }

   MqlRates rates[];
   if(CopyRates(_Symbol, SIGNAL_TF, 1, 1, rates) != 1) { why = StringFormat("no se pudo leer la vela cerrada (error %d)", GetLastError()); return false; }
   bar.time  = rates[0].time;
   bar.close = rates[0].close;
   if(!ReadClosedBarValue(g_hEma, bar.ema) || !ReadClosedBarValue(g_hRsi, bar.rsi) || !ReadClosedBarValue(g_hAtr, bar.atr))
     { why = StringFormat("valores de indicador no disponibles (error %d)", GetLastError()); return false; }
   if(bar.close <= 0.0 || bar.ema <= 0.0)      { why = "precio o EMA no válidos"; return false; }
   if(bar.rsi < 0.0 || bar.rsi > 100.0)        { why = "RSI fuera de [0, 100]"; return false; }
   if(bar.atr <= 0.0)                          { why = "ATR cero o negativo"; return false; }
   return true;
  }

//+------------------------------------------------------------------+
//| Regla de señal (pura: solo usa la vela cerrada)                  |
//+------------------------------------------------------------------+
SignalType EvaluateSignal(const BarData &bar)
  {
   if(bar.close > bar.ema && bar.rsi > InpRsiBuyLevel)  return SIGNAL_BUY;
   if(bar.close < bar.ema && bar.rsi < InpRsiSellLevel) return SIGNAL_SELL;
   return SIGNAL_NONE;   // incluye 45 <= RSI <= 55 y cierre == EMA
  }

//+------------------------------------------------------------------+
//| Situación de posiciones del símbolo                              |
//|  devuelve false si no puede confirmarse con seguridad            |
//+------------------------------------------------------------------+
bool PositionsAllowEntry(string &why)
  {
   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   bool hedging = (mm == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) { why = StringFormat("no se pudo leer la posición %d (error %d)", i, GetLastError()); return false; }
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
        { why = "ya hay una posición de este EA"; return false; }
      if(!hedging)
        { why = "cuenta netting con una posición del símbolo de otra estrategia o manual: no se puede garantizar el aislamiento"; return false; }
     }
   if(!hedging)
     {
      // En netting, una orden pendiente ajena podría modificar la posición neta.
      int orders = OrdersTotal();
      for(int j = 0; j < orders; j++)
        {
         ulong ot = OrderGetTicket(j);
         if(ot == 0) { why = StringFormat("no se pudo leer la orden %d (error %d)", j, GetLastError()); return false; }
         if(OrderGetString(ORDER_SYMBOL) == _Symbol)
           { why = "cuenta netting con órdenes pendientes en el símbolo: no se puede garantizar el aislamiento"; return false; }
        }
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Utilidades de precio y volumen                                   |
//+------------------------------------------------------------------+
double TickSize()
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0.0) ? ts : SymbolInfoDouble(_Symbol, SYMBOL_POINT);
  }

double RoundToTick(const double price)
  {
   double ts = TickSize();
   return NormalizeDouble(MathRound(price / ts) * ts, _Digits);
  }

// Redondea alejándose del precio de entrada (dir = -1 hacia abajo, +1 hacia arriba).
double RoundToTickAway(const double price, const int dir)
  {
   double ts = TickSize();
   double steps = price / ts;
   double r = (dir < 0) ? MathFloor(steps + 1e-9) : MathCeil(steps - 1e-9);
   return NormalizeDouble(r * ts, _Digits);
  }

int VolumeDigits(const double step)
  {
   int d = 0;
   double s = step;
   while(d < 8 && MathAbs(s - MathRound(s)) > 1e-9) { s *= 10.0; d++; }
   return d;
  }

ENUM_ORDER_TYPE_FILLING ChooseFilling()
  {
   long modes = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((modes & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if((modes & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }

//+------------------------------------------------------------------+
//| Pérdida monetaria por 1 lote si se alcanza el SL                 |
//+------------------------------------------------------------------+
bool LossPerLot(const ENUM_ORDER_TYPE type, const double entry, const double sl, double &loss, string &why)
  {
   double profit = 0.0;
   ResetLastError();
   bool okCalc = OrderCalcProfit(type, _Symbol, 1.0, entry, sl, profit);
   double byCalc = (okCalc && profit < 0.0) ? -profit : 0.0;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0) tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double byTick = (tickValue > 0.0 && ts > 0.0) ? MathAbs(entry - sl) / ts * tickValue : 0.0;

   if(byCalc <= 0.0 && byTick <= 0.0)
     { why = StringFormat("no se puede calcular el riesgo monetario (OrderCalcProfit=%s, error %d; valor de tick=%.10g)",
                          okCalc ? "sí" : "no", GetLastError(), tickValue); return false; }
   if(byCalc > 0.0 && byTick > 0.0 && MathAbs(byCalc - byTick) > 0.05 * MathMax(byCalc, byTick))
      Log("AVISO", StringFormat("OrderCalcProfit (%.2f) y valor de tick (%.2f) difieren más de un 5%%: se usa la pérdida MAYOR.",
                                byCalc, byTick));
   loss = MathMax(byCalc, byTick) + InpCommissionPerLot;
   return true;
  }

//+------------------------------------------------------------------+
//| Plan de la operación: niveles y volumen                          |
//+------------------------------------------------------------------+
struct TradePlan
  {
   ENUM_ORDER_TYPE type;
   double entry;      // precio previsto (Ask en compra, Bid en venta)
   double sl;
   double tp;
   double slDist;     // distancia de precio del SL, ya redondeada
   double volume;
   double riskMoney;  // riesgo objetivo
   double riskReal;   // riesgo con el volumen redondeado
  };

bool BuildPlan(const SignalType sig, const BarData &bar, TradePlan &p, string &why)
  {
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick) || tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid)
     { why = "precios Bid/Ask no válidos"; return false; }

   // Spread en PUNTOS del bróker (SYMBOL_POINT). 35 puntos no son necesariamente 35 centavos.
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) { why = "SYMBOL_POINT no válido"; return false; }
   double spreadPts = (tick.ask - tick.bid) / point;
   if(spreadPts > InpMaxSpreadPoints + 1e-9)
     { why = StringFormat("spread %.1f puntos > máximo %d", spreadPts, InpMaxSpreadPoints); return false; }

   ENUM_SYMBOL_TRADE_MODE tm = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(tm == SYMBOL_TRADE_MODE_DISABLED || tm == SYMBOL_TRADE_MODE_CLOSEONLY ||
      (sig == SIGNAL_BUY && tm == SYMBOL_TRADE_MODE_SHORTONLY) || (sig == SIGNAL_SELL && tm == SYMBOL_TRADE_MODE_LONGONLY))
     { why = "el símbolo no admite esta dirección de entrada ahora"; return false; }

   p.type  = (sig == SIGNAL_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   p.entry = (sig == SIGNAL_BUY) ? tick.ask : tick.bid;
   double rawDist = InpSlAtrMultiplier * bar.atr;
   if(sig == SIGNAL_BUY)
     {
      p.sl = RoundToTickAway(p.entry - rawDist, -1);
      p.slDist = p.entry - p.sl;
      p.tp = RoundToTick(p.entry + InpRewardRiskRatio * p.slDist);
     }
   else
     {
      p.sl = RoundToTickAway(p.entry + rawDist, +1);
      p.slDist = p.sl - p.entry;
      p.tp = RoundToTick(p.entry - InpRewardRiskRatio * p.slDist);
     }
   if(p.slDist <= 0.0 || p.sl <= 0.0 || p.tp <= 0.0) { why = "niveles de SL/TP no válidos"; return false; }

   // Distancia mínima de stops del bróker (respecto al precio de cierre de la posición: Bid en compras, Ask en ventas).
   double minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double ref = (sig == SIGNAL_BUY) ? tick.bid : tick.ask;
   if(MathAbs(ref - p.sl) < minDist || MathAbs(p.tp - ref) < minDist)
     { why = StringFormat("SL/TP más cerca que el mínimo del bróker (%.10g)", minDist); return false; }

   // Volumen por riesgo.
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity <= 0.0) { why = "equidad no válida"; return false; }
   p.riskMoney = equity * InpRiskPercent / 100.0;
   double lossLot = 0.0;
   if(!LossPerLot(p.type, p.entry, p.sl, lossLot, why)) return false;

   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vlim = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_LIMIT);
   if(vmin <= 0.0 || vmax <= 0.0 || step <= 0.0) { why = "especificaciones de volumen del símbolo no válidas"; return false; }

   double raw = p.riskMoney / lossLot;
   double vol = MathFloor(raw / step + 1e-9) * step;           // SIEMPRE hacia abajo
   vol = MathMin(vol, vmax);
   if(vlim > 0.0) vol = MathMin(vol, vlim);                     // límite total del símbolo (sin posiciones del EA abiertas)
   vol = NormalizeDouble(MathFloor(vol / step + 1e-9) * step, VolumeDigits(step));
   if(vol < vmin - 1e-12)
     { why = StringFormat("el volumen mínimo (%.2f) supera el riesgo permitido (%.2f para %.4f lotes)", vmin, p.riskMoney, raw); return false; }
   p.volume = vol;
   p.riskReal = vol * lossLot;
   if(p.riskReal > p.riskMoney * (1.0 + 1e-9))
     { why = "el volumen redondeado supera el riesgo objetivo"; return false; }

   // Margen.
   double margin = 0.0;
   if(!OrderCalcMargin(p.type, _Symbol, p.volume, p.entry, margin) || margin <= 0.0)
     { why = StringFormat("no se pudo calcular el margen (error %d)", GetLastError()); return false; }
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(margin > freeMargin)
     { why = StringFormat("margen insuficiente (necesario %.2f, libre %.2f)", margin, freeMargin); return false; }
   return true;
  }

//+------------------------------------------------------------------+
//| Si el precio real difiere del previsto, recoloca SL y TP a la    |
//| MISMA distancia desde el precio real (riesgo por lote y ratio 1:2 |
//| se conservan). Si el bróker no lo permite, se mantienen los      |
//| niveles enviados y se registra.                                  |
//+------------------------------------------------------------------+
void AlignStopsToFill(const TradePlan &p, const MqlTradeResult &res)
  {
   double fill = res.price;
   ulong positionTicket = 0;
   if(res.deal > 0 && HistoryDealSelect(res.deal))
     {
      fill = HistoryDealGetDouble(res.deal, DEAL_PRICE);
      positionTicket = (ulong)HistoryDealGetInteger(res.deal, DEAL_POSITION_ID);
     }
   if(fill <= 0.0) { Log("AVISO", "Precio de ejecución no disponible: se mantienen SL/TP enviados."); return; }
   if(MathAbs(fill - p.entry) < TickSize() / 2.0) return;   // sin deslizamiento relevante

   double sl, tp;
   if(p.type == ORDER_TYPE_BUY) { sl = RoundToTick(fill - p.slDist); tp = RoundToTick(fill + InpRewardRiskRatio * p.slDist); }
   else                         { sl = RoundToTick(fill + p.slDist); tp = RoundToTick(fill - InpRewardRiskRatio * p.slDist); }

   bool selected = (positionTicket > 0) ? PositionSelectByTicket(positionTicket) : PositionSelect(_Symbol);
   if(!selected || (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
     { Log("AVISO", "No se pudo seleccionar la posición del EA para recolocar SL/TP: se mantienen los enviados."); return; }

   MqlTick tick;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minDist = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
                            (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * point;
   if(!SymbolInfoTick(_Symbol, tick)) { Log("AVISO", "Sin precio actual: se mantienen SL/TP enviados."); return; }
   double ref = (p.type == ORDER_TYPE_BUY) ? tick.bid : tick.ask;
   if(MathAbs(ref - sl) < minDist || MathAbs(tp - ref) < minDist)
     { Log("AVISO", "Los niveles ajustados al precio real violarían la distancia mínima: se mantienen los enviados."); return; }

   MqlTradeRequest req;
   MqlTradeResult  r;
   ZeroMemory(req); ZeroMemory(r);
   req.action   = TRADE_ACTION_SLTP;
   req.symbol   = _Symbol;
   req.position = (ulong)PositionGetInteger(POSITION_TICKET);
   req.sl       = sl;
   req.tp       = tp;
   req.magic    = InpMagicNumber;
   if(!OrderSend(req, r) || r.retcode != TRADE_RETCODE_DONE)
      Log("AVISO", StringFormat("No se pudieron recolocar SL/TP (retcode %u, %s): se mantienen SL %s / TP %s.",
                                r.retcode, r.comment, Px(p.sl), Px(p.tp)));
   else
      Log("INFO", StringFormat("SL/TP recolocados al precio real %s: SL %s · TP %s (misma distancia, ratio 1:%.1f).",
                               Px(fill), Px(sl), Px(tp), InpRewardRiskRatio));
  }

//+------------------------------------------------------------------+
//| Envío (una sola vez, sin bucles de reintento)                    |
//+------------------------------------------------------------------+
bool SendEntry(const TradePlan &p)
  {
   MqlTradeRequest req;
   MqlTradeResult  res;
   MqlTradeCheckResult chk;
   ZeroMemory(req); ZeroMemory(res); ZeroMemory(chk);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = p.volume;
   req.type         = p.type;
   req.price        = p.entry;
   req.sl           = p.sl;
   req.tp           = p.tp;
   req.deviation    = (ulong)InpMaxDeviationPoints;
   req.magic        = InpMagicNumber;
   req.type_filling = ChooseFilling();
   req.comment      = EA_NAME;

   if(!OrderCheck(req, chk))
     {
      Log("ERROR", StringFormat("OrderCheck rechaza la orden: retcode %u (%s). No se envía.", chk.retcode, chk.comment));
      return false;
     }
   ResetLastError();
   bool sent = OrderSend(req, res);
   if(!sent || (res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_DONE_PARTIAL))
     {
      Log("ERROR", StringFormat("OrderSend falla: retcode %u (%s), error %d. No se reintenta.", res.retcode, res.comment, GetLastError()));
      return false;
     }
   Log("INFO", StringFormat("%s %.2f lotes · previsto %s · ejecutado %s · SL %s · TP %s · riesgo %.2f (objetivo %.2f) · deal %I64u",
                            p.type == ORDER_TYPE_BUY ? "BUY" : "SELL", res.volume, Px(p.entry), Px(res.price),
                            Px(p.sl), Px(p.tp), p.riskReal, p.riskMoney, res.deal));
   AlignStopsToFill(p, res);
   return true;
  }

//+------------------------------------------------------------------+
//| Bucle principal: una evaluación por vela H1 nueva                |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime current = iTime(_Symbol, SIGNAL_TF, 0);
   if(current == 0 || current == g_lastProcessedBar)
      return;                                   // misma vela: nada que hacer (evita duplicados por ticks repetidos)
   if(g_lastProcessedBar == 0)
     {
      // Sin vela de referencia al iniciar (historial aún no cargado): la vela actual no se evalúa.
      g_lastProcessedBar = current;
      return;
     }

   BarData bar;
   string why = "";
   if(!LoadClosedBar(bar, why))
     {
      // Datos aún no listos: NO se marca la vela como procesada; se reintenta la LECTURA en el próximo tick.
      // No hay ninguna orden en juego, así que esto no puede duplicar operaciones.
      if(g_lastWaitLogBar != current)
        {
         Log("INFO", "Vela nueva sin evaluar todavía: " + why + ".");
         g_lastWaitLogBar = current;
        }
      return;
     }
   g_lastProcessedBar = current;                // a partir de aquí la vela cuenta como evaluada pase lo que pase

   SignalType sig = EvaluateSignal(bar);
   string base = StringFormat("Vela %s: cierre %s · EMA%d %s · RSI%d %.2f · ATR%d %s",
                              TimeToString(bar.time, TIME_DATE | TIME_MINUTES), Px(bar.close), InpEmaPeriod,
                              Px(bar.ema), InpRsiPeriod, bar.rsi, InpAtrPeriod, Px(bar.atr));
   if(sig == SIGNAL_NONE)
     {
      if(InpLogEveryBar) Log("INFO", base + " → sin señal.");
      return;
     }

   string sigText = (sig == SIGNAL_BUY) ? "BUY" : "SELL";
   if(!EnvironmentAllowsTrading(why))  { Log("INFO", base + " → señal " + sigText + " NO ejecutada: " + why + "."); return; }
   if(!PositionsAllowEntry(why))       { Log("INFO", base + " → señal " + sigText + " NO ejecutada: " + why + "."); return; }

   TradePlan plan;
   if(!BuildPlan(sig, bar, plan, why)) { Log("INFO", base + " → señal " + sigText + " NO ejecutada: " + why + "."); return; }

   Log("INFO", base + " → señal " + sigText + ": se envía la orden.");
   SendEntry(plan);                             // un único intento por vela
  }
//+------------------------------------------------------------------+
