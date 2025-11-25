#!/bin/bash
###############################################################################
# Docker Image Build Script
# Builds all Docker images for the system
# Uses minikube image build for multi-node cluster compatibility
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

# Build GreedyLB Scheduler using minikube image build (multi-node compatible)
print_info "Building GreedyLB Scheduler image..."
minikube image build -t greedylb-scheduler:latest schedulers/greedylb/
print_success "GreedyLB Scheduler image built"

# Build RefineLB Scheduler
print_info "Building RefineLB Scheduler image..."
minikube image build -t refinelb-scheduler:latest schedulers/refinelb/
print_success "RefineLB Scheduler image built"

# Build Pattern Detector
print_info "Building Pattern Detector image..."
minikube image build -t pattern-detector:latest monitoring/
print_success "Pattern Detector image built"

# Verify images
print_header "Verifying Built Images"
minikube image ls | grep -E "greedylb|refinelb|pattern" || true

print_success "All images built successfully!"
