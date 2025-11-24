.PHONY: help setup deploy test validate clean build status logs

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

help: ## Show this help message
	@echo "$(BLUE)================================$(NC)"
	@echo "$(BLUE)Adaptive Load Balancing - Make$(NC)"
	@echo "$(BLUE)================================$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

setup: ## Initial setup (install tools, create cluster, build images)
	@echo "$(YELLOW)Running initial setup...$(NC)"
	@./scripts/setup.sh

deploy: ## Deploy all components to Kubernetes
	@echo "$(YELLOW)Deploying system...$(NC)"
	@./scripts/deploy.sh

build: ## Build all Docker images
	@echo "$(YELLOW)Building Docker images...$(NC)"
	@./scripts/build-images.sh

test: ## Run interactive test menu
	@echo "$(YELLOW)Starting test suite...$(NC)"
	@./scripts/test.sh

validate: ## Validate system is working correctly
	@echo "$(YELLOW)Running validation tests...$(NC)"
	@./scripts/validate.sh

status: ## Show status of all components
	@echo "$(BLUE)================================$(NC)"
	@echo "$(BLUE)System Status$(NC)"
	@echo "$(BLUE)================================$(NC)"
	@echo ""
	@echo "$(GREEN)Cluster Nodes:$(NC)"
	@kubectl get nodes
	@echo ""
	@echo "$(GREEN)Schedulers and Monitor:$(NC)"
	@kubectl get pods -n kube-system -l 'app in (greedylb-scheduler,refinelb-scheduler,pattern-detector)'
	@echo ""
	@echo "$(GREEN)Workload Pods:$(NC)"
	@kubectl get pods -n default
	@echo ""

logs-greedylb: ## View GreedyLB scheduler logs
	@echo "$(YELLOW)GreedyLB Scheduler Logs (Ctrl+C to exit)$(NC)"
	@kubectl logs -n kube-system -l app=greedylb-scheduler -f

logs-refinelb: ## View RefineLB scheduler logs
	@echo "$(YELLOW)RefineLB Scheduler Logs (Ctrl+C to exit)$(NC)"
	@kubectl logs -n kube-system -l app=refinelb-scheduler -f

logs-monitor: ## View pattern detector logs
	@echo "$(YELLOW)Pattern Detector Logs (Ctrl+C to exit)$(NC)"
	@kubectl logs -n kube-system -l app=pattern-detector -f

test-linear: ## Run linear workload test
	@echo "$(YELLOW)Running linear workload test...$(NC)"
	@python3 workload-generators/linear_workload.py

test-exponential: ## Run exponential workload test
	@echo "$(YELLOW)Running exponential workload test...$(NC)"
	@python3 workload-generators/exponential_workload.py

test-continuous: ## Run continuous workload test
	@echo "$(YELLOW)Running continuous workload test...$(NC)"
	@python3 workload-generators/continuous_workload.py

clean-workloads: ## Delete all test workloads
	@echo "$(YELLOW)Cleaning up test workloads...$(NC)"
	@kubectl delete deployment linear-workload --ignore-not-found=true
	@kubectl delete deployment exponential-workload --ignore-not-found=true
	@kubectl delete deployment continuous-workload --ignore-not-found=true
	@kubectl delete deployment test-workload --ignore-not-found=true
	@kubectl delete service test-workload --ignore-not-found=true
	@echo "$(GREEN)Workloads cleaned up$(NC)"

clean: ## Remove all deployed components
	@echo "$(YELLOW)Cleaning up system...$(NC)"
	@./scripts/cleanup.sh

cluster-start: ## Start Minikube cluster
	@echo "$(YELLOW)Starting Minikube cluster...$(NC)"
	@minikube start --nodes=3 --cpus=4 --memory=6144 --driver=docker

cluster-stop: ## Stop Minikube cluster
	@echo "$(YELLOW)Stopping Minikube cluster...$(NC)"
	@minikube stop

cluster-delete: ## Delete Minikube cluster
	@echo "$(YELLOW)Deleting Minikube cluster...$(NC)"
	@minikube delete

cluster-info: ## Show cluster information
	@echo "$(BLUE)================================$(NC)"
	@echo "$(BLUE)Cluster Information$(NC)"
	@echo "$(BLUE)================================$(NC)"
	@kubectl cluster-info
	@echo ""
	@echo "$(GREEN)Minikube Status:$(NC)"
	@minikube status

all: setup deploy validate ## Complete setup, deploy, and validate
	@echo "$(GREEN)System is ready!$(NC)"
