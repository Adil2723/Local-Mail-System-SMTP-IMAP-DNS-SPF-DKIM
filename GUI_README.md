# CN Mail — Purple desktop GUI (SMTP progress edition)

A GUI-only update for the existing CN12 Docker mail system. The original SMTP client, Postfix, Dovecot, DNS, SPF/DKIM, router configuration, test scripts and captured evidence remain unchanged.

## Install / replace

Close both existing GUI windows. Extract `CN12_Purple_GUI.zip` to a temporary folder and run `bash install_gui.sh` from it. The installer validates Python syntax and backs up `cn12_demo_gui.py` and `GUI_README.md` outside the repository before replacing only those two files. Existing `cn12_publish_evidence.sh` is preserved. Requires Python 3 and Tkinter (`sudo apt install python3-tk`).

## Start and launch

On the already-configured Ubuntu VM:

```bash
cd ~/computer-networks-project
sudo systemctl start docker
./run-cn12.sh up -d --no-build
python3 cn12_demo_gui.py sender
```

Second terminal:

```bash
cd ~/computer-networks-project
python3 cn12_demo_gui.py receiver
```

Both modes support light/dark switching. Optional `--theme dark` starts in dark mode.

## Demo

1. In Sender (Zaid), enter a subject and plain-text body; leave STARTTLS enabled or uncheck it for plaintext lab SMTP.
2. Click Send Message. The popup streams actual reply and elapsed-time events from the existing raw SMTP helper functions: greeting, EHLO, STARTTLS and post-TLS EHLO (if enabled), MAIL FROM, RCPT TO, DATA, final message acceptance and QUIT. Progress is the number of successful stages, not estimated transfer bytes. Successful SMTP acceptance means queued, not guaranteed final delivery. If acceptance is uncertain, inspect the inbox before retrying.
3. In Receiver (Adil), enter the existing IMAP password and refresh. Open a message to view the actual body and SPF/DKIM result headers. Details shows the original header values. Passwords are not stored and are passed to the worker on stdin. IMAP remains plaintext inside the isolated laboratory.

Inbox search filters the latest 30 fetched messages; sent history is session-only. Only Alpha-to-Beta GUI sending is supported. Unsupported navigation is visibly disabled; N/A means Not available in that window. No attachments, spam/trash/drafts, account management or new protocols are implemented. No synthetic authentication passes, fixed timing values or simulated delivery statuses are used in the installed GUI.

## GitHub update

```bash
git add -- cn12_demo_gui.py GUI_README.md
git commit --only -m "Refine purple GUI and add live SMTP transaction progress" -- cn12_demo_gui.py GUI_README.md
git push origin main
```

Review changes first. Do not stage the external GUI backup or any private credentials.

## Validation

The GUI and embedded worker syntax were checked. Both windows, theme switching, and progress rendering were exercised in a local virtual display. The SMTP worker was tested with the recovered original SMTP client helpers against a local test server for plaintext, certificate-validated STARTTLS and RCPT rejection. This does not replace live integration testing in your Ubuntu VM; no Docker mail server was available in this environment. The Tkinter layout approximates the approved mockup without extra packages.
