import smtplib
import sys

with smtplib.SMTP('mail.beta.lab', 25, timeout=20) as smtp:
    code, reply = smtp.ehlo('client-alpha.alpha.lab')

    if code != 250:
        raise SystemExit(f'EHLO error: {code} {reply!r}')

    actual_ip = smtp.sock.getsockname()[0]
    print('Direct SMTP connection source IP:', actual_ip)

    if actual_ip != '10.10.1.20':
        raise SystemExit('STOP: source IP differs; SPF test is invalid')

    code, reply = smtp.mail('zaid@alpha.lab')
    print('MAIL FROM:', code, reply.decode(errors='replace'))

    if code != 250:
        raise SystemExit('MAIL FROM was not accepted; inspect logs')

    code, reply = smtp.rcpt('adil@beta.lab')
    print('RCPT TO:', code, reply.decode(errors='replace'))

    if not 500 <= code < 600:
        raise SystemExit('FAIL: spoofed client was not rejected')

    print('PASS: SPF rejected unauthorized source at RCPT')
