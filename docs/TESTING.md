# Testing Guide

Complete guide for testing the Adaptive Dynamic Load Balancing system.

---

## Test Suite Overview

This project includes comprehensive testing capabilities:

1. **Automated Validation** - System health checks
2. **Workload Generators** - Pattern simulation
3. **Manual Testing** - Interactive exploration
4. **Performance Testing** - Load and stress tests

---

## Quick Test

Run the complete validation suite:

```bash
make validate
# or
./scripts/validate.sh
```

This runs 13 automated tests covering:
- ✅ Cluster health
- ✅ Component deployment
- ✅ RBAC configuration
- ✅ Docker images
- ✅ Functional scheduling
- ✅ Log monitoring

---

## Test Scenarios

### 1. Linear Workload Test

**Purpose**: Verify GreedyLB scheduler handles linear growth efficiently

**Command**:
```bash
make test-linear
# or
python3 workload-generators/linear_workload.py
```

**Expected Results**:
- ✅ Pattern detector identifies LINEAR pattern
- ✅ System uses/stays with GreedyLB scheduler
- ✅ Pods scale: 1 → 2 → 3 → 4 → 5
- ✅ Scheduling time: 50-100ms per pod
- ✅ Even distribution across nodes

**Monitoring**:
```bash
# Terminal 1: Watch pattern detector
kubectl logs -n kube-system -l app=pattern-detector -f

# Terminal 2: Watch pods
watch kubectl get pods -o wide

# Terminal 3: Watch GreedyLB logs
kubectl logs -n kube-system -l app=greedylb-scheduler -f
```

**Success Criteria**:
```
✓ All 5 pods reach Running state
✓ Pattern detector shows: "Detected Pattern: LINEAR"
✓ Scheduler: greedylb-scheduler
✓ No pods stuck in Pending
✓ No scheduler errors in logs
```

---

### 2. Exponential Workload Test

**Purpose**: Verify RefineLB handles exponential bursts with balanced distribution

**Command**:
```bash
make test-exponential
# or
python3 workload-generators/exponential_workload.py
```

**Expected Results**:
- ✅ Pattern detector identifies EXPONENTIAL pattern
- ✅ System switches to RefineLB scheduler
- ✅ Pods scale: 5 → 10 → 20 → 40
- ✅ Better resource balance across nodes
- ✅ No single node overloaded

**Monitoring**:
```bash
# Terminal 1: Pattern detector
kubectl logs -n kube-system -l app=pattern-detector -f

# Terminal 2: Pod distribution
watch 'kubectl get pods -o wide | awk "{print \$7}" | sort | uniq -c'

# Terminal 3: RefineLB logs
kubectl logs -n kube-system -l app=refinelb-scheduler -f
```

**Success Criteria**:
```
✓ All 40 pods reach Running state
✓ Pattern detector shows: "Detected Pattern: EXPONENTIAL"
✓ Scheduler: refinelb-scheduler
✓ Pods distributed across all 3 nodes
✓ No node has >50% of total pods
✓ Balanced CPU/memory utilization
```

---

### 3. Continuous Workload Test ⭐ (Recommended)

**Purpose**: Demonstrate automatic scheduler switching during pattern transitions

**Command**:
```bash
make test-continuous
# or
python3 workload-generators/continuous_workload.py
```

**Test Phases**:

**Phase 1: Linear Growth (0-2 minutes)**
- Pods: 1 → 2 → 3 → 4 → 5
- Expected: GreedyLB scheduler
- Pattern: LINEAR

**Phase 2: Stable Period (2-3 minutes)**
- Pods: 5 (constant)
- Expected: GreedyLB scheduler
- Pattern: STABLE

**Phase 3: Exponential Burst (3-5 minutes)**
- Pods: 5 → 10 → 20 → 40
- Expected: **AUTO-SWITCH to RefineLB**
- Pattern: EXPONENTIAL

**Phase 4: Final Stable (5-6 minutes)**
- Pods: 40 (constant)
- Expected: RefineLB scheduler
- Pattern: STABLE

