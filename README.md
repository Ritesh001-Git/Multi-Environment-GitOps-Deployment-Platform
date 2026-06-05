# GitOps Deployment Platform

Automated CI/CD, Kubernetes Orchestration, and Real-Time Observability for containerized applications.

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your-username/gitops-platform)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.28%2B-blue)](https://kubernetes.io/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0%2B-blue)](https://www.typescriptlang.org/)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage Workflow](#usage-workflow)
- [API Documentation](#api-documentation)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Monitoring and Observability](#monitoring-and-observability)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The GitOps Deployment Platform automates the entire deployment lifecycle from GitHub push to running Kubernetes pods. Developers submit repository URLs through a web interface, triggering a fully automated pipeline that clones code, builds Docker images, pushes to Docker Hub, deploys to Kubernetes with zero-downtime rolling updates, and streams real-time metrics to Grafana.

**Key Value Propositions:**
- **Zero Manual Intervention**: Entire pipeline runs automatically end-to-end
- **Zero-Downtime Deployments**: Rolling updates with readiness probes
- **Automatic Rollback**: Failed deployments automatically revert
- **Real-Time Visibility**: Live deployment tracking via WebSocket
- **Enterprise Observability**: Prometheus + Grafana dashboards
- **Infrastructure as Code**: Terraform provisioning from scratch

---

## Features

### CI/CD Pipeline
- ✅ Dynamic GitHub repository submission
- ✅ Parameterized Jenkins pipeline (no per-repo job creation)
- ✅ Docker multi-stage builds with semantic versioning
- ✅ Automatic Docker Hub push with `:BUILD_NUMBER` and `:latest` tags
- ✅ 6-stage pipeline: Clone → Build → Push → Deploy → Verify → Health Check

### Kubernetes Orchestration
- ✅ k3s lightweight Kubernetes cluster on EC2
- ✅ Rolling deployment strategy with zero downtime
- ✅ Horizontal Pod Autoscaling (2-6 replicas based on CPU/memory)
- ✅ RBAC with scoped ServiceAccount for Jenkins
- ✅ Pod health checks (liveness & readiness probes)
- ✅ Automatic pod restart on failure

### Real-Time Observability
- ✅ WebSocket-based live deployment tracker
- ✅ Per-stage metrics (queue time, build time, deploy time)
- ✅ Prometheus metrics collection from 9 sources
- ✅ 6 pre-built Grafana dashboards
- ✅ Custom deployment metrics
- ✅ Alert routing via Alertmanager

### Developer Experience
- ✅ Simple web dashboard: paste GitHub URL → deploy
- ✅ Live status updates without polling
- ✅ Deployment history with success rates
- ✅ Direct links to Grafana and Prometheus
- ✅ WebSocket-based real-time pod monitoring

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEVELOPER WORKFLOW                          │
│  Submit GitHub URL via React Dashboard → FastAPI → Jenkins Pipeline │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────────┐      ┌──────────────────────┐
│  JENKINS EC2         │      │   APP EC2            │
│  (CI/CD + Monitor)   │      │   (Deployment)       │
├──────────────────────┤      ├──────────────────────┤
│ • Jenkins :8080      │◄────►│ • k3s Cluster        │
│ • Prometheus :9090   │      │ • FastAPI :8000      │
│ • Grafana :3001      │      │ • Node Exporter      │
│ • Alertmanager       │      │ • cAdvisor :8081     │
│ • cAdvisor :8081     │      │ • Deployment Pods    │
│ • Docker Build       │      │ • WebSocket :8000/ws │
│ • Docker Hub Push    │      │ • SQLite DB          │
│ • Docker Compose     │      │ • kubectl apply      │
└──────────────────────┘      └──────────────────────┘
        │                             │
        └──────────────┬──────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
   GITHUB                      DOCKER HUB
   (Webhook)                   (Image Registry)
```

### Data Flow

```
1. Developer submits GitHub repo URL via React dashboard
   └─→ HTTP POST /api/deployments (FastAPI)

2. FastAPI creates deployment record in SQLite
   └─→ Triggers background task: run_pipeline()

3. Background task triggers Jenkins via buildWithParameters
   └─→ Jenkins queue ID returned

4. Jenkins receives build parameters (REPO_URL, BRANCH, DOCKER_IMAGE)
   └─→ Starts 6-stage pipeline

5. Jenkins Pipeline Stages:
   a. Clone Repository (git clone REPO_URL)
   b. Build Docker Image (docker build :BUILD_NUMBER)
   c. Push to Docker Hub (docker push)
   d. Deploy to Kubernetes (kubectl apply -f deployment.yaml)
   e. Verify Rollout (kubectl rollout status --timeout 180s)
   f. Health Check (curl :30080/health)

6. FastAPI background task polls Jenkins until completion
   └─→ Updates SQLite with final status, duration, build number

7. React frontend receives WebSocket updates
   └─→ Displays status progression: queued → running → success

8. Prometheus scrapes metrics from FastAPI, Jenkins, k3s, EC2s
   └─→ Grafana displays on 6 dashboards

9. Deployment history available at /api/deployments
   └─→ Success rate, avg duration, pod count tracked
```

---

## Technology Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Cloud** | AWS EC2 (t2.micro × 2) | Compute infrastructure |
| **IaC** | Terraform | Provision EC2, security groups, elastic IPs |
| **CI/CD** | Jenkins | Pipeline orchestration, parameterized jobs |
| **Container** | Docker | Multi-stage builds, semantic versioning |
| **Registry** | Docker Hub | Image storage and versioning |
| **Orchestration** | Kubernetes (k3s) | Pod deployment, rolling updates, HPA |
| **Backend** | FastAPI | Async Python API, WebSocket, SQLAlchemy ORM |
| **Database** | SQLite | Deployment history, persistent state |
| **Frontend** | React + Vite | SPA dashboard, real-time tracker |
| **Metrics** | Prometheus | Time-series database, 9 scrape targets |
| **Visualization** | Grafana | Dashboards, alerts, data provisioning |
| **Monitoring** | Docker Compose | Orchestrate Prometheus, Grafana, Alertmanager |
| **System Metrics** | Node Exporter + cAdvisor | EC2 CPU/RAM/disk, container metrics |

---

## Prerequisites

### For Local Development
- macOS or Linux
- Docker Desktop running
- Python 3.9+
- Node.js 18+
- kubectl installed
- Terraform 1.0+
- AWS CLI v2 with credentials configured
- SSH key pair for EC2 access

### For EC2 Deployment
- AWS account with EC2 permissions
- SSH key pair (`~/.ssh/gitops-key.pem`)
- GitHub personal access token (for webhook)
- Docker Hub account and credentials
- GitHub repository to deploy (with public clone URL)

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/gitops-platform.git
cd gitops-platform
```

### 2. Set Up Infrastructure (AWS)
```bash
# Provision EC2 instances with Terraform
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Note the outputs:
# - jenkins_ec2_public_ip
# - app_ec2_public_ip
# - jenkins_ec2_private_ip
# - app_ec2_private_ip
```

### 3. Configure Jenkins
```bash
# SSH into Jenkins EC2
ssh -i ~/.ssh/gitops-key.pem ubuntu@JENKINS_EC2_PUBLIC_IP

# Jenkins automatically starts
# Access at http://JENKINS_EC2_PUBLIC_IP:8080
# - Create API token: Manage Jenkins → Security → API Token
# - Copy token to backend/.env as JENKINS_TOKEN
```

### 4. Set Up k3s Cluster
```bash
# SSH into App EC2
ssh -i ~/.ssh/gitops-key.pem ubuntu@APP_EC2_PUBLIC_IP

# Install k3s
curl -sfL https://get.k3s.io | sh -

# Verify
sudo kubectl get nodes

# Copy kubeconfig to Jenkins EC2
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown ubuntu:ubuntu ~/.kube/config

# SCP to Jenkins EC2 and Jenkins user
```

### 5. Start FastAPI Backend
```bash
# On App EC2
cd ~/gitops-platform/backend
nano .env  # Configure Jenkins URL, Docker Hub credentials, etc.
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 &
```

### 6. Start React Frontend
```bash
# On App EC2 or locally
cd ~/gitops-platform/frontend
npm install
npm run build
npm run preview  # or `npm run dev` for development
```

### 7. Start Monitoring Stack
```bash
# On Jenkins EC2
cd ~/monitoring
docker compose -f docker-compose.monitoring.yml up -d

# Verify services
curl http://localhost:9090/targets  # Prometheus
curl http://localhost:3001         # Grafana (default: admin/admin)
```

### 8. Test Deployment
```bash
# Open React dashboard
http://APP_EC2_PUBLIC_IP:3000

# Submit deployment
Repo URL: https://github.com/your-username/your-app
Branch: main

# Watch Jenkins console
http://JENKINS_EC2_PUBLIC_IP:8080/job/gitops-deploy/

# View metrics
http://JENKINS_EC2_PUBLIC_IP:9090/targets     # Prometheus
http://JENKINS_EC2_PUBLIC_IP:3001/dashboards  # Grafana
```

---

## Installation

### Local Development Setup

```bash
# 1. Clone and navigate
git clone https://github.com/your-username/gitops-platform.git
cd gitops-platform

# 2. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install backend dependencies
cd backend
pip install -r requirements.txt
cp .env.example .env
nano .env  # Edit with your configuration

# 4. Start FastAPI locally
uvicorn main:app --reload

# 5. In another terminal, set up frontend
cd ../frontend
npm install
npm run dev

# 6. For local Kubernetes testing
minikube start
kubectl apply -f ../k8s/

# Access dashboard at http://localhost:5173
```

### EC2 Deployment via Terraform

```bash
# 1. Initialize Terraform
cd terraform
terraform init

# 2. Create terraform.tfvars
cat > terraform.tfvars << EOF
aws_region         = "us-east-1"
jenkins_instance_type = "t2.micro"
app_instance_type    = "t2.small"
key_name           = "gitops-key"
my_ip              = "YOUR.IP.ADDRESS.HERE"  # For SSH access
EOF

# 3. Plan and apply
terraform plan
terraform apply

# 4. Save outputs
terraform output > infrastructure.txt

# 5. Wait for instances to boot (~3 minutes)
# Then follow "Configuration" section below
```

---

## Usage Workflow

### Step 1: Developer Submits Repository

**Via Web Dashboard:**
1. Open http://APP_EC2_IP:3000
2. Click "New Deployment"
3. Paste GitHub HTTPS URL: `https://github.com/username/repo`
4. Select branch: `main`
5. Click "Deploy Now"

**Via API:**
```bash
curl -X POST http://APP_EC2_IP:8000/api/deployments \
  -H 'Content-Type: application/json' \
  -d '{
    "repo_url": "https://github.com/username/repo",
    "branch": "main",
    "environment": "local-k8s"
  }'

# Response:
{
  "deployment_id": "abc-123-def-456",
  "jenkins_build_number": null,
  "message": "Deployment queued",
  "status": "queued"
}
```

### Step 2: Watch Deployment Progress

**Real-Time WebSocket:**
```bash
# Connect to WebSocket for live updates
websocat ws://APP_EC2_IP:8000/api/deployments/abc-123-def-456/ws

# Receives JSON updates every 5 seconds:
{
  "id": "abc-123-def-456",
  "status": "running",
  "jenkins_build_number": 42,
  "jenkins_build_url": "http://jenkins:8080/job/gitops-deploy/42/",
  "duration_seconds": null,
  "finished_at": null
}

# Status transitions: queued → running → success/failed
```

**Via Dashboard:**
- Live status card shows current stage
- Real-time duration counter
- Links to Jenkins console
- History table of all deployments

### Step 3: Monitor in Grafana

**Dashboard URLs:**
- Cluster Health: http://JENKINS_IP:3001/d/15661/k3s-cluster
- FastAPI Metrics: http://JENKINS_IP:3001/d/17175/fastapi
- Jenkins Pipeline: http://JENKINS_IP:3001/d/14282/jenkins
- Node Exporter: http://JENKINS_IP:3001/d/1860/node-exporter

**Key Metrics Tracked:**
- Deployment success rate (%)
- Active pod count
- Pipeline duration (p95)
- HTTP request latency
- Jenkins build queue depth
- EC2 CPU/RAM/Disk usage
- Container restart count

### Step 4: Verify Deployment

```bash
# Check pods running on k3s
kubectl get pods -n gitops

# View pod logs
kubectl logs -n gitops deployment/gitops-app

# Check service endpoints
kubectl get service -n gitops

# Access deployed application
curl http://APP_EC2_IP:30080/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-05-27T12:34:56Z"
}
```

---

## API Documentation

### Base URL
```
http://APP_EC2_IP:8000/api/deployments
```

### Endpoints

#### 1. Get Dashboard Stats
```bash
GET /stats

Response:
{
  "total_deployments": 10,
  "successful_deployments": 9,
  "failed_deployments": 1,
  "running_deployments": 0,
  "success_rate": 90.0,
  "running_pods": 2,
  "active_services": 3,
  "avg_duration_seconds": 125.5
}
```

#### 2. Trigger Deployment
```bash
POST /

Request:
{
  "repo_url": "https://github.com/user/repo",
  "branch": "main",
  "environment": "local-k8s"
}

Response (HTTP 202):
{
  "deployment_id": "abc-123",
  "jenkins_build_number": null,
  "message": "Deployment queued",
  "status": "queued"
}
```

#### 3. List Deployments
```bash
GET ?limit=50&offset=0&status=success

Response:
{
  "total": 10,
  "items": [
    {
      "id": "abc-123",
      "repo_url": "https://github.com/user/repo",
      "branch": "main",
      "status": "success",
      "jenkins_build_number": 42,
      "duration_seconds": 125.5,
      "started_at": "2025-05-27T10:00:00Z",
      "finished_at": "2025-05-27T10:02:05Z"
    }
  ]
}
```

#### 4. Get Deployment Status
```bash
GET /{deployment_id}/status

Response:
{
  "id": "abc-123",
  "status": "success",
  "jenkins_build_number": 42,
  "jenkins_build_url": "http://jenkins:8080/job/gitops-deploy/42/",
  "duration_seconds": 125.5,
  "finished_at": "2025-05-27T10:02:05Z"
}
```

#### 5. Get Full Deployment Details
```bash
GET /{deployment_id}

Response:
{
  "id": "abc-123",
  "repo_url": "https://github.com/user/repo",
  "repo_name": "user/repo",
  "branch": "main",
  "commit_sha": null,
  "docker_image": "username/repo",
  "docker_tag": "42",
  "jenkins_build_number": 42,
  "jenkins_build_url": "http://jenkins:8080/job/gitops-deploy/42/",
  "k8s_namespace": "gitops",
  "k8s_deployment_name": "gitops-app",
  "status": "success",
  "environment": "local-k8s",
  "started_at": "2025-05-27T10:00:00Z",
  "finished_at": "2025-05-27T10:02:05Z",
  "duration_seconds": 125.5,
  "triggered_by": "api"
}
```

#### 6. Kubernetes Overview
```bash
GET /kubernetes/overview?namespace=gitops

Response:
{
  "namespace": "gitops",
  "node_count": 1,
  "pod_count": 2,
  "service_count": 1,
  "deployment_count": 1,
  "nodes": [...],
  "pods": [...]
}
```

#### 7. WebSocket Live Status
```
ws://APP_EC2_IP:8000/api/deployments/ws/{deployment_id}

Sends JSON every 5 seconds until deployment completes:
{
  "id": "abc-123",
  "status": "running",
  "jenkins_build_number": 42,
  "jenkins_build_url": "...",
  "duration_seconds": 45,
  "finished_at": null
}
```

### Error Responses

```bash
# 404 Not Found
{
  "detail": "Deployment abc-123 not found"
}

# 500 Internal Server Error
{
  "detail": "Failed to fetch deployment"
}
```

---

## Kubernetes Deployment

### Initial Setup

```bash
# 1. Create namespace
kubectl create namespace gitops

# 2. Apply manifests
kubectl apply -f k8s/rbac.yaml           # ServiceAccount + Role
kubectl apply -f k8s/service.yaml         # NodePort service
kubectl apply -f k8s/deployment.yaml      # Deployment template

# 3. Verify
kubectl get ns gitops
kubectl get sa -n gitops
kubectl get svc -n gitops
kubectl get pods -n gitops
```

### Manifests

**Deployment** (`k8s/deployment.yaml`):
- Replicas: 2
- Strategy: RollingUpdate (maxUnavailable: 1)
- Image: Replaced dynamically by Jenkins pipeline
- Health checks: Liveness and readiness probes
- Resource requests: 128Mi RAM, 100m CPU
- Resource limits: 256Mi RAM, 300m CPU

**Service** (`k8s/service.yaml`):
- Type: NodePort
- Port: 80
- TargetPort: 8000
- NodePort: 30080

**HPA** (`k8s/hpa.yaml`):
- Min replicas: 2
- Max replicas: 6
- CPU threshold: 70%
- Memory threshold: 80%

### Manual Deployment (for testing)

```bash
# 1. Create deployment from manifest
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitops-app
  namespace: gitops
spec:
  replicas: 2
  selector:
    matchLabels:
      app: gitops-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  template:
    metadata:
      labels:
        app: gitops-app
    spec:
      containers:
      - name: app
        image: your-username/your-app:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "300m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
EOF

# 2. Watch rollout
kubectl rollout status deployment/gitops-app -n gitops --timeout=180s

# 3. View running pods
kubectl get pods -n gitops

# 4. Check logs
kubectl logs -n gitops deployment/gitops-app

# 5. Rollback if needed
kubectl rollout undo deployment/gitops-app -n gitops
```

---

## Monitoring and Observability

### Prometheus Targets

| Job | Endpoint | Purpose |
|-----|----------|---------|
| prometheus | localhost:9090 | Self-monitoring |
| jenkins | JENKINS_IP:8080/prometheus/ | Build metrics |
| fastapi-backend | APP_IP:8000/metrics | HTTP + custom metrics |
| node-jenkins-ec2 | localhost:9100 | Jenkins EC2 system |
| node-app-ec2 | APP_IP:9100 | App EC2 system |
| cadvisor-jenkins-ec2 | cadvisor:8080 | Jenkins containers |
| cadvisor-app-ec2 | APP_IP:8081 | App containers |
| kube-state-metrics | APP_IP:30091 | Kubernetes object state |
| alertmanager | alertmanager:9093 | Alert routing |

### Custom Metrics

```prometheus
# Deployment metrics
gitops_deployments_total                # Counter: total deployments
gitops_deployments_success_total        # Counter: successful deployments
gitops_deployments_failed_total         # Counter: failed deployments
gitops_active_deployments               # Gauge: currently running deployments
gitops_deployment_duration_seconds      # Histogram: pipeline duration (p50, p95, p99)

# Jenkins metrics
gitops_jenkins_builds_triggered         # Counter: builds triggered
gitops_jenkins_build_duration_seconds   # Histogram: build durations
```

### Grafana Dashboards

Pre-built dashboards available at http://JENKINS_IP:3001/dashboards:

1. **k3s Cluster** (ID: 15661) — Node health, pod count, resource usage
2. **Kubernetes Deployments** (ID: 14205) — Replica count, rollout status
3. **FastAPI Metrics** (ID: 17175) — Request rate, latency, error rate
4. **Jenkins Pipeline** (ID: 14282) — Build duration, success rate, queue depth
5. **Node Exporter** (ID: 1860) — EC2 CPU, RAM, disk, network
6. **Docker Containers** (ID: 193) — Container CPU, memory, restart count

### Alert Rules

Located in `monitoring/rules/alerts.yml`:

```yaml
- DeploymentFailureRate > 10%
- PodRestartCount > 5 in 1 hour
- K8sNodeNotReady
- HighMemoryUsage (>80%)
- HighCPUUsage (>80%)
- PrometheusTargetDown
```

---

## Configuration

### Backend Environment Variables

Create `backend/.env`:

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./gitops.db

# Jenkins
JENKINS_URL=http://JENKINS_EC2_IP:8080
JENKINS_USER=admin
JENKINS_TOKEN=<from Jenkins UI>
JENKINS_JOB_NAME=gitops-deploy

# Docker Hub
DOCKERHUB_USER=your-username

# Kubernetes
KUBE_MODE=kubeconfig
KUBE_NAMESPACE=gitops

# CORS
ALLOWED_ORIGINS=http://APP_EC2_IP:3000,http://localhost:3000

# Polling
POLL_INTERVAL_SECONDS=5

# Debug
DEBUG=false
```

### Frontend Environment Variables

Create `frontend/.env`:

```bash
VITE_BACKEND_URL=http://APP_EC2_IP:8000
VITE_JENKINS_URL=http://JENKINS_EC2_IP:8080
VITE_GRAFANA_URL=http://JENKINS_EC2_IP:3001
VITE_PROMETHEUS_URL=http://JENKINS_EC2_IP:9090
```

### Prometheus Configuration

Edit `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'jenkins'
    metrics_path: '/prometheus/'
    static_configs:
      - targets: ['JENKINS_EC2_PRIVATE_IP:8080']
  
  - job_name: 'fastapi-backend'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['APP_EC2_PRIVATE_IP:8000']
  
  # ... more targets
```

Replace placeholders:
- `JENKINS_EC2_PRIVATE_IP` — Private IP of Jenkins EC2
- `APP_EC2_PRIVATE_IP` — Private IP of App EC2

### Grafana Provisioning

Datasource auto-provisioned in `monitoring/grafana/provisioning/datasources/prometheus.yml`:

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

---

## Troubleshooting

### Frontend Stuck on "RUNNING"

**Issue**: Deployment shows RUNNING forever even though Jenkins completed
**Causes**:
1. Async SQLAlchemy session stale
2. WebSocket connection lost
3. Background task crashed

**Solution**:
```bash
# Check backend logs
ssh -i ~/.ssh/gitops-key.pem ubuntu@APP_EC2_IP
sudo journalctl -u gitops-backend -f

# Look for:
# - StaleDataError → session issue
# - RuntimeError → WebSocket issue
# - Exception → background task crash

# Apply fixes from IMPLEMENTATION_GUIDE.md
# Restart backend
sudo systemctl restart gitops-backend
```

### Kubernetes Pods Stuck in Pending

**Issue**: `kubectl get pods -n gitops` shows Pending
**Causes**: Insufficient resources, bad image, wrong node

**Solution**:
```bash
# Describe pod to see events
kubectl describe pod -n gitops POD_NAME

# Check node resources
kubectl top nodes

# Check image pull
kubectl get events -n gitops
```

### Jenkins Build Fails

**Issue**: Jenkins console shows red
**Causes**: Docker build error, Docker Hub auth, git clone failure

**Solution**:
```bash
# View full log
curl http://JENKINS_IP:8080/job/gitops-deploy/BUILD_NUMBER/consoleText

# Test Docker Hub credentials
docker login -u DOCKERHUB_USER
docker pull DOCKERHUB_USER/IMAGE:latest

# Test git clone
git clone https://github.com/user/repo
```

### Prometheus Targets DOWN

**Issue**: Prometheus shows "1 down, 8 up"
**Causes**: Service not running, port not open, wrong IP

**Solution**:
```bash
# Check service running
# On target EC2:
curl http://localhost:9100/metrics  # For Node Exporter
curl http://localhost:8000/metrics  # For FastAPI

# Check security group allows Prometheus EC2's IP
# Check prometheus.yml has correct IPs

# Reload Prometheus
curl -X POST http://JENKINS_IP:9090/-/reload
```

### WebSocket Connection Closed

**Issue**: "WebSocket disconnected" in frontend logs
**Causes**: Session timeout, exception in handler, client disconnected

**Solution**:
```bash
# Check backend logs for exception
sudo journalctl -u gitops-backend -f | grep -E "WebSocket|Exception"

# Verify WebSocket route exists
curl -i http://APP_EC2_IP:8000/api/deployments/abc-123/status

# Verify ALLOWED_ORIGINS in .env includes frontend URL
```

---

## Project Structure

```
gitops-platform/
├── README.md                          # This file
├── LICENSE                            # MIT License
├── .gitignore
├── .github/
│   └── workflows/                     # GitHub Actions (optional)
│
├── terraform/                         # Infrastructure as Code
│   ├── main.tf                        # EC2 instances
│   ├── security.tf                    # Security groups
│   ├── variables.tf                   # Input variables
│   ├── outputs.tf                     # Outputs (IPs, etc)
│   └── terraform.tfvars               # Configuration (NOT in git)
│
├── backend/                           # FastAPI backend
│   ├── main.py                        # Application entry point
│   ├── requirements.txt               # Python dependencies
│   ├── .env                           # Environment variables (NOT in git)
│   ├── gitops.db                      # SQLite database (NOT in git)
│   ├── core/
│   │   └── config.py                  # Configuration/settings
│   ├── models/
│   │   └── deployment.py              # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── deployment.py              # Pydantic request/response schemas
│   ├── services/
│   │   └── deployment_service.py      # Business logic, Jenkins integration
│   ├── api/
│   │   └── routes/
│   │       └── deployments.py         # REST + WebSocket endpoints
│   ├── db/
│   │   └── database.py                # SQLAlchemy async setup
│   ├── k8s/
│   │   └── client.py                  # Kubernetes Python client
│   └── metrics.py                     # Prometheus metric definitions
│
├── frontend/                          # React + Vite frontend
│   ├── package.json                   # Node dependencies
│   ├── vite.config.js                 # Vite configuration
│   ├── tailwind.config.js             # Tailwind CSS configuration
│   ├── index.html
│   ├── .env                           # Environment variables (NOT in git)
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── types/
│       │   └── index.ts               # TypeScript types
│       ├── api/
│       │   └── client.ts              # HTTP client, API methods
│       ├── hooks/
│       │   └── index.ts               # Custom React hooks
│       ├── components/
│       │   ├── dashboard/             # Dashboard components
│       │   ├── deployments/           # Deployment list/tracker
│       │   ├── pods/                  # Pod monitoring
│       │   └── common/                # Reusable UI components
│       └── pages/
│           └── Dashboard.tsx          # Main page
│
├── k8s/                               # Kubernetes manifests
│   ├── deployment.yaml                # Pod deployment (templated)
│   ├── service.yaml                   # NodePort/ClusterIP service
│   ├── hpa.yaml                       # HorizontalPodAutoscaler
│   ├── rbac.yaml                      # ServiceAccount + Role
│   ├── kube-state-metrics-nodeport.yaml
│   ├── ingress-traefik.yaml           # Traefik ingress
│   └── ingress-nginx.yaml             # NGINX ingress
│
├── monitoring/                        # Prometheus + Grafana stack
│   ├── docker-compose.monitoring.yml  # Orchestration
│   ├── prometheus.yml                 # Prometheus config
│   ├── alertmanager.yml               # Alert routing
│   ├── rules/
│   │   └── alerts.yml                 # Alert rules
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml     # Auto-provision Prometheus
│           └── dashboards/            # Imported at startup
│
├── Jenkinsfile                        # Pipeline definition
│
└── docs/                              # Additional documentation
    ├── ARCHITECTURE.md
    ├── SETUP_GUIDE.md
    ├── TROUBLESHOOTING.md
    ├── API_REFERENCE.md
    └── KUBERNETES_SETUP.md
```

---

## Contributing

### Code Standards

- **Backend**: PEP 8, type hints, async/await properly used
- **Frontend**: ESLint, Prettier, TypeScript strict mode
- **Infrastructure**: Terraform formatting (`terraform fmt`)

### Testing

```bash
# Backend unit tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend
npm run test

```

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "feat: description"`
4. Push to branch: `git push origin feature/your-feature`
5. Submit a Pull Request

### Bug Reports

Please include:
- Reproduction steps
- Expected behavior
- Actual behavior
- Backend logs (sanitized)
- Environment (local/EC2, Python version, etc)

---

## License

MIT License — see LICENSE file for details.

---

## Acknowledgments

Built with:
- FastAPI for async Python backend
- React for interactive frontend
- Kubernetes (k3s) for container orchestration
- Jenkins for CI/CD
- Prometheus + Grafana for observability

---

## Roadmap

- [ ] Multi-cluster deployments (Kubernetes federation)
- [ ] GitOps reconciliation (ArgoCD integration)
- [ ] Canary deployments with traffic splitting
- [ ] Database migration automation
- [ ] Helm chart support
- [ ] Slack/Teams webhook notifications
- [ ] Cost estimation and optimization
- [ ] Multi-region failover

---

**Last Updated**: May 2026
**Maintainer**: Ritesh  
**Status**: Production Ready
