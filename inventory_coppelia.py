import re
import time
from pathlib import Path

root = Path.cwd()
skip = {"site-packages", ".venv", "venv", "__pycache__", ".git", "node_modules"}
pat = re.compile(r"coppelia|hrc|scene|handoff|hand_off|network|emulat|completed|fullshift|full_shift|latency|ack", re.I)
rows = [
    p for p in root.rglob("*")
    if p.is_file()
    and p.suffix.lower() in {".py", ".ttt", ".json", ".yaml", ".yml", ".csv"}
    and not any(part in skip for part in p.parts)
    and pat.search(p.name)
]

for p in sorted(rows):
    st = p.stat()
    print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}  {st.st_size:>9}  {p.relative_to(root)}")

print("\n--- definitions and key calls ---")
key = re.compile(r"^\s*(def |class )|RemoteAPIClient|setStepping|step\(|timeout|perf_counter|ack", re.I)
for p in sorted(rows):
    if p.suffix == ".py":
        print(f"\n## {p.relative_to(root)}")
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            if key.search(line):
                print(f"{i:>5}: {line.strip()[:110]}")