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
