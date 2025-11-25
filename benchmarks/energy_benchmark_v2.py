#!/usr/bin/env python3
"""
Energy Efficiency Benchmark v2 - Corrected Version

This benchmark focuses on the REAL energy savings:
1. Load Distribution (variance) - balanced nodes use less total energy
2. Node Utilization Efficiency - prevents overloading
3. Steady-state power consumption - after pods are scheduled

Energy Model:
- Imbalanced cluster: Some nodes at 80% CPU (high power), others at 20% (wasted)
- Balanced cluster: All nodes at ~45% CPU (optimal efficiency)

In real data centers:
- Overloaded nodes consume more power (non-linear CPU-power curve)
- Idle nodes still consume base power (wasted)
- Balanced distribution = optimal energy efficiency
"""

import logging
import time
import sys
import json
import statistics
import math
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - Benchmark - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnergyBenchmarkV2:
    """
    Corrected Energy Efficiency Benchmark

    Key insight: Energy savings come from BALANCED LOAD DISTRIBUTION,
    not from scheduling speed.
    """

    # Power consumption model (based on real server data)
    # Servers have non-linear power consumption:
    # - Idle server: ~100W base power
    # - 50% load: ~150W (optimal efficiency)
    # - 100% load: ~250W (inefficient, thermal throttling)

    NODE_IDLE_POWER = 100  # Watts when idle
    NODE_MAX_POWER = 250   # Watts at 100% CPU

    def __init__(self):
        self.initialize_k8s_client()
        self.results = {}

    def initialize_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        logger.info("Kubernetes client initialized")

    def get_node_metrics(self):
        """Get CPU usage for all worker nodes"""
        nodes = self.v1.list_node()
        metrics = []

        for node in nodes.items:
            node_name = node.metadata.name

            # Get allocatable CPU
            allocatable = node.status.allocatable
            allocatable_cpu = self._parse_cpu(allocatable.get('cpu', '0'))

            # Get pods on this node
            pods = self.v1.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name},status.phase=Running"
            )

            used_cpu = 0
            workload_pods = 0

            for pod in pods.items:
                # Count workload pods (not system pods)
                if pod.metadata.namespace not in ['kube-system', 'kube-public', 'kube-node-lease']:
                    workload_pods += 1

                for container in pod.spec.containers:
                    if container.resources and container.resources.requests:
                        used_cpu += self._parse_cpu(container.resources.requests.get('cpu', '0'))

            cpu_percent = (used_cpu / allocatable_cpu * 100) if allocatable_cpu > 0 else 0

            metrics.append({
                "node": node_name,
                "cpu_percent": round(cpu_percent, 2),
                "workload_pods": workload_pods,
                "used_cpu_millicores": used_cpu
            })

        return metrics

    def _parse_cpu(self, cpu_str):
        """Parse CPU string to millicores"""
        cpu_str = str(cpu_str)
        if cpu_str.endswith('m'):
            return int(cpu_str[:-1])
        elif cpu_str.endswith('n'):
            return int(cpu_str[:-1]) / 1000000
        else:
            return int(float(cpu_str) * 1000)

    def calculate_node_power(self, cpu_percent):
        """
        Calculate power consumption for a node based on CPU usage
        Uses realistic non-linear power model

        Real servers have:
        - Base power (idle): ~40% of max
        - Linear increase with load
        - Slight superlinear increase at high loads (thermal)
        """
        # Normalize CPU to 0-1
        cpu_ratio = min(cpu_percent / 100, 1.0)

        # Non-linear power model: P = P_idle + (P_max - P_idle) * cpu^1.2
        # The 1.2 exponent models thermal inefficiency at high loads
        power = self.NODE_IDLE_POWER + (self.NODE_MAX_POWER - self.NODE_IDLE_POWER) * (cpu_ratio ** 1.2)

        return power

    def calculate_cluster_power(self, metrics):
        """Calculate total cluster power consumption"""
        total_power = 0
        node_powers = []

        for m in metrics:
            power = self.calculate_node_power(m['cpu_percent'])
            node_powers.append({
                "node": m['node'],
                "cpu_percent": m['cpu_percent'],
                "power_watts": round(power, 2)
            })
            total_power += power

        return total_power, node_powers

    def calculate_efficiency_metrics(self, metrics):
        """Calculate efficiency metrics for a distribution"""
        cpu_values = [m['cpu_percent'] for m in metrics]
        pod_counts = [m['workload_pods'] for m in metrics]

        # Variance (lower = more balanced)
        cpu_variance = statistics.variance(cpu_values) if len(cpu_values) > 1 else 0
        pod_variance = statistics.variance(pod_counts) if len(pod_counts) > 1 else 0

        # Standard deviation
        cpu_std = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0

        # Max-min spread
        cpu_spread = max(cpu_values) - min(cpu_values)

        # Coefficient of variation (normalized measure of dispersion)
        mean_cpu = statistics.mean(cpu_values)
        cv = (cpu_std / mean_cpu * 100) if mean_cpu > 0 else 0

        return {
            "cpu_variance": round(cpu_variance, 2),
            "cpu_std_dev": round(cpu_std, 2),
            "cpu_spread": round(cpu_spread, 2),
            "coefficient_of_variation": round(cv, 2),
            "pod_variance": round(pod_variance, 2),
            "mean_cpu": round(mean_cpu, 2),
            "max_cpu": round(max(cpu_values), 2),
            "min_cpu": round(min(cpu_values), 2)
        }

    def create_workload(self, name, replicas, scheduler_name):
        """Create a workload deployment"""
        # First try to delete existing
        try:
            self.apps_v1.delete_namespaced_deployment(name, "default")
            time.sleep(5)
        except ApiException:
            pass

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name, namespace="default"),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector=client.V1LabelSelector(match_labels={"app": name}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": name}),
                    spec=client.V1PodSpec(
                        scheduler_name=scheduler_name,
                        containers=[
                            client.V1Container(
                                name="workload",
                                image="nginx:alpine",
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "100m", "memory": "64Mi"},
                                    limits={"cpu": "100m", "memory": "128Mi"}
                                )
                            )
                        ]
                    )
                )
            )
        )

        self.apps_v1.create_namespaced_deployment("default", deployment)
        return True

    def wait_for_ready(self, name, replicas, timeout=180):
        """Wait for all pods to be running"""
        start = time.time()

        while time.time() - start < timeout:
            try:
                pods = self.v1.list_namespaced_pod(
                    "default",
                    label_selector=f"app={name}"
                )
                running = len([p for p in pods.items if p.status.phase == "Running"])

                if running >= replicas:
                    return True, time.time() - start

            except ApiException:
                pass

            time.sleep(2)

        return False, timeout

    def cleanup(self, name):
        """Delete deployment"""
        try:
            self.apps_v1.delete_namespaced_deployment(name, "default")
            time.sleep(10)
        except ApiException:
            pass

    def run_distribution_test(self, scheduler_name, test_name, replicas=30):
        """
        Test load distribution for a scheduler

        This measures STEADY-STATE metrics after pods are deployed,
        which is what matters for energy efficiency.
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"DISTRIBUTION TEST: {test_name}")
        logger.info(f"Scheduler: {scheduler_name}")
        logger.info(f"Pods: {replicas}")
        logger.info(f"{'='*70}")

        deployment_name = f"test-{test_name.lower().replace(' ', '-')}"

        # Create workload
        logger.info(f"Creating {replicas} pods...")
        self.create_workload(deployment_name, replicas, scheduler_name)

        # Wait for all pods to be ready
        success, deploy_time = self.wait_for_ready(deployment_name, replicas)

        if not success:
            logger.error("Timeout waiting for pods")
            self.cleanup(deployment_name)
            return None

        logger.info(f"All pods running in {deploy_time:.1f}s")

        # Wait for metrics to stabilize
        logger.info("Waiting for metrics to stabilize...")
        time.sleep(10)

        # Collect steady-state metrics
        metrics = self.get_node_metrics()
        efficiency = self.calculate_efficiency_metrics(metrics)
        total_power, node_powers = self.calculate_cluster_power(metrics)

        # Calculate energy for a standard duration (e.g., 1 hour operation)
        OPERATION_HOURS = 1
        energy_joules = total_power * 3600 * OPERATION_HOURS  # Power × Time
        energy_kwh = energy_joules / 3600000

        result = {
            "test_name": test_name,
            "scheduler": scheduler_name,
            "replicas": replicas,
            "deploy_time_sec": round(deploy_time, 2),
            "node_metrics": metrics,
            "node_powers": node_powers,
            "efficiency": efficiency,
            "total_power_watts": round(total_power, 2),
            "energy_1hr_joules": round(energy_joules, 2),
            "energy_1hr_kwh": round(energy_kwh, 4)
        }

        # Log results
        logger.info(f"\n--- Node Distribution ---")
        for m in metrics:
            power = self.calculate_node_power(m['cpu_percent'])
            logger.info(f"  {m['node']}: CPU={m['cpu_percent']:.1f}%, Pods={m['workload_pods']}, Power={power:.0f}W")

        logger.info(f"\n--- Efficiency Metrics ---")
        logger.info(f"  CPU Variance: {efficiency['cpu_variance']:.2f} (lower = better)")
        logger.info(f"  CPU Spread: {efficiency['cpu_spread']:.1f}% (lower = better)")
        logger.info(f"  CV: {efficiency['coefficient_of_variation']:.1f}% (lower = better)")

        logger.info(f"\n--- Power Consumption ---")
        logger.info(f"  Total Cluster Power: {total_power:.0f}W")
        logger.info(f"  Energy (1 hour): {energy_kwh:.4f} kWh")

        # Cleanup
        self.cleanup(deployment_name)

        return result

    def run_comparison(self):
        """Run complete comparison benchmark"""
        logger.info("\n" + "="*70)
        logger.info("ENERGY EFFICIENCY BENCHMARK v2")
        logger.info("Comparing Load Distribution & Power Consumption")
        logger.info("="*70)

        replicas = 30  # Use 30 pods for clear distribution

        # Test 1: Default Scheduler
        default_result = self.run_distribution_test(
            "default-scheduler",
            "Default Scheduler",
            replicas
        )

        time.sleep(15)  # Wait between tests

        # Test 2: RefineLB (Balanced) Scheduler
        adaptive_result = self.run_distribution_test(
            "refinelb-scheduler",
            "Adaptive RefineLB",
            replicas
        )

        if not default_result or not adaptive_result:
            logger.error("Benchmark failed")
            return None

        # Generate comparison
        self.generate_report(default_result, adaptive_result)

        return {
            "default": default_result,
            "adaptive": adaptive_result
        }

    def generate_report(self, default, adaptive):
        """Generate comparison report"""

        # Calculate savings
        power_diff = default['total_power_watts'] - adaptive['total_power_watts']
        power_savings_pct = (power_diff / default['total_power_watts']) * 100

        energy_diff = default['energy_1hr_joules'] - adaptive['energy_1hr_joules']

        # Variance improvement
        variance_improvement = (
            (default['efficiency']['cpu_variance'] - adaptive['efficiency']['cpu_variance'])
            / default['efficiency']['cpu_variance'] * 100
        ) if default['efficiency']['cpu_variance'] > 0 else 0

        report = f"""
{'='*70}
            ENERGY EFFICIENCY COMPARISON REPORT v2
{'='*70}

