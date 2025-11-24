#!/bin/bash
###############################################################################
# Deployment Script for Adaptive Dynamic Load Balancing
# Deploys schedulers, monitoring system, and RBAC configurations
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Change to project root
cd "$(dirname "$0")/.."

print_header "Deploying Adaptive Load Balancing System"

# 1. Deploy RBAC configurations
print_header "Step 1: Deploying RBAC Configurations"

print_info "Creating scheduler service account and permissions..."
kubectl apply -f k8s-manifests/rbac/scheduler-rbac.yaml
print_success "Scheduler RBAC configured"

print_info "Creating monitor service account and permissions..."
kubectl apply -f k8s-manifests/rbac/monitor-rbac.yaml
print_success "Monitor RBAC configured"

sleep 2

# 2. Deploy Schedulers
print_header "Step 2: Deploying Custom Schedulers"

print_info "Deploying GreedyLB Scheduler..."
kubectl apply -f k8s-manifests/schedulers/greedylb-deployment.yaml
print_success "GreedyLB Scheduler deployed"

print_info "Deploying RefineLB Scheduler..."
kubectl apply -f k8s-manifests/schedulers/refinelb-deployment.yaml
print_success "RefineLB Scheduler deployed"

print_info "Waiting for schedulers to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/greedylb-scheduler -n kube-system
kubectl wait --for=condition=available --timeout=60s deployment/refinelb-scheduler -n kube-system
print_success "Schedulers are ready"

# 3. Deploy Monitoring System
print_header "Step 3: Deploying Pattern Detector"

print_info "Deploying Pattern Detector..."
kubectl apply -f k8s-manifests/monitoring/monitor-deployment.yaml
print_success "Pattern Detector deployed"

print_info "Waiting for pattern detector to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/pattern-detector -n kube-system
print_success "Pattern Detector is ready"

# 4. Verify deployment
print_header "Step 4: Verifying Deployment"

echo ""
print_info "Checking pod status in kube-system namespace:"
kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'

echo ""
print_info "Checking deployments:"
kubectl get deployments -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'

echo ""
print_success "Deployment completed successfully!"
echo ""
print_header "System Status"
echo ""
print_info "View GreedyLB logs:"
echo "  kubectl logs -n kube-system -l app=greedylb-scheduler -f"
echo ""
print_info "View RefineLB logs:"
echo "  kubectl logs -n kube-system -l app=refinelb-scheduler -f"
echo ""
print_info "View Pattern Detector logs:"
echo "  kubectl logs -n kube-system -l app=pattern-detector -f"
echo ""
print_info "Test the system:"
echo "  ./scripts/test.sh"
echo ""
