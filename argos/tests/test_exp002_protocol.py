"""Pre-registro de EXP-002: el protocolo queda bloqueado por su huella y cualquier alteración se detecta.

Ningún test de este fichero lee datos de mercado ni ejecuta la estrategia.
"""

import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from argos.data.calendar_us import sessions
from argos.experiments.protocol import ProtocolChangedError, check_preregistered, load_protocol
from argos.experiments.registry import ExperimentRegistry
from argos.experiments.runner import UnsupportedExperimentError, run_experiment

ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = ROOT / "protocols"
EXP002_SHA = "bd9f206d6df94ccb103873e9f63daceca2c76ded8f42b4a0c8e978bce7759d11"
EXP001_SHA = "7f553e110fff59245a96504bdd0107b179550164eaf3800cbe8664f34cc98cce"


@pytest.fixture
def pdir(tmp_path):
    d = tmp_path / "protocols"
    d.mkdir()
    for name in ("EXP-001.json", "EXP-002.json", "LOCKS.json"):
        shutil.copy(PROTOCOLS / name, d / name)
    return d


def test_lock_matches_committed_bytes():
    locks = json.loads((PROTOCOLS / "LOCKS.json").read_text(encoding="utf-8"))
    actual = hashlib.sha256((PROTOCOLS / "EXP-002.json").read_bytes()).hexdigest()
    assert locks["EXP-002"] == {"sha256": EXP002_SHA, "preregistration_commit": "e2451bb"}
    assert actual == EXP002_SHA
    _, sha, _ = load_protocol("EXP-002")
    check_preregistered("EXP-002", sha)  # no lanza


def test_exp001_lock_untouched():
    locks = json.loads((PROTOCOLS / "LOCKS.json").read_text(encoding="utf-8"))
    assert locks["EXP-001"] == {"sha256": EXP001_SHA, "preregistration_commit": "6b230de"}
    assert hashlib.sha256((PROTOCOLS / "EXP-001.json").read_bytes()).hexdigest() == EXP001_SHA
    assert set(locks) == {"_nota", "EXP-001", "EXP-002"}


def test_locked_protocol_is_exact_copy_of_approved_draft():
    assert (PROTOCOLS / "EXP-002.json").read_bytes() == (ROOT / "docs" / "borradores" / "EXP-002.json").read_bytes()


@pytest.mark.parametrize("mutate", [
    lambda b: b.replace(b'"lookback_months": 12', b'"lookback_months": 10'),
    lambda b: b.replace(b'0,75', b'0,80', 1),
    lambda b: b + b" ",
    lambda b: b[:-1],
])
def test_any_alteration_is_detected(pdir, mutate):
    p = pdir / "EXP-002.json"
    altered = mutate(p.read_bytes())
    assert altered != p.read_bytes()
    p.write_bytes(altered)
    _, sha, _ = load_protocol("EXP-002", pdir)
    with pytest.raises(ProtocolChangedError, match="no coincide con el pre-registrado"):
        check_preregistered("EXP-002", sha, pdir)


def test_crlf_is_detected_and_explained(pdir):
    p = pdir / "EXP-002.json"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    _, sha, _ = load_protocol("EXP-002", pdir)
    with pytest.raises(ProtocolChangedError, match="SALTOS DE LÍNEA") as exc:
        check_preregistered("EXP-002", sha, pdir)
    assert "EXP-002.json" in str(exc.value)


def test_git_keeps_exp002_byte_exact():
    out = subprocess.run(["git", "check-attr", "text", "protocols/EXP-002.json"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout
    assert "text: unset" in out, out
    assert b"\r\n" not in (PROTOCOLS / "EXP-002.json").read_bytes()


def test_exp001_runner_refuses_exp002_without_touching_data(tmp_path):
    reg = ExperimentRegistry(tmp_path / "registry.jsonl")
    with pytest.raises(UnsupportedExperimentError, match="propio ejecutor"):
        run_experiment("EXP-002", data_dir=tmp_path / "no-existe", registry=reg)
    assert reg.list() == []
    assert not (tmp_path / "registry.jsonl").exists()


def test_protocol_content_as_approved():
    p, _, _ = load_protocol("EXP-002")
    raw = json.loads((PROTOCOLS / "EXP-002.json").read_text(encoding="utf-8"))
    assert [a.ticker for a in p.assets] == ["SPY", "VEU", "AGG", "BIL"]
    ev = next(x for x in p.periods if x.name == "evaluacion")
    assert (ev.start, ev.end) == (date(2015, 1, 1), date(2025, 12, 31))
    assert raw["costs"]["currency"] == "USD" and raw["costs"]["initial_capital"] == 100
    assert raw["costs"]["commission_min_per_order"] == 1.0
    assert "NO representa una inversión de 100 EUR" in raw["costs"]["currency_note"]
    assert "NO verificada en el libro" in raw["strategy"]["source_status"]["regla_principal_y_fuente"]
    assert "regla_S1_y_fuente" in raw["strategy"]["source_status"]
    assert [v["id"] for v in raw["sensitivity"]["variants"]] == [f"S{i}" for i in range(1, 9)]
    assert "EXPLORATORIO" in p.success_criteria["C1_threshold_status"]
    assert "FECHAS DE DECISIÓN" in p.success_criteria["decisions_vs_trades"]
    assert p.reserved_holdout["start"] == "2026-10-01"


def test_132_decision_dates_in_evaluation_period():
    """Son fechas de decisión (último día hábil NYSE de cada mes), no operaciones."""
    s = sessions(date(2014, 11, 1), date(2026, 1, 31))
    month_end = {}
    for d in s:
        month_end[(d.year, d.month)] = d
    decisions = sorted(d for d in month_end.values() if date(2014, 12, 1) <= d <= date(2025, 11, 30))
    nxt = {d: s[i + 1] for i, d in enumerate(s[:-1])}
    assert len(decisions) == 132
    assert (decisions[0], decisions[-1]) == (date(2014, 12, 31), date(2025, 11, 28))
    assert (nxt[decisions[0]], nxt[decisions[-1]]) == (date(2015, 1, 2), date(2025, 12, 1))
    assert nxt[month_end[(2025, 12)]] > date(2025, 12, 31)  # la decisión de diciembre de 2025 no se ejecuta
