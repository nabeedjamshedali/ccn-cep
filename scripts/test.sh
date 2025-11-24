#!/bin/bash
###############################################################################
# Test Script for Adaptive Dynamic Load Balancing
# Provides interactive menu to test different workload patterns
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_menu() {
    echo -e "${CYAN}$1${NC}"
}

# Change to project root
cd "$(dirname "$0")/.."

print_header "Adaptive Load Balancing Test Suite"

# Install Python dependencies if needed
if ! python3 -c "import kubernetes" 2>/dev/null; then
    print_info "Installing Python dependencies..."
    pip3 install -r workload-generators/requirements.txt
    print_success "Dependencies installed"
fi

# Main menu
while true; do
    echo ""
    print_menu "═══════════════════════════════════════"
    print_menu "  TEST MENU"
    print_menu "═══════════════════════════════════════"
    echo -e "${CYAN}1)${NC} Test Linear Workload (1→2→3→4→5 pods)"
    echo -e "${CYAN}2)${NC} Test Exponential Workload (5→10→20→40 pods)"
    echo -e "${CYAN}3)${NC} Test Continuous Workload (Linear→Exponential transition)"
    echo -e "${CYAN}4)${NC} Deploy Test Workload (manual testing)"
    echo -e "${CYAN}5)${NC} Monitor System Status"
    echo -e "${CYAN}6)${NC} View Scheduler Logs"
    echo -e "${CYAN}7)${NC} View Pattern Detector Logs"
    echo -e "${CYAN}8)${NC} Clean Up Test Workloads"
    echo -e "${CYAN}9)${NC} Exit"
    print_menu "═══════════════════════════════════════"
    echo -n "Select option: "
    read -r choice

    case $choice in
        1)
            print_header "Running Linear Workload Test"
            print_info "Expected behavior: GreedyLB scheduler should be used"
            print_info "Growth pattern: 1 → 2 → 3 → 4 → 5 pods (linear)"
            echo ""
            read -p "Press Enter to start test..."
            python3 workload-generators/linear_workload.py
            ;;
        2)
            print_header "Running Exponential Workload Test"
            print_info "Expected behavior: RefineLB scheduler should be activated"
            print_info "Growth pattern: 5 → 10 → 20 → 40 pods (exponential)"
            echo ""
            read -p "Press Enter to start test..."
            python3 workload-generators/exponential_workload.py
            ;;
        3)
            print_header "Running Continuous Workload Test"
            print_info "Expected behavior: Automatic scheduler switching"
            print_info "Phase 1: Linear growth (GreedyLB)"
            print_info "Phase 2: Stable period"
            print_info "Phase 3: Exponential burst (switch to RefineLB)"
            print_info "Phase 4: Final stable period"
            echo ""
            print_info "This test takes approximately 5 minutes"
            read -p "Press Enter to start test..."
            python3 workload-generators/continuous_workload.py
            ;;
        4)
            print_header "Deploying Test Workload"
            kubectl apply -f k8s-manifests/workloads/test-workload.yaml
            print_success "Test workload deployed"
            echo ""
            print_info "Check status with: kubectl get pods"
            ;;
        5)
            print_header "System Status"
            echo ""
            print_info "Scheduler Pods:"
            kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'
            echo ""
            print_info "Workload Pods:"
            kubectl get pods -n default
            echo ""
            print_info "Pod Distribution Across Nodes:"
            kubectl get pods -n default -o wide
            ;;
        6)
            print_header "Scheduler Logs"
            echo -e "${CYAN}1)${NC} GreedyLB Scheduler"
            echo -e "${CYAN}2)${NC} RefineLB Scheduler"
            echo -e "${CYAN}3)${NC} Both (split view)"
            echo -n "Select: "
            read -r log_choice
            case $log_choice in
                1)
                    print_info "Showing GreedyLB logs (Ctrl+C to exit)..."
                    kubectl logs -n kube-system -l app=greedylb-scheduler -f --tail=50
                    ;;
                2)
                    print_info "Showing RefineLB logs (Ctrl+C to exit)..."
                    kubectl logs -n kube-system -l app=refinelb-scheduler -f --tail=50
                    ;;
                3)
                    print_info "Install 'kubectl stern' for better log viewing"
                    print_info "Showing recent logs from both schedulers..."
                    kubectl logs -n kube-system -l app=greedylb-scheduler --tail=20
                    echo ""
                    kubectl logs -n kube-system -l app=refinelb-scheduler --tail=20
                    ;;
            esac
            ;;
        7)
            print_header "Pattern Detector Logs"
            print_info "Showing pattern detector logs (Ctrl+C to exit)..."
            kubectl logs -n kube-system -l app=pattern-detector -f --tail=50
            ;;
        8)
            print_header "Cleaning Up Test Workloads"
            print_info "Deleting test workloads..."
            kubectl delete deployment linear-workload --ignore-not-found=true
            kubectl delete deployment exponential-workload --ignore-not-found=true
            kubectl delete deployment continuous-workload --ignore-not-found=true
            kubectl delete deployment test-workload --ignore-not-found=true
            kubectl delete service test-workload --ignore-not-found=true
            print_success "Test workloads cleaned up"
            ;;
        9)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid option. Please try again."
            ;;
    esac
done