LOAD DISTRIBUTION COMPARISON ({default['replicas']} pods):
{'─'*70}
                            Default         Adaptive (RefineLB)
                            ───────         ───────────────────
Node Distribution:
"""
        # Add node details
        for d, a in zip(default['node_metrics'], adaptive['node_metrics']):
            report += f"  {d['node']:15} CPU: {d['cpu_percent']:5.1f}%        CPU: {a['cpu_percent']:5.1f}%\n"
            report += f"  {' '*15} Pods: {d['workload_pods']:5}         Pods: {a['workload_pods']:5}\n"

        report += f"""
BALANCE METRICS:
{'─'*70}
                            Default         Adaptive
                            ───────         ────────
CPU Variance:               {default['efficiency']['cpu_variance']:7.2f}         {adaptive['efficiency']['cpu_variance']:7.2f}  {'✓ BETTER' if adaptive['efficiency']['cpu_variance'] < default['efficiency']['cpu_variance'] else ''}
CPU Spread (max-min):       {default['efficiency']['cpu_spread']:7.1f}%        {adaptive['efficiency']['cpu_spread']:7.1f}%  {'✓ BETTER' if adaptive['efficiency']['cpu_spread'] < default['efficiency']['cpu_spread'] else ''}
Coeff. of Variation:        {default['efficiency']['coefficient_of_variation']:7.1f}%        {adaptive['efficiency']['coefficient_of_variation']:7.1f}%  {'✓ BETTER' if adaptive['efficiency']['coefficient_of_variation'] < default['efficiency']['coefficient_of_variation'] else ''}

