#!/usr/bin/env python3
"""
RefineLB Scheduler - Advanced load balancing for exponential workloads
Implements sophisticated scoring with resource balancing and distribution awareness
"""

import logging
import time
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import sys
from collections import defaultdict
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - RefineLB - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class RefineLBScheduler:
    """
    RefineLB implements an advanced, refined scheduling algorithm.
    - Multi-factor scoring system
    - Optimizes for balanced resource distribution
    - Considers pod density and spreading
    - Best for exponential workload patterns
    """

    def __init__(self, scheduler_name="refinelb-scheduler"):
        """Initialize the RefineLB scheduler"""
        self.scheduler_name = scheduler_name
        self.v1 = None
        self.initialize_k8s_client()
        logger.info(f"RefineLB Scheduler initialized: {scheduler_name}")

    def initialize_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            # Try to load in-cluster config first
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            # Fall back to local kubeconfig
            try:
                config.load_kube_config()
                logger.info("Loaded local kubeconfig")
            except config.ConfigException as e:
                logger.error(f"Failed to load Kubernetes configuration: {e}")
                sys.exit(1)

        self.v1 = client.CoreV1Api()

    def get_schedulable_nodes(self):
        """
        Get all schedulable nodes in the cluster
        Returns nodes that are ready and not cordoned
        """
        try:
            nodes = self.v1.list_node(watch=False)
            schedulable_nodes = []

            for node in nodes.items:
                # Check if node is ready
                is_ready = False
                for condition in node.status.conditions:
                    if condition.type == "Ready" and condition.status == "True":
                        is_ready = True
                        break

                # Check if node is schedulable (not cordoned)
                is_schedulable = not node.spec.unschedulable if node.spec.unschedulable is not None else True

                if is_ready and is_schedulable:
                    schedulable_nodes.append(node)

            logger.info(f"Found {len(schedulable_nodes)} schedulable nodes")
            return schedulable_nodes

        except ApiException as e:
            logger.error(f"Error fetching nodes: {e}")
            return []

    def get_node_resource_usage(self, node):
        """Get detailed resource usage for a node"""
        try:
            node_name = node.metadata.name

            # Get node allocatable resources
            allocatable = node.status.allocatable
            cpu_allocatable = self.parse_cpu(allocatable.get('cpu', '0'))
            memory_allocatable = self.parse_memory(allocatable.get('memory', '0'))

            # Get current pod usage on this node
            field_selector = f"spec.nodeName={node_name},status.phase!=Failed,status.phase!=Succeeded"
            pods = self.v1.list_pod_for_all_namespaces(field_selector=field_selector)

            cpu_used = 0
            memory_used = 0
            pod_count = len(pods.items)

            for pod in pods.items:
                if pod.spec.containers:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            cpu_used += self.parse_cpu(container.resources.requests.get('cpu', '0'))
                            memory_used += self.parse_memory(container.resources.requests.get('memory', '0'))

            return {
                'name': node_name,
                'cpu_allocatable': cpu_allocatable,
                'memory_allocatable': memory_allocatable,
                'cpu_used': cpu_used,
                'memory_used': memory_used,
                'cpu_available': cpu_allocatable - cpu_used,
                'memory_available': memory_allocatable - memory_used,
                'pod_count': pod_count,
                'cpu_utilization': (cpu_used / max(cpu_allocatable, 1)) * 100,
                'memory_utilization': (memory_used / max(memory_allocatable, 1)) * 100
            }

        except Exception as e:
            logger.error(f"Error getting resource usage for node {node.metadata.name}: {e}")
            return None

    def calculate_resource_balance_score(self, nodes_usage):
        """
        Calculate how balanced resources are across cluster
        Returns variance - lower is better (more balanced)
        """
        if not nodes_usage:
            return 0

        cpu_utils = [usage['cpu_utilization'] for usage in nodes_usage]
        memory_utils = [usage['memory_utilization'] for usage in nodes_usage]

        # Calculate standard deviation (variance measure)
        cpu_std = self.calculate_std_dev(cpu_utils)
        memory_std = self.calculate_std_dev(memory_utils)

        return (cpu_std + memory_std) / 2

    def calculate_refined_score(self, node, pod_request, all_nodes_usage):
        """
        Advanced multi-factor scoring algorithm
        Factors:
        1. Available resources (40%)
        2. Resource balance after placement (30%)
        3. Pod density/spreading (20%)
        4. Utilization target (10%)
        """
        try:
            usage = self.get_node_resource_usage(node)
            if not usage:
                return 0

            # Factor 1: Available Resources Score (40%)
            # Check if node has enough resources
            cpu_available = usage['cpu_available']
            memory_available = usage['memory_available']

            if cpu_available < pod_request['cpu'] or memory_available < pod_request['memory']:
                return 0  # Cannot schedule here

            # Score based on remaining resources after placement
            cpu_after = cpu_available - pod_request['cpu']
            memory_after = memory_available - pod_request['memory']

            cpu_ratio = cpu_after / max(usage['cpu_allocatable'], 1)
            memory_ratio = memory_after / max(usage['memory_allocatable'], 1)

            resources_score = (cpu_ratio * 0.5 + memory_ratio * 0.5) * 40

            # Factor 2: Balance Score (30%)
            # Prefer nodes that maintain better cluster balance
            current_cpu_util = usage['cpu_utilization']
            current_mem_util = usage['memory_utilization']

            # Calculate what utilization would be after placement
            new_cpu_util = ((usage['cpu_used'] + pod_request['cpu']) /
                           max(usage['cpu_allocatable'], 1)) * 100
            new_mem_util = ((usage['memory_used'] + pod_request['memory']) /
                           max(usage['memory_allocatable'], 1)) * 100

            # Prefer nodes with lower utilization to spread load
            avg_cpu_util = sum(n['cpu_utilization'] for n in all_nodes_usage) / len(all_nodes_usage)
            avg_mem_util = sum(n['memory_utilization'] for n in all_nodes_usage) / len(all_nodes_usage)

            # Score higher if new utilization is closer to average (better balance)
            cpu_balance = 100 - abs(new_cpu_util - avg_cpu_util)
            mem_balance = 100 - abs(new_mem_util - avg_mem_util)

            balance_score = (cpu_balance * 0.5 + mem_balance * 0.5) * 0.3

            # Factor 3: Pod Density Score (20%)
            # Prefer nodes with fewer pods for better spreading
            max_pods = 110  # Kubernetes default
            pod_density = (1 - (usage['pod_count'] / max_pods)) * 20

            # Factor 4: Target Utilization Score (10%)
            # Aim for 60-70% utilization (sweet spot)
            target_util = 65
            cpu_target_score = 100 - abs(new_cpu_util - target_util)
            mem_target_score = 100 - abs(new_mem_util - target_util)
            target_score = (cpu_target_score * 0.5 + mem_target_score * 0.5) * 0.1

            # Total Score
            total_score = resources_score + balance_score + pod_density + target_score

            logger.debug(f"Node {usage['name']}: Total={total_score:.2f} "
                        f"[Res={resources_score:.2f}, Bal={balance_score:.2f}, "
                        f"Den={pod_density:.2f}, Tgt={target_score:.2f}] "
                        f"CPU={usage['cpu_utilization']:.1f}%->{new_cpu_util:.1f}% "
                        f"MEM={usage['memory_utilization']:.1f}%->{new_mem_util:.1f}% "
                        f"Pods={usage['pod_count']}")

            return total_score

        except Exception as e:
            logger.error(f"Error calculating refined score for node {node.metadata.name}: {e}")
            return 0

    def select_best_node(self, nodes, pod):
        """
        Advanced selection using multi-factor scoring
        """
        if not nodes:
            return None

        # Extract pod resource requests
        pod_request = self.get_pod_resource_requests(pod)

        # Get resource usage for all nodes
        all_nodes_usage = []
        for node in nodes:
            usage = self.get_node_resource_usage(node)
            if usage:
                all_nodes_usage.append(usage)

        if not all_nodes_usage:
            return None

        # Calculate scores for all nodes
        scored_nodes = []
        for node in nodes:
            score = self.calculate_refined_score(node, pod_request, all_nodes_usage)
            if score > 0:
                scored_nodes.append((node, score))

        if not scored_nodes:
            logger.warning("No suitable nodes found for pod")
            return None

        # Sort by score (descending)
        scored_nodes.sort(key=lambda x: x[1], reverse=True)

        best_node, best_score = scored_nodes[0]
        logger.info(f"Selected node: {best_node.metadata.name} with refined score {best_score:.2f}")

        return best_node

    def get_pod_resource_requests(self, pod):
        """Extract CPU and memory requests from pod spec"""
        cpu_request = 0
        memory_request = 0

        if pod.spec.containers:
            for container in pod.spec.containers:
                if container.resources and container.resources.requests:
                    cpu_request += self.parse_cpu(container.resources.requests.get('cpu', '100m'))
                    memory_request += self.parse_memory(container.resources.requests.get('memory', '128Mi'))

        # Default requests if not specified
        if cpu_request == 0:
            cpu_request = 100  # 100m
        if memory_request == 0:
            memory_request = 128 * 1024 * 1024  # 128Mi

        return {
            'cpu': cpu_request,
            'memory': memory_request
        }

    def bind_pod_to_node(self, pod_name, namespace, node_name):
        """Bind a pod to a specific node"""
        try:
            target = client.V1ObjectReference(
                api_version="v1",
                kind="Node",
                name=node_name
            )

            binding = client.V1Binding(
                api_version="v1",
                kind="Binding",
                metadata=client.V1ObjectMeta(
                    name=pod_name,
                    namespace=namespace
                ),
                target=target
            )

            self.v1.create_namespaced_binding(
                namespace=namespace,
                body=binding,
                _preload_content=False
            )

            logger.info(f"Successfully bound pod {namespace}/{pod_name} to node {node_name}")
            return True

        except ApiException as e:
            logger.error(f"Failed to bind pod {namespace}/{pod_name} to node {node_name}: {e}")
            return False

    def schedule_pod(self, pod):
        """Main scheduling logic for a single pod"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace

        logger.info(f"Scheduling pod: {namespace}/{pod_name}")

        # Get schedulable nodes
        nodes = self.get_schedulable_nodes()
        if not nodes:
            logger.error("No schedulable nodes available")
            return False

        # Select best node using refined algorithm
        selected_node = self.select_best_node(nodes, pod)
        if not selected_node:
            logger.error("Failed to select a node")
            return False

        # Bind pod to selected node
        return self.bind_pod_to_node(pod_name, namespace, selected_node.metadata.name)

    def watch_for_pods(self):
        """Watch for unscheduled pods assigned to this scheduler"""
        logger.info(f"Starting to watch for pods with schedulerName={self.scheduler_name}")

        w = watch.Watch()

        while True:
            try:
                for event in w.stream(
                    self.v1.list_pod_for_all_namespaces,
                    field_selector=f"spec.schedulerName={self.scheduler_name},spec.nodeName="
                ):
                    if event['type'] == 'ADDED' or event['type'] == 'MODIFIED':
                        pod = event['object']

                        # Check if pod is pending and not yet scheduled
                        if (pod.status.phase == 'Pending' and
                            pod.spec.node_name is None):

                            logger.info(f"Detected unscheduled pod: {pod.metadata.namespace}/{pod.metadata.name}")

                            # Schedule the pod
                            self.schedule_pod(pod)

            except ApiException as e:
                if e.status == 410:
                    # Resource version too old, restart watch
                    logger.warning("Watch expired, restarting...")
                    continue
                else:
                    logger.error(f"API exception in watch loop: {e}")
                    time.sleep(5)

            except Exception as e:
                logger.error(f"Unexpected error in watch loop: {e}")
                time.sleep(5)

    @staticmethod
    def calculate_std_dev(values):
        """Calculate standard deviation"""
        if not values:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def parse_cpu(cpu_string):
        """Parse Kubernetes CPU string to millicores"""
        if not cpu_string:
            return 0

        cpu_string = str(cpu_string)

        if cpu_string.endswith('m'):
            return float(cpu_string[:-1])
        elif cpu_string.endswith('n'):
            return float(cpu_string[:-1]) / 1_000_000
        else:
            return float(cpu_string) * 1000

    @staticmethod
    def parse_memory(memory_string):
        """Parse Kubernetes memory string to bytes"""
        if not memory_string:
            return 0

        memory_string = str(memory_string)

        units = {
            'Ki': 1024,
            'Mi': 1024**2,
            'Gi': 1024**3,
            'Ti': 1024**4,
            'K': 1000,
            'M': 1000**2,
            'G': 1000**3,
            'T': 1000**4
        }

        for unit, multiplier in units.items():
            if memory_string.endswith(unit):
                return float(memory_string[:-len(unit)]) * multiplier

        return float(memory_string)


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Starting RefineLB Scheduler")
    logger.info("Optimized for exponential workload patterns")
    logger.info("Advanced multi-factor load balancing")
    logger.info("=" * 60)

    scheduler = RefineLBScheduler(scheduler_name="refinelb-scheduler")

    try:
        scheduler.watch_for_pods()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
