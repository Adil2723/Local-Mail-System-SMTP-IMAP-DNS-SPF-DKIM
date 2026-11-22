#!/usr/bin/env bash
# CN12 Phase 5 - DKIM signing on Alpha, verification on Beta.
# Run from the existing computer-networks-project folder.
set -Eeuo pipefail
cd "$(dirname "$0")"

say() { printf '\n=== %s ===\n' "$*"; }
need() { [[ -e "$1" ]] || { echo "STOP: missing $1" >&2; exit 1; }; }
need network/compose.yaml
need network/compose.integration.yaml
need network/compose.spf.yaml
need run-cn12.sh
need mail-alpha/Dockerfile
need beta/Dockerfile.spf
need dns/db.lab

prepare() {
  say 'Prepare code (preserves all previous SPF files)'
  mkdir -p mail-alpha/dkim/keys beta/dkim beta/scripts
  touch .gitignore
  grep -qxF '/mail-alpha/dkim/keys/' .gitignore || printf '\n# DKIM private key - NEVER commit\n/mail-alpha/dkim/keys/\n' >> .gitignore
  touch mail-alpha/.dockerignore
  grep -qxF 'dkim/keys/' mail-alpha/.dockerignore || printf 'dkim/keys/\n' >> mail-alpha/.dockerignore
  test -f dns/db.lab.phase5.bak || cp dns/db.lab dns/db.lab.phase5.bak
  test -f run-cn12.sh.phase5.bak || cp run-cn12.sh run-cn12.sh.phase5.bak

  cat > mail-alpha/dkim/opendkim.conf <<'EOF'
Syslog                  yes
SyslogSuccess           yes
Mode                    s
Canonicalization        relaxed/relaxed
Domain                  alpha.lab
Selector                mail
KeyFile                 /etc/opendkim/keys/mail.private
InternalHosts           /etc/opendkim/TrustedHosts
Socket                  inet:8891@127.0.0.1
UserID                  opendkim
UMask                   007
EOF
  cat > mail-alpha/dkim/TrustedHosts <<'EOF'
127.0.0.1
10.10.1.20
EOF
  cat > mail-alpha/dkim/start-alpha-dkim.sh <<'EOF'
#!/bin/sh
set -eu
test -s /etc/opendkim/keys/mail.private || { echo 'STOP: Alpha DKIM key missing'; exit 1; }
opendkim -x /etc/opendkim.conf
exec /usr/local/bin/start-mail-alpha
EOF
  cat > mail-alpha/Dockerfile.dkim <<'EOF'
FROM cn-mail-lab-mail-alpha:local
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends opendkim opendkim-tools \
    && rm -rf /var/lib/apt/lists/*
COPY dkim/opendkim.conf /etc/opendkim.conf
COPY dkim/TrustedHosts /etc/opendkim/TrustedHosts
COPY dkim/start-alpha-dkim.sh /usr/local/bin/start-alpha-dkim
RUN chmod 755 /usr/local/bin/start-alpha-dkim \
    && postconf -e 'smtpd_milters = inet:127.0.0.1:8891' \
    && postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891' \
    && postconf -e 'milter_default_action = tempfail' \
    && postconf -e 'milter_protocol = 6' \
    && postfix check
EOF

  cat > beta/dkim/opendkim.conf <<'EOF'
Syslog                  yes
SyslogSuccess           yes
Mode                    v
AuthservID              mail.beta.lab
Socket                  inet:8891@127.0.0.1
UserID                  opendkim
UMask                   007
EOF
  cat > beta/dkim/start-beta-dkim.sh <<'EOF'
#!/bin/sh
set -eu
opendkim -x /etc/opendkim.conf
exec /usr/local/bin/start-beta-imap.sh
EOF
  cat > beta/Dockerfile.dkim <<'EOF'
FROM cn12-mail-beta-spf:local
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends opendkim opendkim-tools \
    && rm -rf /var/lib/apt/lists/*
COPY dkim/opendkim.conf /etc/opendkim.conf
COPY dkim/start-beta-dkim.sh /usr/local/bin/start-beta-dkim
RUN chmod 755 /usr/local/bin/start-beta-dkim \
    && postconf -e 'smtpd_milters = inet:127.0.0.1:8891' \
    && postconf -e 'non_smtpd_milters = inet:127.0.0.1:8891' \
    && postconf -e 'milter_default_action = tempfail' \
    && postconf -e 'milter_protocol = 6' \
    && postfix check
EOF

  cat > network/compose.dkim.yaml <<'EOF'
services:
  mail-alpha:
    image: cn-mail-lab-mail-alpha-dkim:local
    build:
      context: ../mail-alpha
      dockerfile: Dockerfile.dkim
    command: ["sh", "/usr/local/bin/start-alpha-dkim"]
    volumes:
      - ../mail-alpha/dkim/keys:/etc/opendkim/keys:ro
  mail-beta:
    image: cn12-mail-beta-dkim:local
    build:
      context: ../beta
      dockerfile: Dockerfile.dkim
    command: ["sh", "/usr/local/bin/start-beta-dkim"]
EOF
  cat > beta/scripts/dkim_examine_maildir.py <<'EOF'
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
EOF
  cat > beta/scripts/dkim_export_latest.py <<'EOF'
from pathlib import Path
import sys
base = Path('/home/adil/Maildir')
files = [p for sub in ('new', 'cur') for p in (base / sub).glob('*') if p.is_file()]
if not files:
    raise SystemExit('STOP: Beta Maildir is empty')
latest = max(files, key=lambda f: f.stat().st_mtime)
sys.stdout.buffer.write(latest.read_bytes())
EOF
  cat > beta/scripts/dkim_tamper.py <<'EOF'
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
    if line.lower().startswith(b'authentication-results:'):
        skipping = True
        continue
    if skipping and line.startswith((b' ', b'\t')):
        continue
    skipping = False
    filtered.append(line)
dst.write_bytes(b''.join(filtered) + sep + body)
print('Created:', dst)
EOF
  cat > beta/scripts/dkim_replay_tampered.py <<'EOF'
from pathlib import Path
import smtplib
raw = Path('/tmp/cn12-dkim-tampered.eml').read_bytes()
with smtplib.SMTP('mail.beta.lab', 25, timeout=20) as smtp:
    smtp.ehlo('mail.alpha.lab')
    source_ip = smtp.sock.getsockname()[0]
    print('Direct connection source IP:', source_ip)
    if source_ip != '10.10.1.10':
        raise SystemExit('STOP: source IP is not authorized Alpha MTA; SPF test would interfere')
    smtp.sendmail('zaid@alpha.lab', ['adil@beta.lab'], raw)
print('Modified signed message submitted directly from Alpha IP to Beta')
EOF
  python3 -m py_compile beta/scripts/dkim_*.py
  say 'Files prepared; SPF installation remains unchanged'
  git check-ignore -v mail-alpha/dkim/keys/mail.private || true
}

build() {
  say 'Build new Alpha and Beta OpenDKIM images (inherit existing working images)'
  docker image inspect cn-mail-lab-mail-alpha:local >/dev/null
  docker image inspect cn12-mail-beta-spf:local >/dev/null
  docker build -t cn-mail-lab-mail-alpha-dkim:local -f mail-alpha/Dockerfile.dkim mail-alpha
  docker build -t cn12-mail-beta-dkim:local -f beta/Dockerfile.dkim beta
}

keys() {
  say 'Generate 2048-bit DKIM key locally; never commit the private key'
  mkdir -p mail-alpha/dkim/keys
  docker run --rm --entrypoint sh \
    -v "$PWD/mail-alpha/dkim/keys:/keys" \
    cn-mail-lab-mail-alpha-dkim:local -ec '
      if [ ! -f /keys/mail.private ] && [ ! -f /keys/mail.txt ]; then
        opendkim-genkey -b 2048 -d alpha.lab -s mail -D /keys
      fi
      test -s /keys/mail.private && test -s /keys/mail.txt || { echo "STOP: incomplete key pair"; exit 1; }
      chown opendkim:opendkim /keys/mail.private
      chmod 0600 /keys/mail.private
      chmod 0644 /keys/mail.txt
      echo "Generated/verified DKIM key pair. PRIVATE FILE NOT PRINTED."
    '
  git check-ignore -q mail-alpha/dkim/keys/mail.private || { echo 'STOP: private key not ignored by Git'; exit 1; }
}

dns() {
  say 'Publish DKIM PUBLIC key in DNS and bump SOA serial'
  python3 - <<'PY'
from pathlib import Path
import re
zone_path = Path('dns/db.lab')
key_path = Path('mail-alpha/dkim/keys/mail.txt')
record = key_path.read_text()
if not ('v=DKIM1' in record and 'p=' in record):
    raise SystemExit('STOP: generated public key record incomplete')
record, changed = re.subn(r'(?m)^mail\._domainkey\s+IN\s+TXT', 'mail._domainkey.alpha IN TXT', record, count=1)
if changed != 1:
    raise SystemExit('STOP: unexpected opendkim-genkey DNS record format')
zone = zone_path.read_text()
if re.search(r'(?m)^\s*mail\._domainkey\.alpha\s+IN\s+TXT\b', zone):
    print('DKIM DNS entry already exists. Not changing keys or SOA. Review record if needed.')
else:
    serial = re.search(r'(?m)^(\s*)(\d{10})(\s*(?:;[^\n]*)?)$', zone)
    if not serial:
        raise SystemExit('STOP: DNS zone SOA serial not found')
    old = int(serial.group(2)); new = old + 1
    zone = zone[:serial.start(2)] + str(new) + zone[serial.end(2):]
    zone_path.write_text(zone.rstrip() + '\n\n' + record.strip() + '\n')
    print('SOA serial:', old, '->', new)
    print('Published: mail._domainkey.alpha.lab TXT (public key only)')
PY
  docker run --rm --entrypoint named-checkzone \
    -v "$PWD/dns/db.lab:/tmp/db.lab:ro" \
    cn-mail-lab-dns:local lab /tmp/db.lab
  docker build -t cn-mail-lab-dns:local -f dns/Dockerfile dns
}

activate() {
  say 'Activate DKIM as the LAST Compose override; preserve SPF and volumes'
  python3 - <<'PY'
from pathlib import Path
p = Path('run-cn12.sh')
s = p.read_text()
add = '  -f network/compose.dkim.yaml \\\n'
if 'network/compose.dkim.yaml' not in s:
    anchor = '  -f network/compose.spf.yaml \\\n'
    if anchor not in s:
        raise SystemExit('STOP: expected SPF override line missing in run-cn12.sh')
    s = s.replace(anchor, anchor + add, 1)
    p.write_text(s)
print('DKIM override is last after SPF')
PY
  chmod +x run-cn12.sh
  bash -n run-cn12.sh
  ./run-cn12.sh config --quiet
  ./run-cn12.sh config --format json | python3 -c 'import sys,json; d=json.load(sys.stdin)["services"]; print("Alpha:", d["mail-alpha"]["image"]); print("Beta:", d["mail-beta"]["image"]); assert d["mail-beta"]["image"]=="cn12-mail-beta-dkim:local"'
  docker volume inspect cn12-topology_beta_maildir >/dev/null || { echo 'STOP: Beta mail volume missing'; exit 1; }
  [[ -s beta/dovecot/users ]] || { echo 'STOP: local IMAP credentials missing'; exit 1; }
  ./run-cn12.sh up -d --no-build --force-recreate dns mail-alpha mail-beta
  ./run-cn12.sh ps -a
}

verify() {
  say 'Verify DNS, OpenDKIM and Postfix milters'
  ./run-cn12.sh exec -T client-alpha dig @10.10.0.53 mail._domainkey.alpha.lab TXT +short
  ./run-cn12.sh exec -T mail-alpha postconf -h smtpd_milters
  ./run-cn12.sh exec -T mail-beta postconf -h smtpd_milters
  ./run-cn12.sh exec -T mail-beta postconf -h smtpd_recipient_restrictions
  ./run-cn12.sh exec -T mail-alpha opendkim-testkey -d alpha.lab -s mail -k /etc/opendkim/keys/mail.private -vvv
}

positive() {
  say 'POSITIVE TEST - send signed email from Alpha SMTP to Adil'
  ./run-cn12.sh exec -T client-alpha python3 - adil@beta.lab < smtp_client.py
  sleep 2
  ./run-cn12.sh exec -T mail-beta python3 - < beta/scripts/dkim_examine_maildir.py
  echo 'REQUIRE: newest message has DKIM-Signature and Authentication-Results dkim=pass'
}

negative() {
  say 'NEGATIVE TEST - replay altered signed body directly from authorized Alpha IP'
  ./run-cn12.sh exec -T mail-beta python3 - < beta/scripts/dkim_export_latest.py > /tmp/cn12-dkim-signed.eml
  python3 beta/scripts/dkim_tamper.py /tmp/cn12-dkim-signed.eml /tmp/cn12-dkim-tampered.eml
  ./run-cn12.sh cp /tmp/cn12-dkim-tampered.eml mail-alpha:/tmp/cn12-dkim-tampered.eml
  ./run-cn12.sh exec -T mail-alpha python3 - < beta/scripts/dkim_replay_tampered.py
  sleep 2
  ./run-cn12.sh exec -T mail-beta python3 - < beta/scripts/dkim_examine_maildir.py
  echo 'REQUIRE: new Authentication-Results dkim=fail (or explicit signature failure)'
  echo 'DKIM verification failure normally does NOT imply SMTP rejection.'
}

case "${1:-help}" in
  prepare) prepare;;
  build) build;;
  keys) keys;;
  dns) dns;;
  activate) activate;;
  verify) verify;;
  positive) positive;;
  negative) negative;;
  help|*) cat <<'USAGE'
CN12 Phase 5 DKIM steps, run ONE AT A TIME in this order:
  ./phase5-dkim.sh prepare
  ./phase5-dkim.sh build
  ./phase5-dkim.sh keys
  ./phase5-dkim.sh dns
  ./phase5-dkim.sh activate
  ./phase5-dkim.sh verify
  ./phase5-dkim.sh positive
  ./phase5-dkim.sh negative
Never run 'down -v'. Never commit mail-alpha/dkim/keys/.
USAGE
  ;;
esac
