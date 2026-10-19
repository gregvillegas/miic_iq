# MIICiQ — On-Premise & Intranet Deployment Guide

**Application:** MIICiQ — Internal Knowledge Assistant  
**Architecture:** Retrieval-Augmented Generation (RAG) with 100% Private Local LLM  
**Security Level:** On-Premise / Air-Gapped Intranet (Zero External Cloud API Calls)  

---

## 1. System Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    Company Intranet / Employee Web     │
                      │  (Direct Web Access / Portal Iframe)   │
                      └──────────────────┬─────────────────────┘
                                         │ HTTP / HTTPS (SSE Stream)
                                         ▼
                      ┌────────────────────────────────────────┐
                      │          Nginx Reverse Proxy           │
                      │  • SSL Termination (Port 443/80)       │
                      │  • X-Frame-Options: SAMEORIGIN         │
                      │  • proxy_buffering off (SSE Streams)   │
                      └──────────────────┬─────────────────────┘
                                         │
                                         ▼
                      ┌────────────────────────────────────────┐
                      │         Django Web Application         │
                      │  • RAG Orchestration & Prompt Guard    │
                      │  • Hybrid Search (Dense + BM25Okapi)   │
                      │  • Role-Based Access Control (RBAC)    │
                      │  • Security Audit & Query Analytics    │
                      └──────────┬───────────────────┬─────────┘
                                 │                   │
                     Dense Query │                   │ Prompt + Grounded Context
                                 ▼                   ▼
       ┌───────────────────────────────────┐  ┌──────────────────────────────────┐
       │   Local ChromaDB Vector Database  │  │    Local Ollama LLM Inference    │
       │   • 384-d Persistent Vector Store │  │    • llama3.1:8b-instruct        │
       │   • Page-level Chunk Metadata     │  │    • Local GPU / CPU Execution   │
       │   • Document Category/Role Filter │  │    • http://localhost:11434      │
       └───────────────────────────────────┘  └──────────────────────────────────┘
```

---

## 2. Prerequisites & Hardware Specifications

### Recommended Server Hardware
| Component | Minimum Specification | Recommended Production Spec |
| :--- | :--- | :--- |
| **CPU** | 8 Cores (x86_64 or Apple Silicon ARM64) | 16+ Cores |
| **RAM** | 16 GB | 32 GB - 64 GB |
| **GPU** | Optional (Runs in CPU mode <10s) | NVIDIA RTX 3090 / 4090 / A4000 / A5000 (16GB+ VRAM) |
| **Storage** | 50 GB SSD | 250 GB NVMe SSD |
| **OS** | Ubuntu 22.04 LTS / Debian 12 / macOS Sonoma+ | Ubuntu 24.04 LTS / RHEL 9 |

---

## 3. Fast Deployment via Docker Compose (Recommended)

### Step 1: Clone Repository & Create Data Directories
```bash
git clone <your-internal-git-repo>/MIIC_iQ.git
cd MIIC_iQ
mkdir -p media staticfiles chroma_db
```

### Step 2: Start Containers
```bash
docker compose up -d --build
```

### Step 3: Pull Ollama Local Model
In the running Ollama container:
```bash
docker exec -it miiciq_ollama ollama pull llama3.1:8b-instruct
```

### Step 4: Verify Services
```bash
docker compose ps
# Expected status: miiciq_web, miiciq_ollama, miiciq_nginx all Up
```
Access the application at `http://<your-server-ip>/` or `http://localhost/`.

---

## 4. Bare-Metal / Native Systemd Deployment

If deploying directly onto an internal Linux virtual machine without Docker:

### Step 1: Install Python & Ollama
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y python3-venv python3-pip nginx
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Setup Python Virtual Environment
```bash
cd /opt/miiciq
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Run Database Migrations & Ingest Initial SOPs
```bash
python manage.py migrate
python manage.py ingest_samples
```

### Step 4: Configure Systemd for Ollama Service
Create `/etc/systemd/system/ollama.service`:
```ini
[Unit]
Description=Ollama Local LLM Service
After=network.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_KEEP_ALIVE=24h"

[Install]
WantedBy=multi-user.target
```

### Step 5: Configure Systemd for MIICiQ Gunicorn
Create `/etc/systemd/system/miiciq.service`:
```ini
[Unit]
Description=MIICiQ Knowledge Assistant Gunicorn Daemon
After=network.target ollama.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/miiciq
ExecStart=/opt/miiciq/venv/bin/gunicorn config.wsgi:application \
          --workers 4 \
          --bind 127.0.0.1:8000 \
          --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

### Step 6: Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl enable --now miiciq
ollama pull llama3.1:8b-instruct
```

---

## 5. Enterprise Intranet Iframe Embedding

MIICiQ is pre-configured with headers allowing embedding inside company intranet portals (e.g. SharePoint, Confluence, internal wiki dashboards):

```html
<!-- Embed MIICiQ in your company intranet portal -->
<iframe 
  src="https://intranet.company.local/chat/" 
  width="100%" 
  height="750px" 
  style="border: 1px solid #1e293b; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
  title="MIICiQ Internal Knowledge Assistant">
</iframe>
```

---

## 6. Single Sign-On (SSO) Integration

MIICiQ supports company SSO architectures:
1. **Reverse Proxy Header Authentication** (Azure AD / Okta / Cloudflare Access):
   - Configure your reverse proxy to forward the authenticated employee email in the `X-Remote-User` header.
2. **LDAP / Active Directory Integration**:
   - Install `django-auth-ldap` to bind directly to Active Directory Domain Controllers.

---

## 7. Data Privacy Verification

To verify that **zero outbound data** leaves your corporate perimeter:
```bash
# Monitor outgoing network connections from the MIICiQ server
sudo tcpdump -i any not dst net 10.0.0.0/8 and not dst net 172.16.0.0/12 and not dst net 192.168.0.0/16 -n
```
All vector queries, text embeddings, and model inferences execute 100% locally on localhost.
