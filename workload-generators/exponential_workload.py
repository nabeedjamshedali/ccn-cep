#!/usr/bin/env python3
"""
Exponential Workload Generator
Simulates exponential growth pattern: 5 → 10 → 20 → 40 pods
"""

import logging
import time
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ExponentialWorkload - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExponentialWorkloadGenerator:
    """Generates exponential workload pattern"""

    def __init__(self, namespace="default", deployment_name="exponential-workload"):
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
                    replicas=5,
                    selector=client.V1LabelSelector(
                        match_labels={"app": "exponential-workload"}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "exponential-workload"}
                        ),
                        spec=client.V1PodSpec(
                            scheduler_name="refinelb-scheduler",  # Use RefineLB for exponential
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

    def run_exponential_pattern(self, initial=5, multiplier=2, steps=4, interval=30):
        """
        Generate exponential workload pattern

        Args:
            initial: Initial number of pods (default: 5)
            multiplier: Growth multiplier (default: 2x)
            steps: Number of scaling steps (default: 4)
            interval: Seconds between scaling steps (default: 30)
        """
        logger.info("=" * 60)
        logger.info("Starting Exponential Workload Pattern Generator")
        logger.info(f"Pattern: {initial} → {initial * multiplier} → {initial * multiplier**2} → ... pods")
        logger.info(f"Multiplier: {multiplier}x")
        logger.info(f"Steps: {steps}")
        logger.info(f"Interval: {interval} seconds")
        logger.info("=" * 60)

        # Create deployment
        if not self.create_deployment():
            logger.error("Failed to create deployment")
            return

        # Scale exponentially
        for step in range(steps):
            replicas = int(initial * (multiplier ** step))
            logger.info(f"\n>>> Step {step + 1}/{steps}: Scaling to {replicas} pod(s)")
            self.scale_deployment(replicas)

            if step < steps - 1:
                logger.info(f"Waiting {interval} seconds before next step...")
                time.sleep(interval)

        final_replicas = int(initial * (multiplier ** (steps - 1)))
        logger.info("\n" + "=" * 60)
        logger.info("Exponential workload pattern complete!")
        logger.info(f"Final state: {final_replicas} pods")
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
    generator = ExponentialWorkloadGenerator(
        namespace="default",
        deployment_name="exponential-workload"
    )

    try:
        generator.run_exponential_pattern(initial=5, multiplier=2, steps=4, interval=30)
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
