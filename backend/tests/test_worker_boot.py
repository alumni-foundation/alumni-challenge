import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_the_worker_starts_with_every_model_registered() -> None:
    """
    The worker is its own process and loads only what it imports. Handlers read users, so a
    missing model registration shows up as 'mappers failed to initialize' the first time an
    event is handled, long after startup. Boot it in a fresh interpreter and configure the
    mappers, which is exactly what that first event does.
    """
    code = (
        "import app.worker\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
        "print('worker-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=60
    )

    assert result.returncode == 0, result.stderr[-800:]
    assert "worker-ok" in result.stdout
