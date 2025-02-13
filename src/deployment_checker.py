from kubernetes import client, config
import boto3
import base64
import tempfile
import json
from datetime import datetime, timedelta, timezone
from load_config import load_config
from kubernetes.client import ApiClient
import os


class DeploymentChecker:
    def __init__(self, config_data):
        """Initialize Kubernetes client with EKS authentication."""
        self.config_data = config_data
        self.cluster_name = config_data.get("KUBERNETES_CLUSTER_NAME")
        self.namespace = config_data.get("KUBERNETES_NAMESPACE", "default")
        self.time_offset_days = config_data.get("TIME_OFFSET_DAYS", 7)
        self.region = config_data.get("AWS_REGION", "ap-south-1")

        # Get Kubernetes API Client for the EKS Cluster
        # self.kube_client = self.get_kube_client(self.cluster_name)
        # self.apps_v1 = client.AppsV1Api(self.kube_client)

    def get_kube_client(self, cluster_name):
        """Authenticate with EKS and return Kubernetes API client."""
        print("🔄 Fetching Kubernetes cluster authentication details...")
        eks = boto3.client('eks', region_name=self.region)
        cluster_info = eks.describe_cluster(name=cluster_name)

        endpoint = cluster_info['cluster']['endpoint']
        ca_data = cluster_info['cluster']['certificateAuthority']['data']

        # Decode CA certificate
        decoded_ca_data = base64.b64decode(ca_data)

        # Save CA certificate to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".crt") as ca_cert_file:
            ca_cert_file.write(decoded_ca_data)
            ca_cert_file_path = ca_cert_file.name

        # Get the authentication token
        token = self.get_bearer_token(cluster_name)

        # Configure Kubernetes client
        configuration = client.Configuration()
        configuration.host = endpoint
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = ca_cert_file_path
        configuration.api_key['authorization'] = f'Bearer {token}'
        client.Configuration.set_default(configuration)

        print(f"✅ Connected to Kubernetes cluster: {cluster_name}")
        return ApiClient(configuration)

    def get_bearer_token(self, cluster_name):
        """Generate AWS EKS authentication token for Kubernetes."""
        command = f"aws eks get-token --cluster-name {cluster_name}"
        response = json.loads(os.popen(command).read())

        if "status" in response and "token" in response["status"]:
            return response["status"]["token"]
        else:
            raise Exception("❌ Failed to fetch authentication token for EKS")

    def get_recent_active_deployments(self):
        """Fetch ACTIVE deployments created between `TIME_OFFSET_DAYS` and now."""
        now = datetime.now(timezone.utc)
        past_time = now - timedelta(days=self.time_offset_days)

        kube_client = self.get_kube_client(self.cluster_name)
        apps_v1 = client.AppsV1Api(kube_client)

        print(f"\n🔎 Checking active deployments between {past_time} and {now}")


        deployments = apps_v1.list_namespaced_deployment(namespace=self.namespace)
        active_deployments = []

        for deploy in deployments.items:
            deploy_time = deploy.metadata.creation_timestamp.astimezone(timezone.utc)

            # Check if deployment is active (running pods)
            available_replicas = deploy.status.available_replicas
            if available_replicas and available_replicas > 0 and past_time <= deploy_time <= now:
                active_deployments.append({
                    "name": deploy.metadata.name,
                    "created_at": deploy_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "available_replicas": available_replicas
                })

        if not active_deployments:
            print("\n✅ No active deployments found in the given time range.")
        else:
            print(f"\n🚀 Found {len(active_deployments)} active deployments in the last {self.time_offset_days} days!")

        return active_deployments
    
