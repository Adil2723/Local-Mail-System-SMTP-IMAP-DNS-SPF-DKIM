
<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:49318C,50:7952B3,100:251447&height=210&section=header&text=CN%20MAIL&fontSize=68&fontColor=ffffff&fontAlignY=38&desc=Local%20Mail%20Communication%20System&descAlignY=59&descSize=18" width="100%"/>

### Secure Email Communication Across Local Domains

<p>
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/SMTP-7952B3?style=for-the-badge"/>
<img src="https://img.shields.io/badge/IMAP-6A5ACD?style=for-the-badge"/>
</p>

<p>
<img src="https://img.shields.io/badge/SPF-Authentication-7057C8?style=flat-square"/>
<img src="https://img.shields.io/badge/DKIM-Signatures-7057C8?style=flat-square"/>
<img src="https://img.shields.io/badge/STARTTLS-Encryption-7057C8?style=flat-square"/>
<img src="https://img.shields.io/badge/Status-Completed-success?style=flat-square"/>
</p>

</div>

---

## 📬 Overview

**CN Mail** is a Docker-based local email communication system that enables secure email exchange between two independent domains: `alpha.lab` and `beta.lab`.

The system uses a multi-subnet network architecture with two Linux routers to facilitate communication between both domains through static routing.

It integrates SMTP for email transmission, IMAP for email retrieval, DNS for domain resolution, SPF and DKIM for email authentication, and STARTTLS for encrypted communication.

CN Mail also includes a Python-based desktop GUI with separate sender and receiver interfaces, featuring a custom purple-themed design with light and dark modes.

## ✨ Features

| Feature | Description |
|---|---|
| 📤 SMTP | Email transmission using Postfix |
| 📥 IMAP | Email retrieval using Dovecot |
| 🌐 DNS | A, MX and TXT record configuration |
| 🛡️ SPF | Sender authentication and validation |
| 🔏 DKIM | Digital signature generation and verification |
| 🔒 STARTTLS | Encrypted email communication |
| 🖧 Static Routing | Communication across multiple IPv4 subnets |
| 📊 Wireshark | Network protocol analysis |
| ⚡ Benchmarking | Network performance experiments |
| 🖥️ Desktop GUI | Python-based sender and receiver interfaces |
| 🎨 Themes | Custom purple light and dark modes |

## 🏗️ Network Architecture

<div align="center">

<img src="captures/final-evidence/07_Network_Architecture/CN12_Final_Network_Topology.png" width="95%" alt="CN Mail Network Architecture"/>

*CN Mail Network Topology*

</div>

### Network Configuration

| Network | Subnet |
|---|---|
| Alpha LAN | `10.10.1.0/24` |
| Core Network | `10.10.0.0/24` |
| Beta LAN | `10.10.2.0/24` |

## 🛠️ Technology Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,linux,docker,bash&theme=dark" alt="Technology Stack"/>

</div>

| Technology | Purpose |
|---|---|
| Python & Tkinter | Desktop GUI |
| Ubuntu Linux | Host environment |
| Docker & Docker Compose | Containerized infrastructure |
| Postfix | SMTP mail server |
| Dovecot | IMAP mail server |
| BIND9 | DNS services |
| OpenDKIM | DKIM authentication |
| Wireshark | Network traffic analysis |
| Linux Traffic Control | Network emulation using Netem and TBF |

## 🚀 Getting Started

### Prerequisites

- Ubuntu Linux environment
- Docker and Docker Compose
- Python 3
- Tkinter

### 1. Start Docker

```bash
sudo systemctl start docker
```

### 2. Start the Mail Infrastructure

```bash
./run-cn12.sh up -d --no-build
```

### 3. Verify Running Containers

```bash
./run-cn12.sh ps
```

> **Note:** A fresh installation requires building the Docker images and configuring private credentials, DKIM keys, and TLS certificates.

## 🖥️ Desktop Application

Install Tkinter if required:

```bash
sudo apt install python3-tk
```

Launch the sender and receiver interfaces in two separate terminals.

**Sender — Zaid**

```bash
python3 cn12_demo_gui.py sender
```

**Receiver — Adil**

```bash
python3 cn12_demo_gui.py receiver
```

The desktop application provides:

- Email composition and transmission.
- Inbox listing and message retrieval.
- Message searching and reading.
- SMTP protocol transcript inspection.
- Email authentication details.
- STARTTLS connection support.
- Light and dark interface themes.

## 📊 Testing & Performance

<div align="center">

| Evaluation | Result |
|:---:|:---:|
| Functional Tests | **20/20 Passed** |
| Wireshark Scenarios | **10/10 Completed** |
| Performance Experiments | **15/15 Passed** |
| Emails Delivered | **15,000/15,000** |
| SPF Positive Pass Rate | **100%** |
| DKIM Positive Pass Rate | **100%** |
| SMTP Command Measurements | **360** |
| STARTTLS Comparison Transactions | **60** |

</div>

### 🔍 Security Verification

- Unauthorized SPF senders were successfully rejected.
- Tampered DKIM signatures were successfully detected.
- STARTTLS encryption was evaluated through comparison experiments.
- SMTP and IMAP traffic were inspected using Wireshark.

> **Note:** Delivery latency measurements are estimates. CN Mail is designed for an isolated educational environment and is not intended for production email deployment.

## 📂 Project Evidence

Explore the available testing results, packet captures, statistical analysis, and application screenshots.

<details>
<summary><b>🧪 Functional Testing & Protocol Analysis</b></summary>

- [Functional Tests](captures/final-evidence/02_Functional_Tests/)
- [Wireshark Captures](captures/final-evidence/03_Wireshark/)

</details>

<details>
<summary><b>📈 Performance & Statistical Analysis</b></summary>

- [Performance Experiments](captures/final-evidence/04_Performance_Experiments/)
- [Additional Measurements](captures/final-evidence/05_Additional_Measurements/)
- [Statistics and Graphs](captures/final-evidence/06_Statistical_Analysis/)

</details>

<details>
<summary><b>🖼️ Architecture & Application Screenshots</b></summary>

- [Network Architecture](captures/final-evidence/07_Network_Architecture/)
- [Final Product Verification](captures/final-evidence/08_Final_Product_Verification/)
- [Screenshots](captures/final-evidence/09_Screenshots_Review/)

</details>

## 🔐 Security

Private passwords, password hashes, and cryptographic private keys are excluded from the repository.

CN Mail is designed for local network experimentation and demonstration rather than public email hosting.

---

<div align="center">

### CN Mail
**Local. Secure. Connected.**

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:251447,50:7952B3,100:49318C&height=110&section=footer" width="100%"/>

</div>
