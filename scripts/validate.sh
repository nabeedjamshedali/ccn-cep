#!/bin/bash
###############################################################################
# Validation Script
# Validates the entire system setup and functionality
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_test() {
    echo -e "${YELLOW}TEST: $1${NC}"
    ((TOTAL_TESTS++))
}

print_pass() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    ((PASSED_TESTS++))
}

print_fail() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    ((FAILED_TESTS++))
}

print_info() {
    echo -e "${YELLOW}  ➜ $1${NC}"
}

# Start validation
print_header "System Validation"

# Test 1: Check Minikube
print_test "Minikube cluster is running"
if minikube status | grep -q "Running"; then
    print_pass "Minikube is running"
else
    print_fail "Minikube is not running"
fi

# Test 2: Check kubectl connectivity
print_test "kubectl can connect to cluster"
if kubectl cluster-info >/dev/null 2>&1; then
    print_pass "kubectl connectivity OK"
else
    print_fail "kubectl cannot connect"
fi

# Test 3: Check nodes
print_test "Cluster has multiple nodes"
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -ge 3 ]; then
    print_pass "Found $NODE_COUNT nodes"
else
    print_fail "Expected 3+ nodes, found $NODE_COUNT"
fi

# Test 4: Check GreedyLB Scheduler
print_test "GreedyLB scheduler is deployed"
if kubectl get deployment greedylb-scheduler -n kube-system >/dev/null 2>&1; then
    print_pass "GreedyLB deployment exists"

    print_test "GreedyLB scheduler is running"
    READY=$(kubectl get deployment greedylb-scheduler -n kube-system -o jsonpath='{.status.availableReplicas}')
    if [ "$READY" == "1" ]; then
        print_pass "GreedyLB is running (1/1 ready)"
    else
        print_fail "GreedyLB not ready ($READY/1)"
    fi
else
    print_fail "GreedyLB deployment not found"
    ((FAILED_TESTS++))
fi

# Test 5: Check RefineLB Scheduler
print_test "RefineLB scheduler is deployed"
if kubectl get deployment refinelb-scheduler -n kube-system >/dev/null 2>&1; then
    print_pass "RefineLB deployment exists"

    print_test "RefineLB scheduler is running"
    READY=$(kubectl get deployment refinelb-scheduler -n kube-system -o jsonpath='{.status.availableReplicas}')
    if [ "$READY" == "1" ]; then
        print_pass "RefineLB is running (1/1 ready)"
    else
        print_fail "RefineLB not ready ($READY/1)"
    fi
else
    print_fail "RefineLB deployment not found"
    ((FAILED_TESTS++))
fi

# Test 6: Check Pattern Detector
print_test "Pattern detector is deployed"
if kubectl get deployment pattern-detector -n kube-system >/dev/null 2>&1; then
    print_pass "Pattern detector deployment exists"

    print_test "Pattern detector is running"
    READY=$(kubectl get deployment pattern-detector -n kube-system -o jsonpath='{.status.availableReplicas}')
    if [ "$READY" == "1" ]; then
        print_pass "Pattern detector is running (1/1 ready)"
    else
        print_fail "Pattern detector not ready ($READY/1)"
    fi
else
    print_fail "Pattern detector deployment not found"
    ((FAILED_TESTS++))
fi

# Test 7: Check RBAC - Scheduler
print_test "Scheduler RBAC is configured"
if kubectl get serviceaccount custom-scheduler -n kube-system >/dev/null 2>&1; then
    print_pass "Scheduler service account exists"
else
    print_fail "Scheduler service account not found"
fi

if kubectl get clusterrole custom-scheduler >/dev/null 2>&1; then
    print_pass "Scheduler cluster role exists"
else
    print_fail "Scheduler cluster role not found"
fi

# Test 8: Check RBAC - Monitor
print_test "Monitor RBAC is configured"
if kubectl get serviceaccount pattern-detector -n kube-system >/dev/null 2>&1; then
    print_pass "Monitor service account exists"