**Monitoring Setup**:
```bash
# Terminal 1: Pattern detector (MOST IMPORTANT)
kubectl logs -n kube-system -l app=pattern-detector -f

# Terminal 2: Pod count tracking
watch 'kubectl get pods | grep continuous | wc -l'

# Terminal 3: Scheduler activity
# Watch both schedulers
kubectl logs -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler)' -f

# Terminal 4: Pod distribution
watch 'kubectl get pods -o wide'
```

**Success Criteria**:
```
✓ Phase 1: GreedyLB active, linear growth
✓ Phase 2: Stable pattern detected
✓ Phase 3: Pattern changes to EXPONENTIAL
✓ Phase 3: Automatic switch to RefineLB
✓ Phase 3: New pods scheduled by RefineLB
✓ Phase 4: All 40 pods Running
✓ Final: Balanced distribution across nodes
✓ No errors in any logs
```

**Look for this in logs**:
```
Pattern change detected: linear → exponential
Switching scheduler: greedylb-scheduler → refinelb-scheduler
Successfully switched deployments to refinelb-scheduler
```

---

## Manual Testing

### Test Custom Workload

Create a deployment with specific scheduler:

```bash
# Test with GreedyLB
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: manual-test-greedy
spec:
  replicas: 5
  selector:
    matchLabels:
      app: manual-test
  template:
    metadata:
      labels:
        app: manual-test
    spec:
      schedulerName: greedylb-scheduler
      containers:
      - name: nginx
        image: nginx:alpine
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
EOF

# Watch scheduling
kubectl get pods -w
```

### Test Scheduler Switching

```bash
# 1. Deploy with GreedyLB
kubectl apply -f k8s-manifests/workloads/test-workload.yaml

# 2. Verify scheduler
kubectl get deployment test-workload -o jsonpath='{.spec.template.spec.schedulerName}'

# 3. Manually switch to RefineLB
kubectl patch deployment test-workload -p '{"spec":{"template":{"spec":{"schedulerName":"refinelb-scheduler"}}}}'

# 4. Scale to trigger rescheduling
kubectl scale deployment test-workload --replicas=10

# 5. Verify new pods use RefineLB
kubectl get pods -l app=test-workload -o wide
```

---

## Performance Testing

### Scheduling Latency Test

Measure how fast each scheduler places pods:

```bash
# Test GreedyLB
time kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: latency-test-greedy
spec:
  replicas: 20
  selector:
    matchLabels:
      app: latency-test
  template:
    metadata:
      labels:
        app: latency-test
    spec:
      schedulerName: greedylb-scheduler
      containers:
      - name: pause
        image: k8s.gcr.io/pause:3.9
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
EOF

# Wait for all pods to be scheduled
kubectl wait --for=condition=ready pod -l app=latency-test --timeout=60s

# Clean up
kubectl delete deployment latency-test-greedy

# Repeat with RefineLB
# ... (same but schedulerName: refinelb-scheduler)
```

### Load Distribution Test

Verify balanced pod distribution:

```bash
# Create heavy workload
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: load-test
spec:
  replicas: 30
  selector:
    matchLabels:
      app: load-test
  template:
    metadata:
      labels:
        app: load-test
    spec:
      schedulerName: refinelb-scheduler
      containers:
      - name: nginx
        image: nginx:alpine
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
EOF

# Wait for pods to be scheduled
sleep 30

# Check distribution
echo "Pod distribution across nodes:"
kubectl get pods -l app=load-test -o wide | awk '{print $7}' | sort | uniq -c

# Check node utilization
kubectl top nodes

# Expected: Roughly equal distribution (±3 pods per node)

# Clean up
kubectl delete deployment load-test
```

---

## Stress Testing

### Burst Scheduling Test

Test scheduler behavior under rapid scaling:

```bash
# Create deployment
kubectl create deployment stress-test --image=nginx:alpine --replicas=1

# Set scheduler
kubectl patch deployment stress-test -p '{"spec":{"template":{"spec":{"schedulerName":"refinelb-scheduler"}}}}'

# Rapid scaling
for i in 5 10 20 40 60 80; do
  kubectl scale deployment stress-test --replicas=$i
  sleep 10
done

# Monitor pattern detector response
kubectl logs -n kube-system -l app=pattern-detector --tail=50

# Clean up
kubectl delete deployment stress-test
```

---

## Debugging Tests

