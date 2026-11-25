# CN Mail — Local Mail System

**CS3001 Computer Networks | Project 12 | Fall 2026 | FAST NUCES**

## Project Overview

CN Mail is a Docker-based local email communication system that enables secure email communication between two domains, `alpha.lab` and `beta.lab`, connected through two Linux routers and three IPv4 subnets.

The system includes a Python-based desktop GUI with purple light and dark themes for sending and receiving emails.

## Features

- SMTP email transmission
- IMAP email retrieval
- DNS A, MX and TXT records
- SPF sender authentication
- DKIM digital signature verification
- STARTTLS encryption
- Static routing and IP subnetting
- Wireshark protocol analysis
- Performance benchmarking
- Desktop GUI with light and dark modes

## Network Architecture

![Network Topology](captures/final-evidence/07_Network_Architecture/CN12_Final_Network_Topology.png)

| Network | Subnet |
|---|---|
| Alpha LAN | 10.10.1.0/24 |
| Core Network | 10.10.0.0/24 |
| Beta LAN | 10.10.2.0/24 |

## Technologies Used

- Python and Tkinter
- Ubuntu Linux
- Docker and Docker Compose
- Postfix
- Dovecot
- BIND9
- OpenDKIM
- Wireshark
- Linux Traffic Control (Netem and TBF)

## Start the Project

On the configured Ubuntu environment:

```bash
sudo systemctl start docker
./run-cn12.sh up -d --no-build
./run-cn12.sh ps
```

A fresh installation requires building the Docker images and
configuring private credentials, DKIM keys and TLS certificates.

## Launch the GUI

Install Tkinter if required:

```bash
sudo apt install python3-tk
```

**Terminal 1 — Sender**

```bash
python3 cn12_demo_gui.py sender
```

**Terminal 2 — Receiver**

```bash
python3 cn12_demo_gui.py receiver
```

## Testing and Results

| Evaluation | Result |
|---|---|
| Functional Tests | 20/20 Passed |
| Wireshark Scenarios | 10/10 |
| Performance Experiments | 15/15 Passed |
| Workload Emails Delivered | 15,000/15,000 |
| SPF Positive Pass Rate | 100% |
| DKIM Positive Pass Rate | 100% |
| SMTP Command Measurements | 360 |
| STARTTLS Comparison Transactions | 60 |

Unauthorized SPF senders were rejected, and tampered DKIM
signatures were successfully detected.

Delivery latency measurements are estimates. The system is
intended for an isolated educational environment.

## Project Evidence

- [Functional Tests](captures/final-evidence/02_Functional_Tests/)
- [Wireshark Captures](captures/final-evidence/03_Wireshark/)
- [Performance Experiments](captures/final-evidence/04_Performance_Experiments/)
- [Additional Measurements](captures/final-evidence/05_Additional_Measurements/)
- [Statistics and Graphs](captures/final-evidence/06_Statistical_Analysis/)
- [Network Architecture](captures/final-evidence/07_Network_Architecture/)
- [Final Product Verification](captures/final-evidence/08_Final_Product_Verification/)
- [Screenshots](captures/final-evidence/09_Screenshots_Review/)

## Team Members

| Name | Roll Number |
|---|---|
| Zaid Faraz | 24K-0636 |
| Muhammad Adil Saeed | 24K-0705 |

**Instructor:** Dr. Ghufran Ahmed

**University:** FAST NUCES

## AI Disclosure

AI tools assisted with implementation, debugging and
documentation. Experimental testing and validation were
performed in the team laboratory environment.

## Security

Private passwords, password hashes and cryptographic private
keys are excluded from the repository.
