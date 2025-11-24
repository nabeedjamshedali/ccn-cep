# Installation Guide

## Prerequisites

### Required Software

1. **Windows 10/11 with WSL2**
   ```powershell
   # In PowerShell (as Administrator)
   wsl --install
   wsl --set-default-version 2
   ```

2. **Ubuntu 22.04 on WSL**
   ```powershell
   wsl --install -d Ubuntu-22.04
   ```

3. **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Enable WSL2 integration in Docker Desktop settings
   - Allocate minimum: 4 CPUs, 6GB RAM

4. **Verify Docker in WSL**
   ```bash
   docker --version
   docker info
   ```

---

## Quick Install (Automated)

### Option 1: One-Command Install

```bash
cd ~/cnn-cep
make all
```

This runs:
1. Setup (installs tools, creates cluster, builds images)
2. Deploy (deploys all components)
3. Validate (runs 13 tests to verify)

**Time**: ~15 minutes

---

### Option 2: Step-by-Step Install

#### Step 1: Clone Repository

```bash
cd ~
git clone <repository-url> cnn-cep
cd cnn-cep
```

#### Step 2: Run Setup

```bash
./scripts/setup.sh
```

What it does:
- ✅ Checks for Docker, kubectl, Minikube, Python
- ✅ Installs missing tools automatically
- ✅ Creates 3-node Minikube cluster
- ✅ Builds all Docker images

**Time**: ~10 minutes

#### Step 3: Deploy System

```bash
./scripts/deploy.sh
```

What it does:
- ✅ Deploys RBAC configurations
- ✅ Deploys GreedyLB scheduler
- ✅ Deploys RefineLB scheduler
- ✅ Deploys Pattern Detector
- ✅ Waits for all components to be ready

**Time**: ~3 minutes

#### Step 4: Validate Installation

```bash
./scripts/validate.sh
```

What it does:
- ✅ Runs 13 automated tests
- ✅ Verifies cluster health
- ✅ Tests scheduler functionality
- ✅ Checks logs for errors

**Time**: ~2 minutes

---

## Manual Install (Advanced)

### 1. Install kubectl

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
kubectl version --client
```

### 2. Install Minikube

```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
minikube version
```

### 3. Start Minikube Cluster

```bash
minikube start \
  --nodes=3 \
  --cpus=4 \
  --memory=6144 \
  --driver=docker \
  --kubernetes-version=stable
```

### 4. Build Docker Images

```bash
# Use Minikube's Docker daemon
eval $(minikube docker-env)

# Build GreedyLB
docker build -t greedylb-scheduler:latest ./schedulers/greedylb/

# Build RefineLB
docker build -t refinelb-scheduler:latest ./schedulers/refinelb/

# Build Pattern Detector
docker build -t pattern-detector:latest ./monitoring/
```

### 5. Deploy RBAC

```bash
kubectl apply -f k8s-manifests/rbac/scheduler-rbac.yaml
kubectl apply -f k8s-manifests/rbac/monitor-rbac.yaml
```

### 6. Deploy Schedulers

```bash
kubectl apply -f k8s-manifests/schedulers/greedylb-deployment.yaml
kubectl apply -f k8s-manifests/schedulers/refinelb-deployment.yaml
```

### 7. Deploy Pattern Detector

```bash
kubectl apply -f k8s-manifests/monitoring/monitor-deployment.yaml
```

### 8. Verify Deployment

```bash
kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'
```

---

## Post-Installation

### 1. Verify System is Running

```bash
make status
# or
kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'
```

Expected output:
```
NAME                                  READY   STATUS    RESTARTS   AGE
greedylb-scheduler-xxx                1/1     Running   0          2m
pattern-detector-xxx                  1/1     Running   0          2m
refinelb-scheduler-xxx                1/1     Running   0          2m
```

### 2. Run First Test

```bash
make test-continuous
# or
python3 workload-generators/continuous_workload.py
```

### 3. Monitor the System

Open 2 terminals:

**Terminal 1**: Watch pattern detector
```bash
kubectl logs -n kube-system -l app=pattern-detector -f
```

**Terminal 2**: Watch pods
```bash
watch kubectl get pods -o wide
```

---

## Configuration

### Adjust Pattern Detection Thresholds

Edit `monitoring/pattern_detector.py`:

```python
MONITOR_INTERVAL = 10      # Seconds between checks
HISTORY_WINDOW = 6         # Number of samples to keep
STABLE_THRESHOLD = 10      # Percentage for stable pattern
LINEAR_THRESHOLD = 30      # Percentage for exponential pattern
```

Then rebuild and redeploy:
```bash
./scripts/build-images.sh
kubectl rollout restart deployment/pattern-detector -n kube-system
```

### Adjust Resource Limits

Edit deployment files in `k8s-manifests/schedulers/`:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

Apply changes:
```bash
kubectl apply -f k8s-manifests/schedulers/
```

---

## Troubleshooting Installation

### Issue: Minikube Won't Start

```bash
# Delete and recreate
minikube delete
minikube start --nodes=3 --cpus=4 --memory=6144 --driver=docker

# Check Docker is running
docker ps

# Check WSL2 integration in Docker Desktop
```

### Issue: Docker Images Not Found

```bash
# Make sure you're using Minikube's Docker
eval $(minikube docker-env)

# Rebuild images
./scripts/build-images.sh

# Verify images exist
docker images | grep -E "greedylb|refinelb|pattern"
```

### Issue: Pods Stuck in Pending

```bash
# Check scheduler logs
kubectl logs -n kube-system -l app=greedylb-scheduler

# Check pod events
kubectl describe pod <pod-name>

# Check node resources
kubectl top nodes
```

### Issue: Permission Denied

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Or use make
make setup
```

### Issue: Python Dependencies Missing

```bash
# Install Python packages
pip3 install -r monitoring/requirements.txt
pip3 install -r workload-generators/requirements.txt
```

---

## Uninstall

### Remove All Components (Keep Cluster)

```bash
make clean
# or
./scripts/cleanup.sh
```

### Remove Everything (Including Cluster)

```bash
./scripts/cleanup.sh
# Select 'y' when asked about cluster deletion

# Or manually:
minikube delete
```

---

## Upgrading

### Update Code

```bash
cd ~/cnn-cep
git pull origin main
```

### Rebuild and Redeploy

```bash
# Rebuild images
./scripts/build-images.sh

# Restart deployments
kubectl rollout restart deployment/greedylb-scheduler -n kube-system
kubectl rollout restart deployment/refinelb-scheduler -n kube-system
kubectl rollout restart deployment/pattern-detector -n kube-system

# Verify
kubectl rollout status deployment/greedylb-scheduler -n kube-system
```

---

## Next Steps

After successful installation:

1. **Read the Quick Start**: `docs/QUICKSTART.md`
2. **Run Tests**: `make test` or `./scripts/test.sh`
3. **Check Architecture**: `docs/ARCHITECTURE.md`
4. **Review Testing Guide**: `docs/TESTING.md`

---

## Support

- **Documentation**: Check `README.md` and `docs/` directory
- **Validation**: Run `./scripts/validate.sh`
- **Logs**: Use `make logs-monitor`, `make logs-greedylb`, `make logs-refinelb`

---

**Installation Support**: v1.0.0
**Last Updated**: November 24, 2025
