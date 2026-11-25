# CN Mail — Purple desktop GUI

A simple desktop interface for the existing CN12 Docker mail lab. Two independent windows use the same original raw SMTP helpers and Dovecot IMAP backend as the original demo.

## Run

```bash
cd ~/computer-networks-project
sudo systemctl start docker
./run-cn12.sh up -d --no-build
python3 cn12_demo_gui.py sender --theme light
```

In a second terminal:

```bash
cd ~/computer-networks-project
python3 cn12_demo_gui.py receiver --theme dark
```

The theme button switches between light and dark without restarting. Default theme is light.

Sender: enter a subject and body, then Send. The STARTTLS toggle is enabled by default; certificate verification is enabled. Protocol details shows the most recent successful SMTP transcript. Sent this session is an in-memory list of accepted submissions, not a server-side Sent folder. Receiver: enter the existing Adil mailbox password, Refresh, and open a message. Search filters the latest 30 fetched messages. Details shows the actual authentication headers. Mailbox access is read-only and password input is masked. Credentials are passed to the Docker worker on stdin, not stored. IMAP is plaintext inside the isolated lab.

No Docker networking, port mappings, existing tests, keys or mailboxes are modified. Only Alpha-to-Beta GUI sending is implemented. No attachment, delete, draft, spam folder, external recipient or account management features are added.

## Replace and restore

Close previous GUI windows before installation. Run `bash install_gui.sh` from the extracted bundle. The installer backs up the old GUI and GUI README to a printed `~/CN12_GUI_Backup_*` folder. To restore, copy those files back into the original project. The existing `cn12_publish_evidence.sh` is not overwritten. Review the new GUI and testing evidence for sensitive data before pushing to GitHub.

## Verification

Python syntax and both theme layouts were checked locally, including mocked receiver data. The real SMTP/IMAP integration requires a live test in your Ubuntu VM.
