import subprocess
import boto3
from datetime import datetime, timedelta, timezone as dt_timezone  # Rename timezone to avoid conflict
import json
import redis
from load_config import load_config
from time_function import TimeFunction
import matplotlib.pyplot as plt 
import os 
from pytz import timezone  

class RedisMetricsFetcher:
    def __init__(self,config):
        """Initialize AWS CloudWatch and ElastiCache clients."""
        self.region = config.get("AWS_REGION", "ap-south-1")
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.elasticache = boto3.client('elasticache', region_name=self.region)
        self.default_period = int(config.get("DEFAULT_PERIOD", 60))  # Default to 60 seconds if not specified
        self.cluster_ids = config.get("REDIS_CLUSTER_IDENTIFIERS", [""])
        self.max_bigkey_size_mb = int(config.get("MAX_BIGKEY_SIZE_MB", 10))  # Default to 10 MB if not specified
        self.redis_time_delta = config.get("TIME_DELTA", {"hours": 1})
        self.cpu_threshold = float(config.get("REDIS_CPU_DIFFERENCE_THRESHOLD", 10.0))
        self.memory_threshold = float(config.get("REDIS_MEMORY_DIFFERENCE_THRESHOLD", 10.0))
        self.capacity_threshold = float(config.get("REDIS_CAPACITY_DIFFERENCE_THRESHOLD", 10.0))
        self.redis_cpu_memory_threshold = float(config.get("REDIS_CPU_MEMORY_THRESHOLD", 80.0))
        self.allow_instance_anomalies = config.get("ALLOW_INSTANCE_ANOMALIES", False)
        self.time_function = TimeFunction(config)


    def get_cache_instance_endpoints(self, cluster_instances):
        """
        Fetch the endpoint details for each Redis instance.

        :param cluster_instances: List of Redis instance identifiers.
        :return: Dictionary with instance_id -> (endpoint, port) mapping.
        """
        endpoints = {}
        for instance_id in cluster_instances:
            response = self.elasticache.describe_cache_clusters(CacheClusterId=instance_id, ShowCacheNodeInfo=True)
            for cluster in response.get("CacheClusters", []):
                for node in cluster.get("CacheNodes", []):
                    endpoints[instance_id] = {
                        "Address": node["Endpoint"]["Address"],
                        "Port": node["Endpoint"]["Port"]
                    }
        return endpoints

    def get_redis_cluster_metrics(self, metrics_start_time=None, metrics_end_time=None, cluster_id=None):
        """
        Fetch Redis CPU utilization, memory usage, number of replicas, master nodes, and their endpoints.
        """
        if metrics_start_time:
            start_time = metrics_start_time
        elif self.redis_time_delta:
            start_time = datetime.now(dt_timezone.utc) - timedelta(**self.redis_time_delta)  # Use dt_timezone.utc
        else:
            raise ValueError("Either metrics_start_time or redis_time_delta must be provided")
        
        end_time = metrics_end_time if metrics_end_time else datetime.now(dt_timezone.utc)  # Use dt_timezone.utc
        period = self.default_period

        # Fetch Redis cluster details
        print(f"Fetching Redis cluster instances for {cluster_id} in region {self.region} time range between {start_time} and {end_time} with period {period} seconds")
        cluster_response = self.elasticache.describe_replication_groups(ReplicationGroupId=cluster_id)
        
        if "ReplicationGroups" not in cluster_response or not cluster_response["ReplicationGroups"]:
            raise ValueError(f"No Redis cluster found with identifier: {cluster_id}")
        
        node_groups = cluster_response["ReplicationGroups"][0].get("NodeGroups", [])
        cluster_metrics = {}
        master_nodes = []
        all_instances = []

        for node_group in node_groups:
            node_members = node_group.get("NodeGroupMembers", [])
            if not node_members:
                continue

            # Assume first node in group is the Primary (Master)
            primary_instance = node_members[0]["CacheClusterId"]
            master_nodes.append(primary_instance)
            all_instances.extend([member["CacheClusterId"] for member in node_members])

        # Fetch endpoints for all instances using describe_cache_clusters
        instance_endpoints = self.get_cache_instance_endpoints(all_instances)
        data_points = {}
        for node_group in node_groups:
            for member in node_group.get("NodeGroupMembers", []):
                instance_id = member["CacheClusterId"]
                instance_role = "Primary" if instance_id in master_nodes else "Replica"
                
                # Get endpoint, fallback to ReadEndpoint if available
                endpoint_data = instance_endpoints.get(instance_id, {})
                instance_endpoint = endpoint_data.get("Address", member.get("ReadEndpoint", {}).get("Address", "Unknown"))
                instance_port = endpoint_data.get("Port", 6379)  # Default Redis port if unknown
                
                data_points[instance_id] = {}
                cluster_metrics[instance_id] = {
                    "Role": instance_role,
                    "Endpoint": instance_endpoint,
                    "Port": instance_port
                }

                # Fetch Redis CPU Utilization
                cpu_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/ElastiCache",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "CacheClusterId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average"]
                )
                cluster_metrics[instance_id]['CPUUtilization'] = round(cpu_response["Datapoints"][-1]["Average"],2) if cpu_response["Datapoints"] else None
                data_points[instance_id]['cpu'] = cpu_response["Datapoints"]

                
                # Fetch Redis Engine CPU Utilization
                engine_cpu_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/ElastiCache",
                    MetricName="EngineCPUUtilization",
                    Dimensions=[{"Name": "CacheClusterId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average"]
                )
                cluster_metrics[instance_id]['EngineCPUUtilization'] = round(engine_cpu_response["Datapoints"][-1]["Average"],2) if engine_cpu_response["Datapoints"] else None
                
                # Fetch Redis Database Capacity Usage Percentage
                capacity_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/ElastiCache",
                    MetricName="DatabaseCapacityUsagePercentage",
                    Dimensions=[{"Name": "CacheClusterId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average"]
                )
                cluster_metrics[instance_id]['DatabaseCapacityUsage'] = round(capacity_response["Datapoints"][-1]["Average"],2) if capacity_response["Datapoints"] else None

                # Fetch Redis Memory Usage
                memory_response = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/ElastiCache",
                    MetricName="DatabaseMemoryUsagePercentage",
                    Dimensions=[{"Name": "CacheClusterId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average"]
                )
                cluster_metrics[instance_id]['MemoryUsage'] = round(memory_response["Datapoints"][-1]["Average"],2) if memory_response["Datapoints"] else None
                data_points[instance_id]['memory'] = memory_response["Datapoints"]
        
        # Add number of replicas
        cluster_metrics["ReplicaCount"] = sum(1 for instance in cluster_metrics if cluster_metrics[instance]["Role"] == "Replica")
        cluster_metrics["StartTime"] = self.time_function.convert_time(start_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC")
        cluster_metrics["EndTime"] = self.time_function.convert_time(end_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC")
        cluster_metrics["MasterNodes"] = [{
            "InstanceId": instance,
            "Endpoint": cluster_metrics[instance]["Endpoint"],
            "Port": cluster_metrics[instance]["Port"]
        } for instance in master_nodes]
        
        print(f"Fetched metrics for Redis cluster {cluster_id}")
        return cluster_metrics , data_points

    def get_all_redis_cluster_metrics(self, metrics_start_time=None, metrics_end_time=None):
        """
        Fetch metrics for all Redis clusters and generate graphs.
        """
        all_cluster_metrics = {}
        for cluster_id in self.cluster_ids:
            mertrics, data_points = self.get_redis_cluster_metrics(metrics_start_time, metrics_end_time, cluster_id)
            all_cluster_metrics[cluster_id] = mertrics
            all_cluster_metrics[cluster_id]["data_points"] = data_points
        return all_cluster_metrics
    
    def get_redis_metrics_graphs(self, redis_data, output_dir="redis_graphs"):
        for cluster_id, metrics in redis_data.items():
            start_time = metrics["StartTime"]
            end_time = metrics["EndTime"]
            metric_data_results = metrics["data_points"]
            return self.generate_metric_graphs(metric_data_results, start_time, end_time, cluster_id, output_dir,threshold=self.redis_cpu_memory_threshold)


    def generate_metric_graphs(self, metric_data_results, start_time, end_time, cluster_id, output_dir="redis_graphs", threshold=80):
        """
        Generate a single graph for each instance containing all metrics with different colors.
        Only generate graphs if two consecutive data points cross the threshold.
        """
        print("📊 Generating graphs for Redis metrics...")
        os.makedirs(output_dir, exist_ok=True)
        ist = timezone("Asia/Kolkata")  # Define IST timezone
        result = []
        for instance_id, metrics in metric_data_results.items():
            if not isinstance(metrics, dict):
                continue

            metric_keys = ["cpu", "memory"]
            metric_labels = {
                "cpu": "CPU Utilization (%)",
                "memory": "Memory Usage (%)"
            }
            colors = ["blue", "red"]

            plt.figure(figsize=(14, 8))
            should_generate_graph = False

            for metric_key, color in zip(metric_keys, colors):
                data_points = metrics.get(metric_key, [])
                if not data_points:
                    continue

                sorted_data = sorted(
                    [(dp["Timestamp"], dp["Average"]) for dp in data_points if "Timestamp" in dp and "Average" in dp],
                    key=lambda x: x[0]
                )
                if not sorted_data:
                    continue

                timestamps, values = zip(*sorted_data)
                timestamps = [ts.astimezone(ist).strftime("%H:%M") for ts in timestamps]  # Format to show only time
                x_indices = range(len(timestamps))  # Use numerical indices for the x-axis

                # Check if two consecutive data points cross the threshold
                for i in range(1, len(values)):
                    if values[i - 1] > threshold and values[i] > threshold:
                        should_generate_graph = True
                        break

                # Plot the metric
                plt.plot(x_indices, values, marker="o", label=metric_labels.get(metric_key, metric_key), color=color)
                plt.xticks(x_indices, timestamps, rotation=45, fontsize=14)  # Set x-axis labels to formatted timestamps

            if not should_generate_graph:
                print(f"⚠️ Skipping graph for instance {instance_id} as no consecutive data points crossed the threshold.")
                plt.close()
                continue

            # Add graph details
            plt.title(f"(Cluster: {cluster_id}) | {instance_id}", fontsize=20, fontweight="bold")
            plt.xlabel("Timestamp (IST)", fontsize=14)
            plt.ylabel("Value (%)", fontsize=14)
            plt.xticks(rotation=45, fontsize=14)
            plt.yticks(fontsize=14)
            plt.grid(True, linestyle="--", alpha=0.6)
            plt.legend(fontsize=14)
            plt.tight_layout()

            filename = os.path.join(output_dir, f"{instance_id}_{start_time.replace(':', '').replace(' ', '_')}_{end_time.replace(':', '').replace(' ', '_')}.png")
            plt.savefig(filename, dpi=300)
            result.append( filename)
            print(f"✅ Graph saved: {filename}")
            plt.close()
        print("📊 Graph generation completed."
              f" Graphs saved in {output_dir} directory.")
        return result


    # Fetch the bigkeys from Redis  
    
    def get_bigkeys_with_size(self, redis_host, redis_port=6379):
        """
        Runs Redis BIGKEYS to find big keys and checks their memory usage.
        
        Calls MEMORY USAGE only if BIGKEYS doesn't provide a size.

        :param redis_host: Redis hostname (endpoint).
        :param redis_port: Redis instance port (default: 6379).
        :return: List of big keys that exceed the threshold, including their estimated size.
        """
        try:
            # Run redis-cli --bigkeys command
            print(f"Running BIGKEYS on Redis {redis_host}:{redis_port}")
            cmd = f"redis-cli -h {redis_host} -p {redis_port} --bigkeys"
            output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if output.returncode != 0:
                print(f"Error running BIGKEYS: {output.stderr}")
                return []

            # Parse BIGKEYS output
            bigkeys = []
            lines = output.stdout.split("\n")
            for line in lines:
                parts = line.split()
                if len(parts) > 1 and parts[1].lower() == "biggest":
                    key_type = parts[2]
                    key_name = parts[-4].strip('"')
                    size = None
                    if key_type == "string":
                        size = int(parts[-2])
                    elif key_type in ["list", "hash", "set", "zset", "stream", "module"]:
                        size = None
                    bigkeys.append({"key": key_name, "type": key_type, "size": size})

            if not bigkeys:
                print("No big keys found")
                return []

            client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            filtered_bigkeys = []
            for entry in bigkeys:
                key_name = entry["key"].strip("'").strip('"')
                key_type = entry["type"]
                key_size = entry["size"]

                if key_size is None:
                    key_size = client.memory_usage(key_name)
    
                    print(f"Key: {key_name}, Type: {key_type}, Size: {key_size}")

                if key_size and (key_size / (1024 * 1024)) > self.max_bigkey_size_mb:
                    entry["size_mb"] = round(key_size / (1024 * 1024), 2)
                    filtered_bigkeys.append(entry)

            return filtered_bigkeys

        except Exception as e:
            print(f"Error fetching big keys: {e}")
            return []
        
    from datetime import datetime, timezone


    def detect_anomalies(self, current_data, past_data):
        """
        Detects anomalies by comparing current and past Redis cluster metrics.
        
        :param current_data: Current Redis cluster data
        :param past_data: Past Redis cluster data
        :return: Dictionary containing detected anomalies
        """
        redis_anomalies = []
        cluster_name = list(current_data.keys())
        for cluster_name in cluster_name:
            anomalies = []

            current_cluster = current_data[cluster_name]
            past_cluster = past_data.get(cluster_name, {})

            for node, metrics in current_cluster.items():
                if node.startswith("beckn-redis-cluster") and isinstance(metrics, dict):
                    past_metrics = past_cluster.get(node, {})
                    if ((not past_metrics or any(v is None for v in past_metrics.values())) and past_metrics.get("Role","None") == "Primary"):
                        anomalies.append({
                            "Cluster": cluster_name,
                            "Instance": node,
                            "Issue": "New Redis node detected",
                            "Anomaly Level": "NEW_INSTANCE"
                        })

            current_totals = {"CPU": 0, "Memory": 0, "Capacity": 0, "EngineCPU": 0}
            past_totals = {"CPU": 0, "Memory": 0, "Capacity": 0, "EngineCPU": 0}
            current_count, past_count = 0, 0

            for node, metrics in current_cluster.items():
                if node.startswith("beckn-redis-cluster") and isinstance(metrics, dict):
                    if metrics["CPUUtilization"] is not None and metrics["Role"] == "Primary":
                        current_totals["CPU"] += metrics["CPUUtilization"]
                        current_count += 1
                    if metrics["MemoryUsage"] is not None and metrics["Role"] == "Primary":
                        current_totals["Memory"] += metrics["MemoryUsage"]
                    if metrics["DatabaseCapacityUsage"] is not None and metrics["Role"] == "Primary":
                        current_totals["Capacity"] += metrics["DatabaseCapacityUsage"]
                    if metrics["EngineCPUUtilization"] is not None and metrics["Role"] == "Primary":
                        current_totals["EngineCPU"] += metrics["EngineCPUUtilization"]

            for node, metrics in past_cluster.items():
                if node.startswith("beckn-redis-cluster") and isinstance(metrics, dict):
                    if metrics["CPUUtilization"] is not None and metrics["Role"] == "Primary":
                        past_totals["CPU"] += metrics["CPUUtilization"]
                        past_count += 1
                    if metrics["MemoryUsage"] is not None and metrics["Role"] == "Primary":
                        past_totals["Memory"] += metrics["MemoryUsage"]
                    if metrics["DatabaseCapacityUsage"] is not None and metrics["Role"] == "Primary":
                        past_totals["Capacity"] += metrics["DatabaseCapacityUsage"]
                    if metrics["EngineCPUUtilization"] is not None and metrics["Role"] == "Primary":
                        past_totals["EngineCPU"] += metrics["EngineCPUUtilization"]

            current_avg = {k: v / max(1, current_count) for k, v in current_totals.items()}
            past_avg = {k: v / max(1, past_count) for k, v in past_totals.items()}

            for key, threshold in [("CPU", self.cpu_threshold), 
                                ("Memory", self.memory_threshold), 
                                ("Capacity", self.capacity_threshold), 
                                ("EngineCPU", self.cpu_threshold)]:
                diff = current_avg[key] - past_avg[key]
                if diff > threshold:
                    anomalies.append({
                        "Cluster": cluster_name,
                        "Issue": f"High {key} Usage Increase Detected in Redis Clusterc {cluster_name} !!!",
                        "Past_Avg": round(past_avg[key], 2),
                        "Current_Avg": round(current_avg[key], 2),
                        "Increased By": round(diff, 2),
                        "Threshold": threshold
                    })

            if len(anomalies) == 0 or not self.allow_instance_anomalies:
                print(f"Skipping instance-level anomaly detection for {cluster_name} as detected anomalies: {anomalies} and allow_instance_anomalies: {self.allow_instance_anomalies}")
                redis_anomalies.extend(anomalies)
                continue
            for node, metrics in current_cluster.items():
                if node.startswith("beckn-redis-cluster") and isinstance(metrics, dict) and metrics["Role"] == "Primary":
                    past_metrics = past_cluster.get(node, {})
                    instance_anomalies = {
                        "Cluster": cluster_name,
                        "Instance": node,
                        "Issues": []
                    }

                    for key, threshold in [("CPUUtilization", self.cpu_threshold), 
                                        ("MemoryUsage", self.memory_threshold), 
                                        ("DatabaseCapacityUsage", self.capacity_threshold), 
                                        ("EngineCPUUtilization", self.cpu_threshold)]:
                        if key in metrics and key in past_metrics:
                            if metrics[key] is not None and past_metrics[key] is not None:
                                diff = metrics[key] - past_metrics[key]
                                if diff > threshold:
                                    instance_anomalies["Issues"].append({
                                        "Metric": key,
                                        "Issue": f"High {key} Usage Increase Detected in Redis Node {node} !!!",
                                        "Past_Value": round(past_metrics[key], 2),
                                        "Current_Value": round(metrics[key], 2),
                                        "Increased By": round(diff, 2),
                                        "Threshold": threshold
                                    })

                    if instance_anomalies["Issues"]:
                        anomalies.append(instance_anomalies)
            redis_anomalies.extend(anomalies)

        return redis_anomalies

# if __name__ == "__main__":
#     config = load_config()
#     redis_metrics_fetcher = RedisMetricsFetcher(config)
#     current_data = redis_metrics_fetcher.get_all_redis_cluster_metrics()
#     redis_metrics_fetcher.get_redis_metrics_graphs(current_data)