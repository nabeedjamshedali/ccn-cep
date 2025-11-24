#!/bin/bash
###############################################################################
# Cleanup Script
# Removes all deployed resources
###############################################################################

set -e

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

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

cd "$(dirname "$0")/.."

print_header "Cleanup Adaptive Load Balancing System"

echo ""
read -p "This will remove all deployed components. Continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Cleanup cancelled"
    exit 0
fi

print_info "Removing pattern detector..."
kubectl delete -f k8s-manifests/monitoring/monitor-deployment.yaml --ignore-not-found=true

print_info "Removing schedulers..."
kubectl delete -f k8s-manifests/schedulers/refinelb-deployment.yaml --ignore-not-found=true
kubectl delete -f k8s-manifests/schedulers/greedylb-deployment.yaml --ignore-not-found=true

print_info "Removing RBAC configurations..."
kubectl delete -f k8s-manifests/rbac/monitor-rbac.yaml --ignore-not-found=true
kubectl delete -f k8s-manifests/rbac/scheduler-rbac.yaml --ignore-not-found=true

print_info "Removing test workloads..."
kubectl delete deployment linear-workload --ignore-not-found=true
kubectl delete deployment exponential-workload --ignore-not-found=true
kubectl delete deployment continuous-workload --ignore-not-found=true
kubectl delete deployment test-workload --ignore-not-found=true
kubectl delete service test-workload --ignore-not-found=true

print_success "Cleanup completed!"

echo ""
read -p "Do you want to delete the Minikube cluster? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Deleting Minikube cluster..."
    minikube delete
    print_success "Minikube cluster deleted"
fi

print_info "Cleanup finished"
