#!/usr/bin/env python3
"""
Linear Workload Generator
Simulates linear growth pattern: 1 → 2 → 3 → 4 → 5 pods
"""

import logging
import time
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - LinearWorkload - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LinearWorkloadGenerator:
    """Generates linear workload pattern"""

    def __init__(self, namespace="default", deployment_name="linear-workload"):
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
                        match_labels={"app": "linear-workload"}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "linear-workload"}
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

    def run_linear_pattern(self, start=1, end=5, interval=30):
        """
        Generate linear workload pattern

        Args:
            start: Starting number of pods (default: 1)
            end: Ending number of pods (default: 5)
            interval: Seconds between scaling steps (default: 30)
        """
        logger.info("=" * 60)
        logger.info("Starting Linear Workload Pattern Generator")
        logger.info(f"Pattern: {start} → {end} pods (increment by 1)")
        logger.info(f"Interval: {interval} seconds")
        logger.info("=" * 60)

        # Create deployment
        if not self.create_deployment():
            logger.error("Failed to create deployment")
            return

        # Scale linearly
        for replicas in range(start, end + 1):
            logger.info(f"\n>>> Step {replicas}/{end}: Scaling to {replicas} pod(s)")
            self.scale_deployment(replicas)

            if replicas < end:
                logger.info(f"Waiting {interval} seconds before next step...")
                time.sleep(interval)

        logger.info("\n" + "=" * 60)
        logger.info("Linear workload pattern complete!")
        logger.info(f"Final state: {end} pods")
        logger.info("=" * 60)

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
    generator = LinearWorkloadGenerator(
        namespace="default",
        deployment_name="linear-workload"
    )

    try:
        generator.run_linear_pattern(start=1, end=5, interval=30)
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Optional: cleanup
        # generator.cleanup()
        pass


if __name__ == "__main__":
    main()
