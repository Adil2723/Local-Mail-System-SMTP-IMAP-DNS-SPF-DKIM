import sys
import csv
import time
import smtplib
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid

condition = sys.argv[1]
run = int(sys.argv[2])

writer = csv.writer(sys.stdout)

writer.writerow([
    "condition",
    "run",
    "transaction",
    "command",
    "response_code",
    "rtt_ms"
])

for transaction in range(1, 11):

    smtp = smtplib.SMTP(
        timeout=30,
        local_hostname="mail.alpha.lab"
    )

    def timed(command, expected, action):

        start = time.perf_counter_ns()

        code, response = action()

        elapsed = (time.perf_counter_ns() - start) / 1e6

        writer.writerow([
            condition,
            run,
            transaction,
            command,
            code,
            round(elapsed, 6)
        ])

        sys.stdout.flush()

        if code != expected:
            raise RuntimeError(
                f"{command}: unexpected response {code} {response!r}"
            )

    try:

        code, response = smtp.connect("10.10.2.10", 25)

        assert code == 220, response

        timed("EHLO", 250, lambda: smtp.ehlo())

        timed(
            "MAIL FROM",
            250,
            lambda: smtp.mail("zaid@alpha.lab")
        )

        timed(
            "RCPT TO",
            250,
            lambda: smtp.rcpt("adil@beta.lab")
        )

        timed(
            "DATA",
            354,
            lambda: smtp.docmd("DATA")
        )

        message = EmailMessage(policy=SMTP)

        message["From"] = "zaid@alpha.lab"
        message["To"] = "adil@beta.lab"

        message["Subject"] = (
            f"CN12-RTT-PROBE-{condition}-{run}-{transaction}"
        )

        message["Date"] = formatdate(localtime=True)

        message["Message-ID"] = make_msgid(domain="alpha.lab")

        message.set_content("X" * 1024)

        payload = message.as_bytes(policy=SMTP)

        if not payload.endswith(b"\r\n"):
            payload += b"\r\n"

        def submit_message():
            smtp.send(payload + b".\r\n")
            return smtp.getreply()

        timed("MESSAGE_ACCEPTANCE", 250, submit_message)

        timed("QUIT", 221, lambda: smtp.quit())

    finally:
        smtp.close()

print(
    f"PASS: {condition} Run {run}: 10 SMTP transactions",
    file=sys.stderr
)
