import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def make_df(closes, volume=1000.0):
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        },
        index=idx,
    )


@pytest.fixture
def root():
    return ROOT
