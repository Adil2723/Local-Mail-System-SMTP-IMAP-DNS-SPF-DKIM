import imaplib
import getpass
from email import message_from_bytes

password = getpass.getpass(
    "Enter lab IMAP password for adil@beta.lab: "
)

with imaplib.IMAP4("10.10.2.10", 143, timeout=15) as client:
    client.login("adil@beta.lab", password)
    print("IMAP login successful!")

    status, count = client.select("INBOX", readonly=True)
    print("INBOX:", count[0].decode(), "messages")

    status, data = client.search(None, "ALL")
    ids = data[0].split()

    if ids:
        status, fetched = client.fetch(ids[-1], "(RFC822)")

        raw = next(
            item[1] for item in fetched
            if isinstance(item, tuple)
        )

        msg = message_from_bytes(raw)

        print("From:", msg.get("From"))
        print("To:", msg.get("To"))
        print("Subject:", msg.get("Subject"))
        print("Message-ID:", msg.get("Message-ID"))

    else:
        print("No emails found.")
