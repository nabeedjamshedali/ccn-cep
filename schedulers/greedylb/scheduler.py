#!/usr/bin/env python3
"""
GreedyLB Scheduler - Fast greedy scheduling for stable/linear workloads
Optimized for quick pod placement with basic resource awareness
"""

import logging
import time
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import random
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - GreedyLB - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class GreedyLBScheduler:
    """
    GreedyLB implements a fast, greedy scheduling algorithm.
    - Selects nodes based on current available resources
    - Prioritizes speed over optimal distribution
    - Best for stable/linear workload patterns
    """

    def __init__(self, scheduler_name="greedylb-scheduler"):
        """Initialize the GreedyLB scheduler"""
        self.scheduler_name = scheduler_name
        self.v1 = None
        self.initialize_k8s_client()
        logger.info(f"GreedyLB Scheduler initialized: {scheduler_name}")

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

    def calculate_node_score(self, node):
        """
        Calculate a simple greedy score for a node
        Higher score = better candidate
        Based on available CPU and memory
        """
        try:
            # Get node allocatable resources
            allocatable = node.status.allocatable
            cpu_allocatable = self.parse_cpu(allocatable.get('cpu', '0'))
            memory_allocatable = self.parse_memory(allocatable.get('memory', '0'))

            # Get current pod usage on this node
            field_selector = f"spec.nodeName={node.metadata.name},status.phase!=Failed,status.phase!=Succeeded"
            pods = self.v1.list_pod_for_all_namespaces(field_selector=field_selector)

            cpu_used = 0
            memory_used = 0

            for pod in pods.items:
                if pod.spec.containers:
                    for container in pod.spec.containers:
                        if container.resources and container.resources.requests:
                            cpu_used += self.parse_cpu(container.resources.requests.get('cpu', '0'))
                            memory_used += self.parse_memory(container.resources.requests.get('memory', '0'))

            # Calculate available resources
            cpu_available = cpu_allocatable - cpu_used
            memory_available = memory_allocatable - memory_used

            # Simple greedy score: weighted sum of available resources
            # Normalize and combine (70% CPU weight, 30% memory weight)
            cpu_score = (cpu_available / max(cpu_allocatable, 1)) * 70
            memory_score = (memory_available / max(memory_allocatable, 1)) * 30

            total_score = cpu_score + memory_score

            logger.debug(f"Node {node.metadata.name}: CPU={cpu_available:.2f}/{cpu_allocatable:.2f}, "
                        f"MEM={memory_available/(1024**3):.2f}/{memory_allocatable/(1024**3):.2f}GB, "
                        f"Score={total_score:.2f}")

            return total_score

        except Exception as e:
            logger.error(f"Error calculating score for node {node.metadata.name}: {e}")
            return 0

    def select_best_node(self, nodes):
        """
        Greedy selection: pick the node with highest score
        Fast O(n) selection
        """
        if not nodes:
            return None

        best_node = None
        best_score = -1

        for node in nodes:
            score = self.calculate_node_score(node)
            if score > best_score:
                best_score = score
                best_node = node

        if best_node:
            logger.info(f"Selected node: {best_node.metadata.name} with score {best_score:.2f}")

        return best_node

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

        # Select best node using greedy algorithm
        selected_node = self.select_best_node(nodes)
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
    logger.info("Starting GreedyLB Scheduler")
    logger.info("Optimized for stable/linear workload patterns")
    logger.info("=" * 60)

    scheduler = GreedyLBScheduler(scheduler_name="greedylb-scheduler")

    try:
        scheduler.watch_for_pods()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
