"""Language preference for the friendly Windows entry points."""

import os
from pathlib import Path


def get_language():
    value = os.environ.get("PAPERFLOW_LANGUAGE", "").strip().lower()
    if value not in {"zh", "en"}:
        try:
            value = (Path(__file__).resolve().parents[2] / ".paperflow-language").read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            value = "zh"
    return "en" if value == "en" else "zh"


def t(chinese, english):
    return english if get_language() == "en" else chinese
