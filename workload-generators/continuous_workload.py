#!/usr/bin/env python3
"""
Continuous Workload Generator
Simulates transition from linear to exponential growth pattern
Demonstrates adaptive scheduler switching in action
"""

import logging
import time
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ContinuousWorkload - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousWorkloadGenerator:
    """Generates continuous workload with pattern transitions"""

    def __init__(self, namespace="default", deployment_name="continuous-workload"):
        self.namespace = namespace
        self.deployment_name = deployment_name
        self.apps_v1 = None
        self.initialize_k8s_client()

    def initialize_k8s_client(self):
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster configuration")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("Loaded local kubeconfig")
            except config.ConfigException as e:
                logger.error(f"Failed to load Kubernetes configuration: {e}")
                sys.exit(1)

        self.apps_v1 = client.AppsV1Api()

    def create_deployment(self):
        """Create initial deployment"""
        try:
            deployment = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=client.V1ObjectMeta(
                    name=self.deployment_name,
                    namespace=self.namespace
                ),
                spec=client.V1DeploymentSpec(
                    replicas=1,
                    selector=client.V1LabelSelector(
                        match_labels={"app": "continuous-workload"}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "continuous-workload"}
                        ),
                        spec=client.V1PodSpec(
                            scheduler_name="greedylb-scheduler",  # Start with GreedyLB
                            containers=[
                                client.V1Container(
                                    name="workload",
                                    image="nginx:alpine",
                                    resources=client.V1ResourceRequirements(
                                        requests={
                                            "cpu": "100m",
                                            "memory": "128Mi"
                                        },
                                        limits={
                                            "cpu": "200m",
                                            "memory": "256Mi"
                                        }
                                    )
                                )
                            ]
                        )
                    )
                )
            )

            self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment
            )
            logger.info(f"Created deployment: {self.deployment_name}")
            return True

        except ApiException as e:
            if e.status == 409:
                logger.info(f"Deployment {self.deployment_name} already exists")
                return True
            else:
                logger.error(f"Failed to create deployment: {e}")
                return False

    def scale_deployment(self, replicas):
        """Scale deployment to specified number of replicas"""
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace
            )

            deployment.spec.replicas = replicas

            self.apps_v1.patch_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace,
                body=deployment
            )

            logger.info(f"Scaled deployment to {replicas} replicas")
            return True

        except ApiException as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False

    def run_continuous_pattern(self):
        """
        Generate continuous workload with pattern transition

        Phase 1: Linear growth (1 → 2 → 3 → 4 → 5) - GreedyLB expected
        Phase 2: Stable period (maintain 5 pods) - GreedyLB expected
        Phase 3: Exponential burst (5 → 10 → 20 → 40) - RefineLB expected
        Phase 4: Stable period (maintain 40 pods) - Monitor behavior
        """
        logger.info("=" * 70)
        logger.info("Starting Continuous Workload Pattern Generator")
        logger.info("This demonstrates adaptive scheduler switching")
        logger.info("=" * 70)

        # Create deployment
        if not self.create_deployment():
            logger.error("Failed to create deployment")
            return

        # Phase 1: Linear Growth
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 1: Linear Growth (GreedyLB expected)")
        logger.info("=" * 70)

        linear_stages = [1, 2, 3, 4, 5]
        for i, replicas in enumerate(linear_stages, 1):
            logger.info(f"\nLinear Step {i}/{len(linear_stages)}: Scaling to {replicas} pod(s)")
            self.scale_deployment(replicas)
            time.sleep(30)

        # Phase 2: Stable Period
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2: Stable Period (GreedyLB expected)")
        logger.info("=" * 70)
        logger.info("Maintaining 5 pods for 60 seconds...")
        time.sleep(60)

        # Phase 3: Exponential Burst
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 3: Exponential Burst (RefineLB expected)")
        logger.info("=" * 70)

        exponential_stages = [5, 10, 20, 40]
        for i, replicas in enumerate(exponential_stages, 1):
            logger.info(f"\nExponential Step {i}/{len(exponential_stages)}: Scaling to {replicas} pod(s)")
            self.scale_deployment(replicas)
            time.sleep(30)

        # Phase 4: Final Stable Period
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 4: Final Stable Period")
        logger.info("=" * 70)
        logger.info("Maintaining 40 pods for 60 seconds...")
        time.sleep(60)

        logger.info("\n" + "=" * 70)
        logger.info("Continuous workload pattern complete!")
        logger.info("The monitoring system should have switched schedulers automatically")
        logger.info("Check the pattern detector logs to see the transitions")
        logger.info("=" * 70)

    def cleanup(self):
        """Delete the deployment"""
        try:
            self.apps_v1.delete_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace
            )
            logger.info(f"Deleted deployment: {self.deployment_name}")
        except ApiException as e:
            logger.error(f"Failed to delete deployment: {e}")


def main():
    """Main entry point"""
    generator = ContinuousWorkloadGenerator(
        namespace="default",
        deployment_name="continuous-workload"
    )

    try:
        generator.run_continuous_pattern()
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        logger.info("\nWorkload generator finished. Deployment is still running.")
        logger.info("To clean up, run: kubectl delete deployment continuous-workload")


if __name__ == "__main__":
    main()
