# CN12 - Local Mail System

Computer Networks Project

## Project Overview

A Docker-based local email communication system implementing
SMTP, IMAP, DNS MX records, SPF, DKIM and STARTTLS.

The system provides communication between two isolated
email domains through Linux routers and multiple subnets.

## Network Architecture

- Alpha LAN: 10.10.1.0/24
- Core network: 10.10.0.0/24
- Beta LAN: 10.10.2.0/24
- Router 1: 10.10.1.254 and 10.10.0.11
- Router 2: 10.10.2.254 and 10.10.0.12
- DNS server: 10.10.0.53
- Client Alpha: 10.10.1.20
- Mail Alpha: 10.10.1.10
- Client Beta: 10.10.2.20
- Mail Beta: 10.10.2.10

## Technologies

- Ubuntu Linux
- Docker and Docker Compose
- Python
- Postfix
- Dovecot
- BIND DNS
- OpenDKIM
- SPF policy service
- STARTTLS
- Wireshark and TShark
- Linux traffic control: netem and TBF

## Requirements

- Ubuntu Linux
- Docker Engine
- Docker Compose plugin
- Python 3
- Required local Docker images
- Locally provisioned IMAP credentials
- DKIM signing key and corresponding DNS public key
- TLS certificate and matching private key

Private credentials and signing keys must not be
committed to the public repository.

## Startup Instructions

Clone the repository:

```bash
git clone https://github.com/Adil2723/Local-Mail-System-SMTP-IMAP-DNS-SPF-DKIM.git
cd Local-Mail-System-SMTP-IMAP-DNS-SPF-DKIM
```

On the configured project environment, start Docker
and launch all services:

```bash
sudo systemctl start docker
./run-cn12.sh up -d --no-build
./run-cn12.sh ps
```

The launcher combines the project Compose configurations.

A fresh installation requires building the project images
and provisioning the local private credentials and keys
before running the startup command.

## SMTP Communication

Send an email from Alpha to Beta using the custom
Python SMTP client:

```bash
./run-cn12.sh exec -T client-alpha python3 - adil@beta.lab < smtp_client.py
```

Send using STARTTLS:

```bash
./run-cn12.sh exec -T client-alpha python3 - adil@beta.lab --starttls < smtp_client.py
```

## IMAP Mailbox Retrieval

Dovecot provides IMAP access on TCP port 143.

Mailboxes:

- zaid@alpha.lab
- adil@beta.lab

Python IMAP testing scripts are available in:

- mail-alpha/scripts/imap_test.py
- beta/scripts/imap_test.py

Use the locally configured mailbox credentials.

Plaintext IMAP is restricted to the isolated laboratory
environment and is not suitable for public deployment.

## DNS Verification

```bash
./run-cn12.sh exec -T client-alpha dig @10.10.0.53 beta.lab MX
./run-cn12.sh exec -T client-alpha dig @10.10.0.53 mail.beta.lab A
```

## SPF Verification

```bash
./run-cn12.sh exec -T client-beta dig @10.10.0.53 alpha.lab TXT
```

Unauthorized sender rejection test:

```bash
./run-cn12.sh exec -T client-alpha python3 - < beta/scripts/spf_fail_probe.py
```

## DKIM Verification

```bash
./phase5-dkim.sh verify
```

Positive and negative signature tests:

```bash
./phase5-dkim.sh positive
./phase5-dkim.sh negative
```

The negative test demonstrates detection of a modified
message signature, not necessarily message rejection.

## Routing Verification

```bash
./run-cn12.sh exec -T r1 ip route
./run-cn12.sh exec -T r2 ip route
./run-cn12.sh exec -T client-alpha traceroute -n -I 10.10.2.10
```

## Functional and Performance Testing

The project evaluation includes:

- 20 functional tests
- 10 Wireshark capture scenarios
- 15 workload experiments
- 1,000 emails per workload experiment
- 15,000 verified workload email deliveries
- 360 SMTP command response-time measurements
- 60 plaintext and STARTTLS comparison transactions

Network conditions:

| Condition | Runs | Emails per run |
|---|---:|---:|
| Baseline | 3 | 1000 |
| 100 ms added RTT | 3 | 1000 |
| 200 ms added RTT | 3 | 1000 |
| 2% forward-path packet loss | 3 | 1000 |
| 1 Mbps bandwidth restriction | 3 | 1000 |

Performance metrics include delivery latency estimates,
throughput, network RTT, authentication success,
SMTP command RTT and STARTTLS overhead.

Raw experimental evidence is maintained separately
from the public source code repository.

## Experimental Limitations

- Email delivery latency uses timestamp-based estimates.
- Negative SPF and DKIM functional tests have limited samples.
- STARTTLS testing verifies client-to-Alpha SMTP encryption.
- Test 02 was recovered from an independent repeated baseline run.
- The system is intended for an isolated educational environment.

## Security

Do not upload IMAP passwords, password hashes,
TLS private keys or DKIM private signing keys.

Review packet captures and screenshots for sensitive
information before sharing them.

## Project Team

- Adil
- Zaid

Individual contributions and AI-assisted development
disclosure are documented in the accompanying report.

## Stop Project

```bash
./run-cn12.sh stop
```

Stopping the services does not intentionally remove
the existing containers or their mailbox data.

## Docker Build Files

The repository contains the following Docker build definitions:

- Dockerfile
- beta/Dockerfile
- beta/Dockerfile.dkim
- beta/Dockerfile.imap
- beta/Dockerfile.spf
- dns/Dockerfile
- mail-alpha/Dockerfile
- mail-alpha/Dockerfile.dkim
- mail-alpha/Dockerfile.imap
- network/Dockerfile
