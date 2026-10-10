"""Comprobaciones ESTÁTICAS del Expert Advisor ARGOS_GoldTrend_H1 (MQL5).

Esto NO es una compilación: en este entorno no hay MetaTrader 5 ni MetaEditor. Estas pruebas solo leen el
texto del .mq5 y verifican estructura, parámetros por defecto y salvaguardas. La compilación real debe hacerse en
MetaEditor (ver argos/mt5/ARGOS_GoldTrend_H1/README.md).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EA = ROOT / "mt5" / "ARGOS_GoldTrend_H1" / "ARGOS_GoldTrend_H1.mq5"


@pytest.fixture(scope="module")
def src():
    raw = EA.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "Se guarda con BOM UTF-8 para que MetaEditor lea bien los acentos."
    return raw.decode("utf-8-sig")


def strip_comments_and_strings(code: str) -> str:
    """Elimina comentarios y literales de texto (sustituye su contenido por espacios)."""
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if code.startswith("//", i):
            j = code.find("\n", i)
            i = n if j < 0 else j
        elif code.startswith("/*", i):
            j = code.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "\"'":
            j = i + 1
            while j < n and code[j] != c:
                j += 2 if code[j] == "\\" else 1
            out.append(c + " " * (j - i - 1) + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


@pytest.fixture(scope="module")
def code(src):
    return strip_comments_and_strings(src)


def body_of(code: str, signature: str) -> str:
    i = code.index(signature)
    j = code.index("{", i)
    depth, k = 0, j
    while True:
        depth += {"{": 1, "}": -1}.get(code[k], 0)
        if depth == 0:
            return code[j:k + 1]
        k += 1


def test_brackets_are_balanced(code):
    for a, b in ("()", "[]", "{}"):
        assert code.count(a) == code.count(b), f"{a}{b} desbalanceados"
    depth = 0
    for ch in code:
        depth += {"{": 1, "}": -1}.get(ch, 0)
        assert depth >= 0


def test_is_mql5_not_mql4(code):
    forbidden = [r"\bMarketInfo\s*\(", r"\bSELECT_BY_POS\b", r"\bOrderClose\s*\(", r"\bRefreshRates\s*\(",
                 r"\bint\s+start\s*\(", r"\bint\s+init\s*\(", r"\b(Ask|Bid)\b", r"#property\s+strict",
                 r"\bOrdersHistoryTotal\s*\("]
    for pat in forbidden:
        assert not re.search(pat, code), f"construcción MQL4: {pat}"
    for fn in ("int OnInit()", "void OnDeinit(const int reason)", "void OnTick()"):
        assert fn in code


@pytest.mark.parametrize("name, value", [
    ("InpRiskPercent", "0.5"), ("InpEmaPeriod", "200"), ("InpRsiPeriod", "14"), ("InpAtrPeriod", "14"),
    ("InpRsiBuyLevel", "55.0"), ("InpRsiSellLevel", "45.0"), ("InpSlAtrMultiplier", "2.0"),
    ("InpRewardRiskRatio", "2.0"), ("InpMaxSpreadPoints", "35"),
    ("InpAllowDemoTrading", "false"), ("InpAllowRealTrading", "false"),
])
def test_input_defaults_match_the_specification(src, name, value):
    m = re.search(rf"^input\s+\w+\s+{name}\s*=\s*([^;]+);", src, re.M)
    assert m and m.group(1).strip() == value, name


def test_indicators_use_handles_on_h1_closed_bars_and_are_released(code):
    assert "PERIOD_H1" in code
    assert re.search(r"iMA\(_Symbol, SIGNAL_TF, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE\)", code)
    assert re.search(r"iRSI\(_Symbol, SIGNAL_TF, InpRsiPeriod, PRICE_CLOSE\)", code)
    assert re.search(r"iATR\(_Symbol, SIGNAL_TF, InpAtrPeriod\)", code)
    for h in ("g_hEma", "g_hRsi", "g_hAtr"):
        assert f"IndicatorRelease({h})" in code
        assert f"{h} == INVALID_HANDLE" in code
    # Toda lectura de indicadores y precios parte de la vela 1 (cerrada), nunca de la 0.
    assert re.findall(r"CopyBuffer\(\s*\w+\s*,\s*0\s*,\s*(\d+)", code) == ["1"]
    assert re.findall(r"CopyRates\(\s*_Symbol\s*,\s*SIGNAL_TF\s*,\s*(\d+)", code) == ["1"]


def test_signal_rule_is_exactly_the_specified_one(code):
    body = body_of(code, "SignalType EvaluateSignal(")
    assert "bar.close > bar.ema && bar.rsi > InpRsiBuyLevel" in body
    assert "bar.close < bar.ema && bar.rsi < InpRsiSellLevel" in body
    assert body.count("return") == 3 and "SIGNAL_NONE" in body


def test_one_evaluation_per_new_bar_and_no_retry_loops(code):
    tick = body_of(code, "void OnTick()")
    assert "current == g_lastProcessedBar" in tick and "g_lastProcessedBar = current" in tick
    assert tick.count("SendEntry(") == 1
    for fn in ("bool SendEntry(", "void AlignStopsToFill("):
        b = body_of(code, fn)
        assert "while" not in b and "for(" not in b, f"{fn} no debe tener bucles"
    assert code.count("OrderSend(") == 2  # entrada + recolocación de SL/TP


def test_every_trade_request_carries_the_magic_number(code):
    assert code.count("req.magic") == 2 and code.count("OrderSend(") == 2
    assert "OrderCheck(req, chk)" in code


def test_risk_volume_and_broker_constraints_are_checked(code):
    plan = body_of(code, "bool BuildPlan(")
    for token in ("SYMBOL_VOLUME_MIN", "SYMBOL_VOLUME_MAX", "SYMBOL_VOLUME_STEP", "SYMBOL_TRADE_STOPS_LEVEL",
                  "OrderCalcMargin", "ACCOUNT_MARGIN_FREE", "ACCOUNT_EQUITY", "MathFloor(raw / step",
                  "InpMaxSpreadPoints", "SYMBOL_POINT"):
        assert token in plan, token
    loss = body_of(code, "bool LossPerLot(")
    assert "OrderCalcProfit" in loss and "SYMBOL_TRADE_TICK_VALUE_LOSS" in loss and "SYMBOL_TRADE_TICK_SIZE" in loss
    assert "SYMBOL_FILLING_MODE" in body_of(code, "ENUM_ORDER_TYPE_FILLING ChooseFilling(")


def test_position_isolation_handles_netting_and_hedging(code):
    b = body_of(code, "bool PositionsAllowEntry(")
    assert "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in b and "POSITION_MAGIC" in b and "OrdersTotal()" in b
    # El EA nunca cierra ni modifica posiciones ajenas: no hay ninguna acción de cierre.
    assert "TRADE_ACTION_CLOSE_BY" not in code and "PositionClose" not in code
    align = body_of(code, "void AlignStopsToFill(")
    assert "POSITION_MAGIC) != InpMagicNumber" in align


def test_trading_outside_the_tester_requires_explicit_permission(code):
    b = body_of(code, "bool EnvironmentAllowsTrading(")
    assert "MQL_TESTER" in b and "InpAllowRealTrading" in b and "InpAllowDemoTrading" in b
