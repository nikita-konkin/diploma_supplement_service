import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The same import paths as PYTHONPATH in the Dockerfile, plus this folder for synthetic.py
for path in (ROOT, ROOT / "reports", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("LOG_DIR", tempfile.mkdtemp(prefix="attestation-logs-"))
os.environ.setdefault("ATTESTATION_DATA_DIR", tempfile.mkdtemp(prefix="attestation-data-"))
os.environ.setdefault("MPLBACKEND", "Agg")
