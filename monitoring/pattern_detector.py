#!/usr/bin/env python3
"""
Adaptive Workload Pattern Detector and Scheduler Switcher
Monitors cluster workload patterns and automatically switches between schedulers
"""

import logging
import time
import sys
from datetime import datetime
from collections import deque
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - PatternDetector - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WorkloadPattern:
    """Enumeration of workload patterns"""
    STABLE = "stable"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class SchedulerType:
    """Enumeration of scheduler types"""
    GREEDY_LB = "greedylb-scheduler"
    REFINE_LB = "refinelb-scheduler"


class PatternDetector:
    """
    Detects workload patterns and switches schedulers adaptively

    Pattern Detection Logic:
    - Stable/Linear (< 30% change) → GreedyLB (fast scheduling)
    - Exponential (≥ 30% change) → RefineLB (balanced distribution)
    """

    def __init__(self,
                 monitor_interval=10,
                 history_window=6,
                 stable_threshold=10,
                 linear_threshold=30):
        """
        Initialize the pattern detector

        Args:
            monitor_interval: Seconds between monitoring checks (default: 10s)
            history_window: Number of historical data points to keep (default: 6)
            stable_threshold: Percentage change threshold for stable pattern (default: 10%)
            linear_threshold: Percentage change threshold for exponential pattern (default: 30%)
        """
        self.monitor_interval = monitor_interval
        self.history_window = history_window
        self.stable_threshold = stable_threshold
        self.linear_threshold = linear_threshold

        self.pod_count_history = deque(maxlen=history_window)
        self.current_scheduler = None
        self.current_pattern = None

        self.v1 = None
        self.apps_v1 = None
        self.initialize_k8s_client()

        logger.info(f"PatternDetector initialized:")
        logger.info(f"  Monitor interval: {monitor_interval}s")
        logger.info(f"  History window: {history_window} samples")
        logger.info(f"  Stable threshold: <{stable_threshold}%")
        logger.info(f"  Linear threshold: {stable_threshold}-{linear_threshold}%")
        logger.info(f"  Exponential threshold: ≥{linear_threshold}%")

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
        self.apps_v1 = client.AppsV1Api()

    def get_active_pod_count(self):
        """
        Get count of active (non-system) pods in the cluster
        Excludes kube-system, kube-public, and kube-node-lease namespaces
        """
        try:
            # Get all pods except system namespaces
            pods = self.v1.list_pod_for_all_namespaces(watch=False)

            active_pods = [
                pod for pod in pods.items
                if pod.metadata.namespace not in ['kube-system', 'kube-public', 'kube-node-lease']
                and pod.status.phase in ['Running', 'Pending']
            ]

            count = len(active_pods)
            logger.debug(f"Active pod count: {count}")
            return count

        except ApiException as e:
            logger.error(f"Error fetching pod count: {e}")
            return 0

    def calculate_growth_rate(self):
        """
        Calculate the growth rate based on historical data
        Returns: (growth_rate_percentage, trend_description)
        """
        if len(self.pod_count_history) < 2:
            return 0, "insufficient_data"

        # Get the oldest and newest values
        oldest = self.pod_count_history[0]
        newest = self.pod_count_history[-1]

        # Avoid division by zero
        if oldest == 0:
            if newest > 0:
                return 100, "startup"
            else:
                return 0, "no_pods"

        # Calculate percentage change
        change = ((newest - oldest) / oldest) * 100

        # Calculate average rate of change
        if len(self.pod_count_history) >= 3:
            rates = []
            for i in range(1, len(self.pod_count_history)):
                prev = self.pod_count_history[i-1]
                curr = self.pod_count_history[i]
                if prev > 0:
                    rate = ((curr - prev) / prev) * 100
                    rates.append(rate)

            if rates:
                avg_rate = sum(rates) / len(rates)
                return avg_rate, "calculated"

        return change, "simple"

    def detect_pattern(self, growth_rate):
        """
        Detect workload pattern based on growth rate

        Pattern Classification:
        - Stable: < 10% change
        - Linear: 10% - 30% change
        - Exponential: ≥ 30% change
        """
        abs_rate = abs(growth_rate)

        if abs_rate < self.stable_threshold:
            return WorkloadPattern.STABLE
        elif abs_rate < self.linear_threshold:
            return WorkloadPattern.LINEAR
        else:
            return WorkloadPattern.EXPONENTIAL

    def determine_optimal_scheduler(self, pattern):
        """
        Determine which scheduler is optimal for the detected pattern

        Rules:
        - Stable/Linear → GreedyLB (fast, greedy scheduling)
        - Exponential → RefineLB (balanced, refined scheduling)
        """
        if pattern in [WorkloadPattern.STABLE, WorkloadPattern.LINEAR]:
            return SchedulerType.GREEDY_LB
        else:
            return SchedulerType.REFINE_LB

    def switch_scheduler(self, target_scheduler):
        """
        Switch all deployments to use the target scheduler
        This updates the schedulerName field in deployment specs
        """
        try:
            # Get all deployments in all namespaces (except system namespaces)
            deployments = self.apps_v1.list_deployment_for_all_namespaces(watch=False)

            switched_count = 0

            for deployment in deployments.items:
                namespace = deployment.metadata.namespace
                name = deployment.metadata.name

                # Skip system namespaces
                if namespace in ['kube-system', 'kube-public', 'kube-node-lease']:
                    continue

                # Check current scheduler name
                current_scheduler = deployment.spec.template.spec.scheduler_name

                # Only update if different
                if current_scheduler != target_scheduler:
                    # Update the scheduler name
                    deployment.spec.template.spec.scheduler_name = target_scheduler

                    try:
                        self.apps_v1.patch_namespaced_deployment(
                            name=name,
                            namespace=namespace,
                            body=deployment
                        )
                        logger.info(f"Switched deployment {namespace}/{name}: "
                                  f"{current_scheduler} → {target_scheduler}")
                        switched_count += 1
                    except ApiException as e:
                        logger.error(f"Failed to update deployment {namespace}/{name}: {e}")

            if switched_count > 0:
                logger.info(f"Successfully switched {switched_count} deployments to {target_scheduler}")
            else:
                logger.debug(f"No deployments needed switching (all already using {target_scheduler})")

            return switched_count

        except ApiException as e:
            logger.error(f"Error switching schedulers: {e}")
            return 0

    def generate_monitoring_report(self, pod_count, growth_rate, pattern, scheduler):
        """Generate a formatted monitoring report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = [
            "",
            "=" * 70,
            f"Monitoring Report - {timestamp}",
            "=" * 70,
            f"Current Pod Count:    {pod_count}",
            f"Pod Count History:    {list(self.pod_count_history)}",
            f"Growth Rate:          {growth_rate:+.2f}%",
            f"Detected Pattern:     {pattern.upper()}",
            f"Active Scheduler:     {scheduler}",
            "=" * 70,
            ""
        ]

        return "\n".join(report)

    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("=" * 70)
        logger.info("Starting Adaptive Workload Pattern Detection")
        logger.info("=" * 70)

        iteration = 0

        while True:
            try:
                iteration += 1
                logger.info(f"\n>>> Monitoring Iteration #{iteration}")

                # Get current pod count
                pod_count = self.get_active_pod_count()
                self.pod_count_history.append(pod_count)

                # Need at least 2 data points to detect pattern
                if len(self.pod_count_history) < 2:
                    logger.info(f"Collecting initial data... ({len(self.pod_count_history)}/{self.history_window})")
                    time.sleep(self.monitor_interval)
                    continue

                # Calculate growth rate
                growth_rate, trend = self.calculate_growth_rate()

                # Detect pattern
                pattern = self.detect_pattern(growth_rate)

                # Determine optimal scheduler
                optimal_scheduler = self.determine_optimal_scheduler(pattern)

                # Switch scheduler if needed
                if optimal_scheduler != self.current_scheduler:
                    logger.info(f"Pattern change detected: {self.current_pattern} → {pattern}")
                    logger.info(f"Switching scheduler: {self.current_scheduler} → {optimal_scheduler}")

                    switched = self.switch_scheduler(optimal_scheduler)

                    if switched >= 0:
                        self.current_scheduler = optimal_scheduler
                        self.current_pattern = pattern
                        logger.info(f"✓ Scheduler switch complete")
                else:
                    logger.info(f"Pattern stable: {pattern} - Keeping scheduler: {optimal_scheduler}")

                # Generate and log report
                report = self.generate_monitoring_report(
                    pod_count, growth_rate, pattern, optimal_scheduler
                )
                logger.info(report)

                # Wait before next iteration
                time.sleep(self.monitor_interval)

            except KeyboardInterrupt:
                logger.info("\nMonitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(self.monitor_interval)


def main():
    """Main entry point"""
    # Configuration
    MONITOR_INTERVAL = 10  # seconds
    HISTORY_WINDOW = 6     # samples
    STABLE_THRESHOLD = 10  # percentage
    LINEAR_THRESHOLD = 30  # percentage

    detector = PatternDetector(
        monitor_interval=MONITOR_INTERVAL,
        history_window=HISTORY_WINDOW,
        stable_threshold=STABLE_THRESHOLD,
        linear_threshold=LINEAR_THRESHOLD
    )

    try:
        detector.monitor_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
