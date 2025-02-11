import boto3
import os
from datetime import datetime, timedelta, timezone
import json

class RDSMetricsFetcher:
    def __init__(self):
        """Initialize AWS CloudWatch client."""
        self.region = os.getenv("AWS_REGION", "ap-south-1")
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.rds_client = boto3.client('rds', region_name=self.region)
        self.default_period = int(os.getenv("DEFAULT_PERIOD", 60))  # Default to 60 seconds if not specified
        self.cluster_identifier = os.getenv("RDS_CLUSTER_ID", "atlas-customer-cluster-v1-cluster")

    def get_rds_cluster_cpu_utilization(self, metrics_start_time=None, metrics_end_time=None, rds_time_delta=None, period=None):
        print("Fetching RDS cluster CPU utilization metrics")
        """
        Fetch CPU utilization metrics for all instances in the given RDS cluster.
        
        :param cluster_identifier: RDS cluster identifier
        :param metrics_start_time: The start time for fetching the metrics
        :param metrics_end_time: The end time for fetching the metrics (defaults to now if not provided)
        :param rds_time_delta: The range of time to fetch metrics if metrics_start_time is not provided
        :param period: The aggregation period in seconds (default is configurable)
        """
        if metrics_start_time:
            start_time = metrics_start_time
        elif rds_time_delta:
            start_time = datetime.now(timezone.utc) - timedelta(**rds_time_delta)
        else:
            raise ValueError("Either metrics_start_time or rds_time_delta must be provided")
        
        # Set end time to now if not provided
        end_time = metrics_end_time if metrics_end_time else datetime.now(timezone.utc)    
        period = period if period else self.default_period  # period means the aggregation period in seconds

        # Fetch all DB instances in the cluster
        print(f"Fetching RDS cluster instances for {self.cluster_identifier} in region {self.region} time range between {start_time} and {end_time} with period {period} seconds")
        cluster_response = self.rds_client.describe_db_clusters(DBClusterIdentifier=self.cluster_identifier)
        
        if "DBClusters" not in cluster_response or not cluster_response["DBClusters"]:
            raise ValueError(f"No cluster found with identifier: {self.cluster_identifier}")

        cluster_instances = cluster_response["DBClusters"][0]["DBClusterMembers"]

        print(f"Found {len(cluster_instances)} instances in cluster {self.cluster_identifier}")
        
        cluster_metrics = {}
        for instance in cluster_instances:
            instance_id = instance["DBInstanceIdentifier"]
            instance_role = "Writer" if instance["IsClusterWriter"] else "Reader"
            cluster_metrics[instance_id] = {"Role": instance_role}
            
            # Fetch CPU Utilization
            cpu_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average"]
            )
            cluster_metrics[instance_id]['CPUUtilization'] = cpu_response["Datapoints"][-1]["Average"] if cpu_response["Datapoints"] else None

            # Fetch DB Connections
            connections_response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="DatabaseConnections",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average"]
            )
            cluster_metrics[instance_id]['DatabaseConnections'] = connections_response["Datapoints"][-1]["Average"] if connections_response["Datapoints"] else None

        cluster_metrics["ReplicaCount"] = len([instance for instance in cluster_instances if not instance["IsClusterWriter"]])

        print(f"Fetched metrics for {len(cluster_instances)} instances in cluster {self.cluster_identifier}")
        return cluster_metrics


# Call the function
rds_metrics_fetcher = RDSMetricsFetcher()
metrics = rds_metrics_fetcher.get_rds_cluster_cpu_utilization(rds_time_delta={"hours": 1})
print(json.dumps(metrics, indent=2))