else
    print_fail "Monitor service account not found"
fi

if kubectl get clusterrole pattern-detector >/dev/null 2>&1; then
    print_pass "Monitor cluster role exists"
else
    print_fail "Monitor cluster role not found"
fi

# Test 9: Check Docker images
print_test "Docker images are available"
eval $(minikube docker-env)

if docker images | grep -q "greedylb-scheduler"; then
    print_pass "GreedyLB image found"
else
    print_fail "GreedyLB image not found"
fi

if docker images | grep -q "refinelb-scheduler"; then
    print_pass "RefineLB image found"
else
    print_fail "RefineLB image not found"
fi

if docker images | grep -q "pattern-detector"; then
    print_pass "Pattern detector image found"
else
    print_fail "Pattern detector image not found"
fi

# Test 10: Functional test - Create test pod with GreedyLB
print_test "Functional test: GreedyLB can schedule pods"
cat <<EOF | kubectl apply -f - >/dev/null 2>&1
apiVersion: v1
kind: Pod
metadata:
  name: test-greedylb-validation
  namespace: default
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

sleep 5

if kubectl get pod test-greedylb-validation -o jsonpath='{.spec.nodeName}' 2>/dev/null | grep -q "."; then
    print_pass "GreedyLB successfully scheduled test pod"
    NODE=$(kubectl get pod test-greedylb-validation -o jsonpath='{.spec.nodeName}')
    print_info "Pod scheduled to node: $NODE"
else
    print_fail "GreedyLB failed to schedule test pod"
fi

# Cleanup test pod
kubectl delete pod test-greedylb-validation --ignore-not-found=true >/dev/null 2>&1

# Test 11: Functional test - Create test pod with RefineLB
print_test "Functional test: RefineLB can schedule pods"
cat <<EOF | kubectl apply -f - >/dev/null 2>&1
apiVersion: v1
kind: Pod
metadata:
  name: test-refinelb-validation
  namespace: default
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

sleep 5

if kubectl get pod test-refinelb-validation -o jsonpath='{.spec.nodeName}' 2>/dev/null | grep -q "."; then
    print_pass "RefineLB successfully scheduled test pod"
    NODE=$(kubectl get pod test-refinelb-validation -o jsonpath='{.spec.nodeName}')
    print_info "Pod scheduled to node: $NODE"
else
    print_fail "RefineLB failed to schedule test pod"
fi

# Cleanup test pod
kubectl delete pod test-refinelb-validation --ignore-not-found=true >/dev/null 2>&1

# Test 12: Check scheduler logs for errors
print_test "Schedulers are logging correctly"

GREEDYLB_ERRORS=$(kubectl logs -n kube-system -l app=greedylb-scheduler --tail=50 2>/dev/null | grep -i error | wc -l || echo 0)
REFINELB_ERRORS=$(kubectl logs -n kube-system -l app=refinelb-scheduler --tail=50 2>/dev/null | grep -i error | wc -l || echo 0)

if [ "$GREEDYLB_ERRORS" -eq 0 ] && [ "$REFINELB_ERRORS" -eq 0 ]; then
    print_pass "No errors in scheduler logs"
else
    print_fail "Found errors in logs (GreedyLB: $GREEDYLB_ERRORS, RefineLB: $REFINELB_ERRORS)"
fi

# Test 13: Check pattern detector logs
print_test "Pattern detector is monitoring"

MONITOR_LOGS=$(kubectl logs -n kube-system -l app=pattern-detector --tail=20 2>/dev/null || echo "")
if echo "$MONITOR_LOGS" | grep -q "Monitoring"; then
    print_pass "Pattern detector is actively monitoring"
else
    print_fail "Pattern detector may not be working correctly"
fi

# Summary
print_header "Validation Summary"
echo ""
echo -e "Total Tests:  ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"
echo ""

if [ "$FAILED_TESTS" -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}System is fully operational!${NC}"
    echo -e "${GREEN}========================================${NC}"
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo -e "${RED}Please review the failures above${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