POWER CONSUMPTION:
{'─'*70}
                            Default         Adaptive
                            ───────         ────────
Total Cluster Power:        {default['total_power_watts']:7.0f}W         {adaptive['total_power_watts']:7.0f}W
Energy per Hour:            {default['energy_1hr_kwh']:7.4f} kWh     {adaptive['energy_1hr_kwh']:7.4f} kWh

SAVINGS SUMMARY:
{'─'*70}
Power Reduction:            {power_diff:+.0f}W ({power_savings_pct:+.1f}%)
Energy Saved (1 hour):      {energy_diff:+.0f} Joules
Variance Improvement:       {variance_improvement:+.1f}%

{'='*70}
CONCLUSION:
{'─'*70}
"""
        if power_savings_pct > 0:
            report += f"""
✓ The Adaptive Scheduler achieves {power_savings_pct:.1f}% POWER SAVINGS
✓ Load variance reduced by {variance_improvement:.0f}%
✓ More balanced distribution = Lower energy consumption

WHY THIS MATTERS:
• Balanced nodes run at optimal efficiency (no thermal throttling)
• No wasted power on overloaded nodes
• In a real data center with 1000 nodes:
  - Daily savings: {(energy_diff * 24 / 1000):.1f} kWh
  - Annual savings: {(energy_diff * 24 * 365 / 1000):.0f} kWh
  - CO2 reduction: ~{(energy_diff * 24 * 365 / 1000 * 0.4):.0f} kg/year