### Test Scheduler Failure Recovery

```bash
# 1. Kill GreedyLB scheduler
kubectl delete pod -n kube-system -l app=greedylb-scheduler

# 2. Immediately create pods
kubectl create deployment recovery-test --image=nginx:alpine --replicas=5
kubectl patch deployment recovery-test -p '{"spec":{"template":{"spec":{"schedulerName":"greedylb-scheduler"}}}}'

# 3. Watch recovery
kubectl get pods -w

# Expected: Pods wait in Pending until scheduler restarts (~30s)
# Then all pods should be scheduled

# Clean up
kubectl delete deployment recovery-test
```

### Test Pattern Detector Failure

```bash
# 1. Scale down pattern detector
kubectl scale deployment pattern-detector -n kube-system --replicas=0

# 2. Create workload with growth
python3 workload-generators/exponential_workload.py &

# Expected: Schedulers continue working, but no auto-switching

# 3. Restore pattern detector
kubectl scale deployment pattern-detector -n kube-system --replicas=1

# 4. Verify it catches up
kubectl logs -n kube-system -l app=pattern-detector -f

# Clean up
kubectl delete deployment exponential-workload
```

---

## Test Cleanup

### Clean Up Test Workloads

```bash
make clean-workloads
# or
kubectl delete deployment linear-workload exponential-workload continuous-workload test-workload --ignore-not-found=true
```

### Full System Reset

```bash
make clean
# or
./scripts/cleanup.sh
```

---

## Continuous Integration Tests

### Automated Test Suite

```bash
#!/bin/bash
# ci-test.sh

set -e

echo "Running CI test suite..."

# 1. Validate setup
./scripts/validate.sh

# 2. Test GreedyLB
echo "Testing GreedyLB..."
python3 workload-generators/linear_workload.py
kubectl wait --for=condition=ready pod -l app=linear-workload --timeout=120s
kubectl delete deployment linear-workload

# 3. Test RefineLB
echo "Testing RefineLB..."
python3 workload-generators/exponential_workload.py
kubectl wait --for=condition=ready pod -l app=exponential-workload --timeout=180s
kubectl delete deployment exponential-workload

# 4. Verify no errors
ERRORS=$(kubectl logs -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)' --tail=100 | grep -i error | wc -l)

if [ "$ERRORS" -gt 0 ]; then
    echo "Found $ERRORS errors in logs"
    exit 1
fi

echo "All CI tests passed!"
```

---

## Expected Test Results

### Validation Test Output

```
========================================
System Validation
========================================

TEST: Minikube cluster is running
✓ PASS: Minikube is running

TEST: kubectl can connect to cluster
✓ PASS: kubectl connectivity OK

TEST: Cluster has multiple nodes
✓ PASS: Found 3 nodes

...

========================================
Validation Summary
========================================

Total Tests:  13
Passed:       13
Failed:       0

========================================
✓ ALL TESTS PASSED
System is fully operational!
========================================
```

---

## Troubleshooting Test Failures

### Pods Not Scheduling

```bash
# Check scheduler status
kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler)'

# Check scheduler logs for errors
kubectl logs -n kube-system -l app=greedylb-scheduler --tail=50

# Check pod events
kubectl describe pod <pending-pod-name>
```

### Pattern Not Detected

```bash
# Check monitor logs
kubectl logs -n kube-system -l app=pattern-detector -f

# Verify pod count is changing
watch kubectl get pods

# Check RBAC permissions
kubectl auth can-i update deployments --as=system:serviceaccount:kube-system:pattern-detector
```

### Scheduler Not Switching

```bash
# Check if deployments exist
kubectl get deployments

# Check deployment schedulerName
kubectl get deployment <name> -o jsonpath='{.spec.template.spec.schedulerName}'

# Manually trigger update
kubectl rollout restart deployment <name>
```

---

## Test Metrics

Track these metrics during testing:

- **Scheduling Latency**: Time from pod creation to binding
- **Pod Distribution**: Standard deviation across nodes
- **Pattern Detection Time**: Time to detect and switch
- **Resource Utilization**: CPU/memory per node
- **Error Rate**: Errors per 100 pods scheduled

---

**Document Version**: 1.0
**Last Updated**: November 24, 2025
