from pathlib import Path
from email.parser import BytesParser
from email import policy

base = Path('/home/adil/Maildir')
files = [p for sub in ('new', 'cur') for p in (base / sub).glob('*') if p.is_file()]
if not files:
    raise SystemExit('STOP: Beta Maildir is empty')
p = max(files, key=lambda f: f.stat().st_mtime)
message = BytesParser(policy=policy.default).parsebytes(p.read_bytes())
print('Latest message:', p.name)
for name in ('From', 'To', 'Subject'):
    print(name + ':', message.get(name, '(missing)'))
print('DKIM-Signature present:', 'DKIM-Signature' in message)
values = message.get_all('Authentication-Results', [])
for value in values:
    print('Authentication-Results:', str(value).replace('\n', ' '))
if not values:
    print('WARNING: no Authentication-Results header (check verifier and logs)')
