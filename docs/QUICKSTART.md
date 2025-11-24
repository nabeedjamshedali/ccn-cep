# Quick Start Guide

Get the Adaptive Dynamic Load Balancing system running in 5 minutes!

## Prerequisites Check

```bash
# Check Docker
docker --version
# Expected: Docker version 20.x or higher

# Check if Minikube exists (will install if not)
minikube version

# Check Python
python3 --version
# Expected: Python 3.11 or higher
```

## Step-by-Step Setup

### 1. Initial Setup (5 minutes)

```bash
cd ~/cnn-cep
./scripts/setup.sh
```

This will:
- ✅ Install kubectl and Minikube (if needed)
- ✅ Create a 3-node Kubernetes cluster
- ✅ Build all Docker images

**Wait for**: "Setup completed successfully!"

---

### 2. Deploy the System (2 minutes)

```bash
./scripts/deploy.sh
```

This will:
- ✅ Create RBAC permissions
- ✅ Deploy both schedulers
- ✅ Deploy pattern detector

**Wait for**: "Deployment completed successfully!"

---

### 3. Verify Everything is Running

```bash
kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'
```

Expected output (all should be Running):
```
NAME                                  READY   STATUS    RESTARTS   AGE
greedylb-scheduler-xxx                1/1     Running   0          1m
pattern-detector-xxx                  1/1     Running   0          1m
refinelb-scheduler-xxx                1/1     Running   0          1m
```

---

### 4. Run Your First Test (5 minutes)

Open the interactive test menu:
```bash
./scripts/test.sh
```

**Recommended First Test**: Option 3 (Continuous Workload)

This will show the adaptive switching in action:
1. Starts with linear growth → Uses GreedyLB
2. Transitions to exponential → Auto-switches to RefineLB
3. Takes ~5 minutes to complete

---

### 5. Monitor in Real-Time

Open 3 terminal windows:

**Terminal 1** - Pattern Detector:
```bash
kubectl logs -n kube-system -l app=pattern-detector -f
```

**Terminal 2** - Active Pods:
```bash
watch kubectl get pods -o wide
```

**Terminal 3** - Run the test:
```bash
python3 workload-generators/continuous_workload.py
```

Watch the pattern detector automatically switch schedulers as workload patterns change!

---

## What You Should See

### Pattern Detector Output
```
======================================================================
Monitoring Report - 2025-11-24 18:45:30
======================================================================
Current Pod Count:    15
Pod Count History:    [5, 7, 10, 15]
Growth Rate:          +50.00%
Detected Pattern:     EXPONENTIAL
Active Scheduler:     refinelb-scheduler
======================================================================
```

### Scheduler Switching
```
Pattern change detected: linear → exponential
Switching scheduler: greedylb-scheduler → refinelb-scheduler
✓ Scheduler switch complete
```

---

## Common Quick Fixes

### Minikube Not Starting
```bash
minikube delete
minikube start --nodes=3 --cpus=4 --memory=6144 --driver=docker
```

### Images Not Found
```bash
eval $(minikube docker-env)
./scripts/build-images.sh
```

### Pods Stuck Pending
```bash
# Check scheduler logs
kubectl logs -n kube-system -l app=greedylb-scheduler

# Check if pod has correct schedulerName
kubectl get pod <pod-name> -o yaml | grep schedulerName
```

---

## Next Steps

Once everything is working:

1. **Experiment with workload patterns**:
   - Try the linear test (Option 1)
   - Try the exponential test (Option 2)
   - Create your own workload patterns

2. **Adjust thresholds** in `monitoring/pattern_detector.py`:
   ```python
   STABLE_THRESHOLD = 10   # Change to 15
   LINEAR_THRESHOLD = 30   # Change to 40
   ```

3. **View detailed logs**:
   ```bash
   # GreedyLB decisions
   kubectl logs -n kube-system -l app=greedylb-scheduler -f

   # RefineLB decisions
   kubectl logs -n kube-system -l app=refinelb-scheduler -f
   ```

4. **Check resource distribution**:
   ```bash
   kubectl top nodes
   kubectl top pods
   ```

---

## Cleanup

When you're done:
```bash
./scripts/cleanup.sh
```

---

## Need Help?

- **Check the main README**: `README.md`
- **View troubleshooting**: README.md → Troubleshooting section
- **Check logs**: `kubectl logs -n kube-system -l app=<component>`

---

**Estimated Total Time**: 15-20 minutes for complete setup and first test

🎉 **You're all set!** The adaptive load balancing system is now running!