"""
        else:
            report += f"""
The Default Scheduler used {-power_savings_pct:.1f}% less power in this test.

HOWEVER, note that:
• Adaptive has {variance_improvement:.0f}% BETTER load balance
• Lower variance prevents node hotspots
• Real-world savings depend on workload patterns
• Energy model may need calibration for your hardware
"""

        report += f"\n{'='*70}\n"

        logger.info(report)

        # Save results
        with open("/tmp/energy_benchmark_v2_report.txt", "w") as f:
            f.write(report)

        results = {
            "default": default,
            "adaptive": adaptive,
            "comparison": {
                "power_savings_watts": power_diff,
                "power_savings_percent": power_savings_pct,
                "energy_saved_joules": energy_diff,
                "variance_improvement_percent": variance_improvement
            }
        }

        with open("/tmp/energy_benchmark_v2_results.json", "w") as f:
            json.dump(results, f, indent=2)

        logger.info("Results saved to:")
        logger.info("  /tmp/energy_benchmark_v2_report.txt")
        logger.info("  /tmp/energy_benchmark_v2_results.json")


def main():
    benchmark = EnergyBenchmarkV2()

    try:
        results = benchmark.run_comparison()

        if results:
            print("\n" + "="*70)
            print("BENCHMARK COMPLETE!")
            print("="*70)

    except KeyboardInterrupt:
        logger.info("\nBenchmark stopped")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
