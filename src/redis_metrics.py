import subprocess
import boto3
from datetime import datetime, timedelta, timezone
import json
import redis
from time_function import TimeFunction

class RedisMetricsFetcher:
    def __init__(self,config):
        """Initialize AWS CloudWatch and ElastiCache clients."""
        self.region = config.get("AWS_REGION", "ap-south-1")
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.elasticache = boto3.client('elasticache', region_name=self.region)
        self.default_period = int(config.get("DEFAULT_PERIOD", 60))  # Default to 60 seconds if not specified
        self.cluster_ids = config.get("REDIS_CLUSTER_IDENTIFIERS", ["beckn-redis-cluster-001"])
        self.max_bigkey_size_mb = int(config.get("MAX_BIGKEY_SIZE_MB", 10))  # Default to 10 MB if not specified
        self.redis_time_delta = config.get("TIME_DELTA", {"hours": 1})
        self.cpu_threshold = float(config.get("REDIS_CPU_DIFFERENCE_THRESHOLD", 10.0))
        self.memory_threshold = float(config.get("REDIS_MEMORY_DIFFERENCE_THRESHOLD", 10.0))
        self.capacity_threshold = float(config.get("REDIS_CAPACITY_DIFFERENCE_THRESHOLD", 10.0))
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
            start_time = datetime.now(timezone.utc) - timedelta(**self.redis_time_delta)
        else:
            raise ValueError("Either metrics_start_time or redis_time_delta must be provided")
        
        end_time = metrics_end_time if metrics_end_time else datetime.now(timezone.utc)    
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

        for node_group in node_groups:
            for member in node_group.get("NodeGroupMembers", []):
                instance_id = member["CacheClusterId"]
                instance_role = "Primary" if instance_id in master_nodes else "Replica"
                
                # Get endpoint, fallback to ReadEndpoint if available
                endpoint_data = instance_endpoints.get(instance_id, {})
                instance_endpoint = endpoint_data.get("Address", member.get("ReadEndpoint", {}).get("Address", "Unknown"))
                instance_port = endpoint_data.get("Port", 6379)  # Default Redis port if unknown
                
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
        return cluster_metrics

    def get_all_redis_cluster_metrics(self, metrics_start_time=None, metrics_end_time=None):
        """
        Fetch metrics for all Redis clusters.
        """
        all_cluster_metrics = {}
        for cluster_id in self.cluster_ids:
            all_cluster_metrics[cluster_id] = self.get_redis_cluster_metrics(metrics_start_time, metrics_end_time, cluster_id)
        return all_cluster_metrics

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
            # print(*lines, sep="\n")
            for line in lines:
                parts = line.split()
                if len(parts) > 1 and parts[1].lower() == "biggest":
                    key_type = parts[2]  # Extract type (e.g., "string", "list", etc.)
                    key_name = parts[-4].strip('"')
                    # Extract size if available
                    size = None
                    if key_type == "string":
                        size = int(parts[-2])  # BIGKEYS provides size for strings
                    elif key_type in ["list", "hash", "set", "zset", "stream", "module"]:
                        size = None
                    bigkeys.append({"key": key_name, "type": key_type, "size": size})

            if not bigkeys:
                print("No big keys found")
                return []

            client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            # Check the memory usage of each big key (only if BIGKEYS didn't provide size)
            filtered_bigkeys = []
            for entry in bigkeys:
                key_name = entry["key"].strip("'").strip('"')
                key_type = entry["type"]
                key_size = entry["size"]

                if key_size is None:  # If BIGKEYS didn't provide size, call MEMORY USAGE
                    key_size = client.memory_usage(key_name)
    
                    print(f"Key: {key_name}, Type: {key_type}, Size: {key_size}")

                # Convert size to MB and check against threshold
                if key_size and (key_size / (1024 * 1024)) > self.max_bigkey_size_mb:
                    entry["size_mb"] = round(key_size / (1024 * 1024), 2)  # Store size in MB
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

            # ✅ Detect if new nodes were added (Check if any node was None in past)
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

            # ✅ Compute cluster-wide averages
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

            # ✅ Compute cluster-wide averages
            current_avg = {k: v / max(1, current_count) for k, v in current_totals.items()}
            past_avg = {k: v / max(1, past_count) for k, v in past_totals.items()}

            # ✅ Detect cluster-level metric spikes
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

            # ✅ Detect instance-level metric spikes
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
