"""Prepare dashboard inputs once per Streamlit server process."""
from pathlib import Path
from threading import Lock

from src.analytics import ROOT
from src.generate import generate
from src.workforce import SCENARIOS, build_workforce

_lock = Lock()


def dashboard_inputs_ready(root: Path) -> bool:
    required = [
        root / "data/serviceops.db",
        root / "reports/dispatch_diagnostics.csv",
    ]
    for scenario in SCENARIOS:
        for table in ("bookings", "shifts"):
            required.append(root / f"reports/scenarios/{scenario}_{table}.csv")
    return all(path.is_file() for path in required)


def dashboard_root() -> Path:
    """Reuse the local build or build only the data required by the dashboard."""
    with _lock:
        if not dashboard_inputs_ready(ROOT):
            (ROOT / "data").mkdir(exist_ok=True)
            (ROOT / "reports").mkdir(exist_ok=True)
            if not (ROOT / "data/serviceops.db").is_file():
                generate()
            build_workforce()
        return ROOT
