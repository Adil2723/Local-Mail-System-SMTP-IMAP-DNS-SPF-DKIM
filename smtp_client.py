import argparse
import re
import socket
import ssl
from contextlib import ExitStack
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid
from time import perf_counter

HOST = "mail.alpha.lab"
PORT = 25
SENDER = "alice@alpha.lab"
CA_FILE = "/run/lab-certs/alpha.crt"


def expect_reply(reader, *expected_codes):
    while True:
        line = reader.readline()
        if not line:
            raise ConnectionError("The SMTP server closed the connection.")

        reply = line.decode("ascii", errors="replace").rstrip("\r\n")
        print(f"S: {reply}")

        if len(line) < 5 or not line[:3].isdigit():
            raise RuntimeError(f"Invalid SMTP reply: {reply}")

        if line[3:4] != b"-":
            code = int(line[:3])
            if code not in expected_codes:
                raise RuntimeError(f"Expected {expected_codes}, got {reply}")
            return


def send_command(connection, reader, command, *expected_codes):
    print(f"C: {command}")
    connection.sendall((command + "\r\n").encode("ascii"))
    expect_reply(reader, *expected_codes)


def main():
    parser = argparse.ArgumentParser(description="Send a test email in the mail lab.")
    parser.add_argument("recipient", choices=("alice@alpha.lab", "bob@beta.lab"))
    parser.add_argument("--starttls", action="store_true")
    args = parser.parse_args()
    recipient = args.recipient

    message = EmailMessage(policy=SMTP)
    message["From"] = SENDER
    message["To"] = recipient
    message["Subject"] = "Python SMTP test"
    message["Date"] = formatdate()
    message["Message-ID"] = make_msgid(domain="alpha.lab")
    message.set_content("Hello from the Python SMTP client.")

    data = re.sub(rb"(?m)^\.", b"..", message.as_bytes())
    if not data.endswith(b"\r\n"):
        data += b"\r\n"

    with ExitStack() as resources:
        connection = resources.enter_context(
            socket.create_connection((HOST, PORT), timeout=10)
        )
        reader = resources.enter_context(connection.makefile("rb"))

        expect_reply(reader, 220)
        send_command(connection, reader, "EHLO client-alpha.alpha.lab", 250)

        if args.starttls:
            tls_context = ssl.create_default_context(cafile=CA_FILE)
            started = perf_counter()
            send_command(connection, reader, "STARTTLS", 220)
            reader.close()

            connection = resources.enter_context(
                tls_context.wrap_socket(connection, server_hostname=HOST)
            )
            reader = resources.enter_context(connection.makefile("rb"))
            elapsed_ms = (perf_counter() - started) * 1000
            print(f"TLS: {connection.version()} established in {elapsed_ms:.2f} ms")

            send_command(connection, reader, "EHLO client-alpha.alpha.lab", 250)

        send_command(connection, reader, f"MAIL FROM:<{SENDER}>", 250)
        send_command(connection, reader, f"RCPT TO:<{recipient}>", 250, 251)
        send_command(connection, reader, "DATA", 354)

        print("C: [message data]")
        connection.sendall(data + b".\r\n")
        expect_reply(reader, 250)
        send_command(connection, reader, "QUIT", 221)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"SMTP failed: {error}")
