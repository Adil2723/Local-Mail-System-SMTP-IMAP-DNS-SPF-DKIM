import sys
import ssl
import csv
import time
import smtplib
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid

host = "mail.alpha.lab"

context = ssl.create_default_context(
    cafile="/run/lab-certs/alpha.crt"
)

writer = csv.writer(sys.stdout)

writer.writerow([
    "run",
    "transaction",
    "mode",
    "connect_ms",
    "initial_ehlo_ms",
    "tls_negotiation_ms",
    "post_tls_ehlo_ms",
    "message_submission_ms",
    "total_transaction_ms",
    "tls_version",
    "tls_cipher",
    "message_id"
])

def timed(action):

    start = time.perf_counter_ns()

    result = action()

    elapsed = (time.perf_counter_ns() - start) / 1e6

    return result, elapsed

def execute(run, transaction, mode):

    msg = EmailMessage(policy=SMTP)

    msg["From"] = "zaid@alpha.lab"
    msg["To"] = "zaid@alpha.lab"

    msg["Subject"] = (
        f"CN12 STARTTLS Benchmark {run}-{transaction}"
    )

    msg["Date"] = formatdate(localtime=True)

    msg["Message-ID"] = make_msgid(domain="alpha.lab")

    msg.set_content("X" * 1024)

    payload = msg.as_bytes(policy=SMTP)

    tls_ms = 0.0
    second_ehlo_ms = 0.0
    version = ""
    cipher = ""

    total_start = time.perf_counter_ns()

    smtp = None

    try:

        smtp, connect_ms = timed(
            lambda: smtplib.SMTP(
                host, 25, timeout=30
            )
        )

        assert smtp.sock.getpeername()[0] == "10.10.1.10"

        result, ehlo_ms = timed(smtp.ehlo)

        assert result[0] == 250

        if mode == "STARTTLS":

            assert smtp.has_extn("starttls")

            result, tls_ms = timed(
                lambda: smtp.starttls(context=context)
            )

            assert result[0] == 220

            version = smtp.sock.version()
            cipher = smtp.sock.cipher()[0]

            assert version in ("TLSv1.2", "TLSv1.3")

            result, second_ehlo_ms = timed(smtp.ehlo)

            assert result[0] == 250

        result, submission_ms = timed(
            lambda: smtp.sendmail(
                "zaid@alpha.lab",
                ["zaid@alpha.lab"],
                payload
            )
        )

        assert not result, "Recipient refused"

        code, _ = smtp.quit()

        assert code == 221

        total_ms = (
            time.perf_counter_ns() - total_start
        ) / 1e6

        writer.writerow([
            run,
            transaction,
            mode,
            round(connect_ms, 6),
            round(ehlo_ms, 6),
            round(tls_ms, 6),
            round(second_ehlo_ms, 6),
            round(submission_ms, 6),
            round(total_ms, 6),
            version,
            cipher,
            str(msg["Message-ID"])
        ])

        sys.stdout.flush()

    finally:

        if smtp is not None:
            smtp.close()

for run in range(1, 4):

    for transaction in range(1, 11):

        modes = (
            ("Plaintext", "STARTTLS")
            if (run + transaction) % 2 == 0
            else ("STARTTLS", "Plaintext")
        )

        for mode in modes:

            execute(run, transaction, mode)

    print(
        f"PASS: Run {run}/3 completed - 20 transactions",
        file=sys.stderr,
        flush=True
    )

print(
    "PASS: All 60 SMTP transactions completed",
    file=sys.stderr
)
