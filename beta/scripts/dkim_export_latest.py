from pathlib import Path
import sys
base = Path('/home/adil/Maildir')
files = [p for sub in ('new', 'cur') for p in (base / sub).glob('*') if p.is_file()]
if not files:
    raise SystemExit('STOP: Beta Maildir is empty')
latest = max(files, key=lambda f: f.stat().st_mtime)
sys.stdout.buffer.write(latest.read_bytes())
