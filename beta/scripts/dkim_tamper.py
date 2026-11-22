from pathlib import Path
import sys
if len(sys.argv) != 3:
    raise SystemExit('Usage: dkim_tamper.py signed.eml tampered.eml')
src, dst = map(Path, sys.argv[1:])
raw = src.read_bytes()
sep = b'\r\n\r\n' if b'\r\n\r\n' in raw else b'\n\n'
if sep not in raw:
    raise SystemExit('STOP: missing header/body separator')
header, body = raw.split(sep, 1)
if b'dkim-signature:' not in header.lower():
    raise SystemExit('STOP: no original DKIM-Signature; first prove positive test')
needle = b'Hello from the Python SMTP client.'
if needle not in body:
    raise SystemExit('STOP: expected original message body not found')
body = body.replace(needle, b'Hello from a deliberately modified DKIM test.', 1)
# Remove previous verifier results, but preserve all DKIM-signed message headers.
filtered, skipping = [], False
for line in header.splitlines(keepends=True):
    if line.lower().startswith((b'authentication-results:', b'delivered-to:', b'x-original-to:', b'return-path:', b'received:')):
        skipping = True
        continue
    if skipping and line.startswith((b' ', b'\t')):
        continue
    skipping = False
    filtered.append(line)
dst.write_bytes(b''.join(filtered) + sep + body)
print('Created:', dst)
