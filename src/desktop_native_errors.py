"""Classify native FM27 host startup failures without mislabeling them as parser rejects."""
import json
from pathlib import Path


class NativeActivationTimeout(ValueError):
    """The native host never reached its activated state; tactic parsing did not run."""


def activation_pending(returncode, log_path):
    if returncode != 82:
        return False
    try:
        events = [json.loads(line) for line in Path(log_path).read_text(encoding="utf8").splitlines()]
    except (OSError, UnicodeError, ValueError):
        return False
    return any(row.get("event") == "activation_still_pending" for row in events)
