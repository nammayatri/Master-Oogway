import boto3
from datetime import datetime, timedelta, timezone
import json
from time_function import TimeFunction

class RDSMetricsFetcher:
    def __init__(self, config):
        """Initialize AWS CloudWatch & RDS client."""
        self.region = config.get("AWS_REGION", "ap-south-1")
        self.cloudwatch = boto3.client("cloudwatch", region_name=self.region)
        self.rds_client = boto3.client("rds", region_name=self.region)
        self.default_period = int(config.get("DEFAULT_PERIOD", 60))  
        self.cluster_identifiers = config.get("RDS_CLUSTER_IDENTIFIERS", ["atlas-customer-cluster-v1-cluster", "atlas-driver-v1-cluster"])
        self.cpu_threshold = config.get("RDS_CPU_DIFFERENCE_THRESHOLD", 10)
        self.conn_threshold = config.get("RDS_CONNECTIONS_DIFFERENCE_THRESHOLD", 100)
        self.replica_threshold = config.get("REPLICA_THRESHOLD", 1)
        self.time_function = TimeFunction()

    def fetch_rds_metrics(self, start_time=None, end_time=None):
        """Fetch CPU & Database Connections metrics for all instances in the given time range."""
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now(timezone.utc)

        period = self.default_period

        # ✅ Get all RDS instances
        instances = self.get_all_rds_instances()
        if not instances:
            print("❌ No RDS instances found.")
            return {}

        # ✅ Prepare metric queries
        metric_queries = [
            {
                "Id": f"cpu_{instance.replace('-', '_')}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/RDS",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": instance}]
                    },
                    "Period": period,
                    "Stat": "Average"
                }
            }
            for instance in instances
        ] + [
            {
                "Id": f"conn_{instance.replace('-', '_')}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/RDS",
                        "MetricName": "DatabaseConnections",
                        "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": instance}]
                    },
                    "Period": period,
                    "Stat": "Average"
                }
            }
            for instance in instances
        ]

        # ✅ Fetch CloudWatch Metrics
        response = self.cloudwatch.get_metric_data(
            MetricDataQueries=metric_queries,
            StartTime=start_time,
            EndTime=end_time,
            ScanBy="TimestampAscending"
        )

        # ✅ Get instance-to-cluster mapping
        instance_cluster_mapping = self.get_instance_roles_and_clusters(instances)

        # ✅ Process & filter results (Remove instances with no metrics)
        metrics_data = {}

        for result in response["MetricDataResults"]:
            if not result["Values"]:
                continue  # Skip instances with no data

            instance_id = result["Id"].split("_", 1)[1].replace("_", "-")
            cluster_name = instance_cluster_mapping.get(instance_id, {}).get("Cluster")

            if not cluster_name or cluster_name not in self.cluster_identifiers:
                continue  # Skip unrecognized instances

            # Initialize cluster if not already present
            if cluster_name not in metrics_data:
                metrics_data[cluster_name] = {
                    "StartTime": self.time_function.convert_time(start_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC"),
                    "EndTime": self.time_function.convert_time(end_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC"),
                    "Instances": {},
                    "ReplicaCount": 0,
                    "WriterCount": 0,
                    "TotalReplicaCPU": 0,
                    "TotalWriterCPU": 0,
                    "TotalReplicaConnections": 0,
                    "TotalWriterConnections": 0
                }

            # Extract metric values
            avg_value = round(sum(result["Values"]) / len(result["Values"]), 2)
            role = instance_cluster_mapping.get(instance_id, {}).get("Role", "Unknown")

            # Add instance data
            if instance_id not in metrics_data[cluster_name]["Instances"]:
                metrics_data[cluster_name]["Instances"][instance_id] = {"Role": role}

            if result["Id"].startswith("cpu"):
                metrics_data[cluster_name]["Instances"][instance_id]["CPUUtilization"] = avg_value
                if role == "Replica":
                    metrics_data[cluster_name]["ReplicaCount"] += 1
                    metrics_data[cluster_name]["TotalReplicaCPU"] += avg_value
                elif role == "Writer":
                    metrics_data[cluster_name]["WriterCount"] += 1
                    metrics_data[cluster_name]["TotalWriterCPU"] += avg_value

            elif result["Id"].startswith("conn"):
                metrics_data[cluster_name]["Instances"][instance_id]["DatabaseConnections"] = avg_value
                if role == "Replica":
                    metrics_data[cluster_name]["TotalReplicaConnections"] += avg_value
                elif role == "Writer":
                    metrics_data[cluster_name]["TotalWriterConnections"] += avg_value

        return metrics_data

    def get_all_rds_instances(self):
        """Retrieve all RDS instances from CloudWatch."""
        instances = []
        response = self.cloudwatch.list_metrics(
            Namespace="AWS/RDS",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "DBInstanceIdentifier"}]
        )
        for metric in response.get("Metrics", []):
            for dimension in metric["Dimensions"]:
                if dimension["Name"] == "DBInstanceIdentifier":
                    instances.append(dimension["Value"])
        return list(set(instances))
    
    def get_instance_roles_and_clusters(self, instances):
        """
        Retrieves the role (Writer/Replica) and cluster name for each RDS instance.
        """
        instance_cluster_role = {}

        try:
            print("🔹 Fetching RDS instance roles and clusters...")
            # 🔹 **Fetch all RDS instances (includes standalone DBs)**
            response = self.rds_client.describe_db_instances()
            for db_instance in response["DBInstances"]:
                instance_id = db_instance["DBInstanceIdentifier"]
                cluster_id = db_instance.get("DBClusterIdentifier", None)  # If None, it's a standalone DB
                role = "Writer" if db_instance.get("ReadReplicaSourceDBInstanceIdentifier") is None else "Replica"

                if instance_id not in instance_cluster_role:
                    instance_cluster_role[instance_id] = {}
                instance_cluster_role[instance_id]["Cluster"] = cluster_id
                instance_cluster_role[instance_id]["Role"] = role
                    

            cluster_response = self.rds_client.describe_db_clusters()
            for cluster in cluster_response.get("DBClusters", []):
                cluster_id = cluster["DBClusterIdentifier"]
                for member in cluster["DBClusterMembers"]:
                    instance_id = member["DBInstanceIdentifier"]
                    if instance_id not in instance_cluster_role:
                        instance_cluster_role[cluster_id] = {}
                    role = "Writer" if member["IsClusterWriter"] else "Replica"
                    instance_cluster_role[instance_id]["Cluster"] = cluster_id
                    instance_cluster_role[instance_id]["Role"] = role

            for cluster_name in self.cluster_identifiers:
                instances_cluster_mapping = self.check_rds_instance_in_cluster_log_group(cluster_name, instances)
                for instance_id in instances_cluster_mapping:
                    if instance_id not in instance_cluster_role:
                        instance_cluster_role[instance_id] = {}
                        instance_cluster_role[instance_id]["Cluster"] = cluster_name
                        instance_cluster_role[instance_id]["Role"] = "Replica"
                            

        except Exception as e:
            print(f"⚠️ Error fetching RDS instance roles: {e}")
        return instance_cluster_role

    # using this for deleted instances if they are still present in the logs and are part of which cluster
    def check_rds_instance_in_cluster_log_group(self, cluster_name, instances):
        """
        Check if an RDS instance was part of a given cluster based on CloudWatch Logs.
        
        :param cluster_name: Name of the RDS cluster
        :param instance_id: RDS instance identifier
        :param region: AWS region
        :return: True if instance logs exist in the cluster, False otherwise
        """
        logs_client = boto3.client("logs", region_name=self.region)
        log_group_name = f"/aws/rds/cluster/{cluster_name}/postgresql"
        cluster_instances = {}
        try:
            response = logs_client.describe_log_streams(logGroupName=log_group_name)
            for log_stream in response.get("logStreams", []):
                for instance_id in instances:
                    if instance_id in log_stream["logStreamName"]:
                        cluster_instances[instance_id] = True
        except Exception as e:
            print(f"⚠️ Error fetching RDS logs: {e}")
        return cluster_instances

    def detect_rds_anomalies(self, current_metrics, past_metrics):
        """Compare current and past RDS metrics to detect anomalies."""
        anomalies = []

        for cluster_name, current_cluster in current_metrics.items():
            past_cluster = past_metrics.get(cluster_name, {})

            if not past_cluster:
                anomalies.append({"Cluster": cluster_name, "Issue": "No historical data available"})
                continue

            # ✅ Check replica count changes
            current_replicas = current_cluster.get("ReplicaCount", 0)
            past_replicas = past_cluster.get("ReplicaCount", 0)

            current_writers = current_cluster.get("WriterCount", 0)
            past_writers = past_cluster.get("WriterCount", 0)

            if current_replicas > past_replicas:
                anomalies.append({
                    "Cluster": cluster_name,
                    "Issue": f"Increase in Replica Count by {current_replicas - past_replicas}",
                    "Past_ReplicaCount": past_replicas,
                    "Current_ReplicaCount": current_replicas,
                    "Older Replicas": [instance for instance, data in past_cluster.get("Instances", {}).items() if data.get("Role") == "Replica"],
                    "New Replicas": [instance for instance, data in current_cluster.get("Instances", {}).items() if data.get("Role") == "Replica"]
                })

            # ✅ Check CPU & Connection spikes
            for metric, label,issue in [("TotalReplicaCPU", "Replica", "DB CPU"), ("TotalWriterCPU", "Writer", "DB CPU"),
                                  ("TotalReplicaConnections", "Replica", "DB Connection"), ("TotalWriterConnections", "Writer", "DB Connection")]:
                past_avg = past_cluster.get(metric, 0) / max(1, past_replicas if "Replica" in label else past_writers)
                current_avg = current_cluster.get(metric, 0) / max(1, current_replicas if "Replica" in label else current_writers)
                if current_avg > past_avg + (self.cpu_threshold if "CPU" in metric else self.conn_threshold):
                    anomalies.append({
                        "Cluster": cluster_name,
                        "Issue": f"Increase in {label} {issue} by {round(current_avg - past_avg, 2)}",
                        "Increased By": round(current_avg - past_avg, 2),
                        "Past_Avg": round(past_avg, 2),
                        "Current_Avg": round(current_avg, 2)
                    })

        return anomalies



# if __name__ == "__main__":
#     fetcher = RDSMetricsFetcher({
#         "AWS_REGION": "ap-south-1",
#         "DEFAULT_PERIOD": 3600,
#         "CPU_THRESHOLD": 10,
#         "CONN_THRESHOLD": 10,
#         "REPLICA_THRESHOLD": 1
#     })

#     current_metrics = fetcher.fetch_rds_metrics(datetime.now(timezone.utc) - timedelta(hours=1), datetime.now(timezone.utc))
#     past_metrics = fetcher.fetch_rds_metrics(datetime.now(timezone.utc) - timedelta(days=7) - timedelta(hours=1) , datetime.now(timezone.utc) - timedelta(days=7))


#     print("\n🔹 Current RDS Metrics:" , current_metrics)
#     print("\n🔹 Past RDS Metrics:" , past_metrics)

#     anomalies = fetcher.detect_rds_anomalies(current_metrics, past_metrics)

#     print("\n🔹 Anomalies Detected:",anomalies)
    # print(anomalies)
    # cluster_names = ["atlas-driver-v1-cluster", "atlas-customer-cluster-v1-cluster"]
    # all_instances = fetcher.get_all_rds_instances()
    # print(fetcher.get_instance_roles_and_clusters(all_instances))











