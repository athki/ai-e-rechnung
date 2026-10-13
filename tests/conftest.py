"""Tests laufen ohne Config und ohne Gewerbe-Ordner: keine RECHNUNG_*-Variable aus der Umgebung.

Eine Claude-Session im Repo setzt RECHNUNG_GEWERBE (Test-Ordner) und RECHNUNG_GESCHWAERZT; ohne
diese Fixture schlügen beide in die Tests durch.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def ohne_rechnung_env(monkeypatch):
    for name in [n for n in os.environ if n.startswith("RECHNUNG_")]:
        monkeypatch.delenv(name)
