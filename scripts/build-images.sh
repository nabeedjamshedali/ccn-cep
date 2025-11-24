#!/bin/bash
###############################################################################
# Docker Image Build Script
# Builds all Docker images for the system
###############################################################################

set -e

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

print_header "Building Docker Images"

# Set Docker environment to use Minikube's Docker daemon
print_info "Configuring Docker environment for Minikube..."
eval $(minikube docker-env)
print_success "Docker environment configured"

# Build GreedyLB Scheduler
print_info "Building GreedyLB Scheduler image..."
docker build -t greedylb-scheduler:latest \
    -f schedulers/greedylb/Dockerfile \
    schedulers/greedylb/
print_success "GreedyLB Scheduler image built"

# Build RefineLB Scheduler
print_info "Building RefineLB Scheduler image..."
docker build -t refinelb-scheduler:latest \
    -f schedulers/refinelb/Dockerfile \
    schedulers/refinelb/
print_success "RefineLB Scheduler image built"

# Build Pattern Detector
print_info "Building Pattern Detector image..."
docker build -t pattern-detector:latest \
    -f monitoring/Dockerfile \
    monitoring/
print_success "Pattern Detector image built"

# Verify images
print_header "Verifying Built Images"
docker images | grep -E "IMAGE|greedylb-scheduler|refinelb-scheduler|pattern-detector"

print_success "All images built successfully!"
