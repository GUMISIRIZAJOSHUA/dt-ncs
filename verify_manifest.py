import hashlib, sys
from pathlib import Path
root = Path(__file__).parent
bad = 0
for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
    digest, rel = line.split("  ", 1)
    p = root / rel
    ok = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == digest
    if not ok:
        bad += 1
        print("MISMATCH", rel)
print("all files verified" if not bad else f"{bad} problem(s)")
sys.exit(1 if bad else 0)
