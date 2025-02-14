import boto3
from datetime import datetime, timedelta, timezone
class RDSMetricsFetcher:
    def __init__(self,config):
        """Initialize AWS CloudWatch client."""
        self.region = config.get("AWS_REGION", "ap-south-1")
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.rds_client = boto3.client('rds', region_name=self.region)
        self.default_period = int(config.get("DEFAULT_PERIOD", 60))  # Default to 60 seconds if not specified
        self.cluster_identifiers = config.get("RDS_CLUSTER_IDENTIFIERS", ["atlas-customer-cluster-v1-cluster"])
        self.rds_time_delta = config.get("RDS_TIME_DELTA", {"hours": 1})
        self.cpu_threshold = config.get("RDS_CPU_DIFFERENCE_THRESHOLD", 10)
        self.db_connections_threshold = config.get("RDS_CONNECTIONS_DIFFERENCE_THRESHOLD", 10)

    def get_rds_cluster_metrics(self, metrics_start_time=None, metrics_end_time=None, cluster_identifier=None):
        print("Fetching RDS cluster CPU utilization metrics")
        """
        Fetch CPU utilization metrics for all instances in the given RDS cluster.
        
        :param metrics_start_time: The start time for fetching the metrics
        :param metrics_end_time: The end time for fetching the metrics (defaults to now if not provided)
        """
        if metrics_start_time:
            start_time = metrics_start_time
        elif self.rds_time_delta:
            start_time = datetime.now(timezone.utc) - timedelta(**self.rds_time_delta)
        else:
            raise ValueError("Either metrics_start_time or rds_time_delta must be provided")
        
        # Set end time to now if not provided
        end_time = metrics_end_time if metrics_end_time else datetime.now(timezone.utc)    
        period = self.default_period

        # Fetch all DB instances in the cluster
        print(f"Fetching RDS cluster instances for {cluster_identifier} in region {self.region} time range between {start_time} and {end_time} with period {period} seconds")
        cluster_response = self.rds_client.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
        
        if "DBClusters" not in cluster_response or not cluster_response["DBClusters"]:
            raise ValueError(f"No cluster found with identifier: {cluster_identifier}")

        cluster_instances = cluster_response["DBClusters"][0]["DBClusterMembers"]

        print(f"Found {len(cluster_instances)} instances in cluster {cluster_identifier}")
        
        cluster_metrics = {}
        cluster_metrics["StartTime"] = str(start_time)
        cluster_metrics["EndTime"] = str(end_time)
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

        print(f"Fetched metrics for {len(cluster_instances)} instances in cluster {cluster_identifier}")
        return cluster_metrics
    
    def get_all_rds_cluster_metrics (self, metrics_start_time=None, metrics_end_time=None):
        all_cluster_metrics = {}
        for cluster_identifier in self.cluster_identifiers:
            all_cluster_metrics[cluster_identifier] = self.get_rds_cluster_metrics(metrics_start_time, metrics_end_time, cluster_identifier)
        return all_cluster_metrics
    
    def detect_rds_anomalies(self,current_metrics, past_metrics):
        """
        Compare RDS metrics (past vs. current) and detect anomalies.

        :param current_metrics: Dictionary containing current RDS metrics.
        :param past_metrics: Dictionary containing past RDS metrics.
        :param cpu_threshold: Percentage increase in CPU utilization to flag an anomaly.
        :param db_connections_threshold: Absolute increase in database connections to flag an anomaly.
        :return: List of detected anomalies with relevant metrics.
        """
        anomalies = []


        cluster_name = list(current_metrics.keys())[0]  # Assuming single cluster
        current_cluster = current_metrics[cluster_name]
        past_cluster = past_metrics[cluster_name]

        for instance in current_cluster:
            if instance in ["StartTime", "EndTime", "ReplicaCount"]:
                continue  # Skip metadata

            if instance not in past_cluster:
                continue  # Instance might not be present in past data

            current_instance = current_cluster[instance]
            past_instance = past_cluster[instance]

            instance_anomalies = {"Issue Type": "", "Instance": instance, "Role": current_instance["Role"], "Issue": [], "Current_Metrics": {}, "Past_Metrics": {}}

            # 🔹 **Check CPU Utilization Spike**
            cpu_diff = current_instance["CPUUtilization"] - past_instance["CPUUtilization"]
            if cpu_diff > self.cpu_threshold:
                instance_anomalies["Issue Type"] = "DB CPU INCREASE"
                instance_anomalies["Issue"].append(f"High CPU usage increase: {cpu_diff:.2f}% (Threshold: {self.cpu_threshold}%) from {past_instance['CPUUtilization']} to {current_instance['CPUUtilization']}")
                instance_anomalies["Current_Metrics"]["CPUUtilization"] = current_instance["CPUUtilization"]
                instance_anomalies["Past_Metrics"]["CPUUtilization"] = past_instance["CPUUtilization"]
                anomalies.append(instance_anomalies)

            # 🔹 **Check Database Connections Spike**
            db_conn_diff = current_instance["DatabaseConnections"] - past_instance["DatabaseConnections"]
            if db_conn_diff / past_instance["DatabaseConnections"] * 100 > self.db_connections_threshold:
                instance_anomalies["Issue Type"] = "DB CONNECTIONS INCREASE"
                instance_anomalies["Issue"].append(f"High DB connections increase: {db_conn_diff} (Threshold: {self.db_connections_threshold}) from {past_instance['DatabaseConnections']} to {current_instance['DatabaseConnections']}")
                instance_anomalies["Current_Metrics"]["DatabaseConnections"] = current_instance["DatabaseConnections"]
                instance_anomalies["Past_Metrics"]["DatabaseConnections"] = past_instance["DatabaseConnections"]
                anomalies.append(instance_anomalies)


        return {"Anomalies": anomalies}

