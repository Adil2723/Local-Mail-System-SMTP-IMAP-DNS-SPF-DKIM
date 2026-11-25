#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
branch=$(git branch --show-current)
test -n "$branch"
if ! git diff --cached --quiet; then echo 'STOP: Existing staged changes; review git status first.'; exit 1; fi
if ! git diff --quiet; then echo 'STOP: Existing tracked edits; review git status first.'; exit 1; fi
for file in cn12_demo_gui.py cn12_publish_evidence.sh GUI_README.md; do test -s "$file"; done
python3 - <<'PY'
import csv, hashlib, re, shutil, subprocess, sys
from pathlib import Path
root=Path.cwd(); dest=root/'captures/final-evidence'
tracked=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
unsafe=[n for n in tracked if n and (n in ('beta/dovecot/users','mail-alpha/dovecot/users') or n.startswith(('beta/backups/','mail-alpha/dkim/keys/','.venv/','venv/')) or Path(n).name=='.env' or n.endswith(('.private','.key','.p12','.pfx')))]
if unsafe: raise SystemExit('STOP: sensitive tracked paths: '+', '.join(unsafe))
packages=sorted(p for p in Path.home().glob('CN12_Final_Evidence_Corrected_*') if p.is_dir() and (p/'Evidence_Review_Report.txt').is_file())
if not packages: raise SystemExit('STOP: corrected evidence folder missing from home directory.')
src=packages[-1]
sections=['02_Functional_Tests','03_Wireshark','04_Performance_Experiments','05_Additional_Measurements','06_Statistical_Analysis','07_Network_Architecture','08_Final_Product_Verification','09_Screenshots_Review']
allowed={'.txt','.csv','.json','.py','.sh','.svg','.png','.jpg','.jpeg','.pcapng','.md'}
secret=re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\$[56]\$[^\s]{15,}|\$2[aby]\$\d{2}\$[A-Za-z0-9./]{20,}')
# Avoid copying all raw data, temp captures or backup archives.
if not dest.exists():
    files=[]
    for section in sections:
        folder=src/section
        if not folder.is_dir(): raise SystemExit('Missing section: '+section)
        for f in sorted(folder.rglob('*')):
            if f.is_symlink(): raise SystemExit('Unexpected symbolic link: '+str(f))
            if f.is_file(): files.append(f)
    files.append(src/'Evidence_Review_Report.txt')
    staged=[]
    for f in files:
        if f.suffix.lower() not in allowed: raise SystemExit('Unexpected evidence type: '+f.name)
        if f.stat().st_size>90*1024*1024: raise SystemExit('File exceeds safe Git size: '+f.name)
        rel=f.relative_to(src)
        if f.suffix.lower() in {'.txt','.csv','.json','.py','.sh','.svg','.md'}:
            text=f.read_text(errors='replace')
            if secret.search(text): raise SystemExit('Possible credential material: '+str(rel))
            if f.suffix.lower()=='.txt':
                text='\n'.join('[REDACTED: credential prompt/line]' if re.search(r'password\s*:|password\s+for|passphrase\s*:|personal access token\s*:', line,re.I) else line for line in text.splitlines())+'\n'
            staged.append((rel,text.encode()))
        else: staged.append((rel,f.read_bytes()))
    dest.mkdir(parents=True)
    for rel,data in staged:
        f=dest/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
else:
    print('Existing final-evidence folder found; preserving it and auditing its contents.')
files=[p for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='Evidence_Inventory.csv']
rows=[]; traces=set(); shots=set()
for f in files:
    rel=f.relative_to(dest)
    if f.is_symlink() or f.suffix.lower() not in allowed or f.stat().st_size>90*1024*1024: raise SystemExit('STOP: review '+str(rel))
    if f.suffix.lower() in {'.txt','.csv','.json','.py','.sh','.svg','.md'} and secret.search(f.read_text(errors='replace')): raise SystemExit('STOP: possible credential material in '+str(rel))
    if f.suffix.lower()=='.pcapng':
        result=subprocess.run(['tshark','-r',str(f),'-Y','(tcp.dstport == 143 && (tcp contains " LOGIN " || tcp contains " AUTHENTICATE ")) || (tcp.dstport == 25 && (tcp contains "AUTH PLAIN" || tcp contains "AUTH LOGIN"))','-T','fields','-e','frame.number'],capture_output=True,text=True)
        if result.returncode or result.stdout.strip(): raise SystemExit('STOP: possible authentication traffic or unreadable capture: '+str(rel))
        m=re.match(r'Capture-(\d{2})',f.name)
        if m:traces.add(int(m.group(1)))
    if f.suffix.lower() in {'.png','.jpg','.jpeg'} and rel.parts[0]=='09_Screenshots_Review':
        m=re.match(r'Capture-(\d{2})',f.name)
        if m:shots.add(int(m.group(1)))
    rows.append({'file':str(rel),'size_bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
assert traces==set(range(1,11)), 'Missing planned packet traces'
assert shots==set(range(1,11)), 'Missing named screenshots'
with (dest/'Evidence_Inventory.csv').open('w',newline='') as file:
    w=csv.DictWriter(file,fieldnames=['file','size_bytes','sha256']);w.writeheader();w.writerows(rows)
print(f'Prepared {len(rows)} evidence files, {len(traces)} trace scenarios and {len(shots)} screenshot scenarios.')
print('Preliminary scan completed; manually inspect images, logs and packet contents for secrets.')
PY
printf '\nReview captures/final-evidence before sharing, especially IMAP evidence.\n'
xdg-open "$PWD/captures/final-evidence" >/dev/null 2>&1 &
read -r -p 'Type YES after reviewing privacy and approving the GitHub upload: ' approval </dev/tty
if [[ "$approval" != YES ]]; then echo 'Cancelled; no Git commit or push performed.'; exit 1; fi
git add -- cn12_demo_gui.py cn12_publish_evidence.sh GUI_README.md
git add -f -- captures/final-evidence/
git diff --cached --stat
if ! git diff --cached --quiet; then git commit -m 'Add CN12 desktop mail demo and verified experimental evidence'; fi
git push origin "$branch"
local_commit=$(git rev-parse HEAD)
remote_commit=$(git ls-remote --exit-code origin "refs/heads/$branch" | awk '{print $1}')
test "$local_commit" = "$remote_commit"
printf '\nPASS: Local and remote commits match: %s\n' "$local_commit"
printf 'Tracked evidence files: '; git ls-files captures/final-evidence/ | wc -l
git status --short
echo 'FINAL GITHUB PUSH: PASSED'
