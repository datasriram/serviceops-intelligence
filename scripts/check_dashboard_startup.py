"""Exercise the Streamlit entry point from a checkout without generated data."""
import json
from pathlib import Path
import subprocess
import sys

from streamlit.testing.v1 import AppTest


def main():
    root = Path(__file__).resolve().parents[1]
    database = root / "data/serviceops.db"
    if database.exists():
        raise RuntimeError("Run the startup check in a fresh checkout.")

    app = AppTest.from_file(str(root / "dashboard/app.py"), default_timeout=480)
    app.run()
    assert not app.exception and not app.error
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Requested"] == "60,000"
    assert metrics["Completed"] == "52,198"

    stamp = database.stat().st_mtime_ns
    app.run()
    assert not app.exception and database.stat().st_mtime_ns == stamp

    code = "import json; from src.analytics import load_data, kpis; print(json.dumps(kpis(load_data()[0])))"
    actual = json.loads(subprocess.check_output([sys.executable, "-c", code], cwd=root))
    expected = json.loads((root / "reports/kpis.json").read_text())["kpis"]
    for name, value in expected.items():
        assert abs(actual[name] - value) < 1e-6, name


if __name__ == "__main__":
    main()
