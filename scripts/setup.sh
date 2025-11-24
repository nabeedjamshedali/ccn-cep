#!/bin/bash
###############################################################################
# Setup Script for Adaptive Dynamic Load Balancing in Kubernetes
# This script sets up the complete environment on Windows/WSL2
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup
print_header "Adaptive Load Balancing Setup"

# 1. Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker Desktop for Windows with WSL2 integration."
    exit 1
fi
print_success "Docker found: $(docker --version)"

if ! command_exists kubectl; then
    print_error "kubectl is not installed."
    print_info "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
    print_success "kubectl installed"
fi
print_success "kubectl found: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"

if ! command_exists minikube; then
    print_error "Minikube is not installed."
    print_info "Installing Minikube..."
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64
    print_success "Minikube installed"
fi
print_success "Minikube found: $(minikube version --short)"

if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.11+"
    exit 1
fi
print_success "Python found: $(python3 --version)"

# 2. Check if Minikube is running
print_header "Setting up Minikube Cluster"

if minikube status >/dev/null 2>&1; then
    print_info "Minikube is already running"
    read -p "Do you want to delete and recreate the cluster? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deleting existing Minikube cluster..."
        minikube delete
        print_success "Cluster deleted"
    fi
fi

if ! minikube status >/dev/null 2>&1; then
    print_info "Starting Minikube cluster..."
    print_info "Configuration: 3 nodes, 4 CPUs, 6GB RAM"

    minikube start \
        --nodes=3 \
        --cpus=4 \
        --memory=6144 \
        --driver=docker \
        --kubernetes-version=stable

    print_success "Minikube cluster started"
else
    print_success "Using existing Minikube cluster"
fi

# 3. Verify cluster
print_info "Verifying cluster..."
kubectl get nodes
print_success "Cluster is ready with $(kubectl get nodes --no-headers | wc -l) nodes"

# 4. Build Docker images
print_header "Building Docker Images"

cd "$(dirname "$0")/.."

print_info "Building GreedyLB Scheduler image..."
eval $(minikube docker-env)
docker build -t greedylb-scheduler:latest ./schedulers/greedylb/
print_success "GreedyLB Scheduler image built"

print_info "Building RefineLB Scheduler image..."
docker build -t refinelb-scheduler:latest ./schedulers/refinelb/
print_success "RefineLB Scheduler image built"

print_info "Building Pattern Detector image..."
docker build -t pattern-detector:latest ./monitoring/
print_success "Pattern Detector image built"

# Verify images
print_info "Docker images:"
docker images | grep -E "greedylb-scheduler|refinelb-scheduler|pattern-detector"

# 5. Create namespace if needed
print_header "Configuring Kubernetes Resources"

print_info "Ensuring kube-system namespace exists..."
kubectl get namespace kube-system >/dev/null 2>&1 && print_success "kube-system namespace ready"

print_success "Setup completed successfully!"
echo ""
print_info "Next steps:"
echo "  1. Run './scripts/deploy.sh' to deploy the system"
echo "  2. Run './scripts/test.sh' to test the adaptive load balancing"
echo "  3. Check logs with: kubectl logs -n kube-system -l app=pattern-detector -f"
