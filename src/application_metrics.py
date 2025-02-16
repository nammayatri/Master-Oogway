import requests
import matplotlib.pyplot as plt
import datetime
import os
class ApplicationMetricsFetcher:
    def __init__(self, config):
        """
        Initialize the VictoriaMetrics API fetcher.
        """
        self.api_list = config.get("API_LIST", [])  # List of API paths
        self.vmselect_url = config.get("VMSELECT_URL", f"http://localhost:8481/select/0/prometheus/api/v1")
        self.query_step_range = config.get("QUERY_STEP_RANGE", "10m")
        self.namespace = config.get("KUBERNETES_NAMESPACE", "atlas")

    def time_to_epoch(self, start_time, end_time):
        """
        Convert datetime objects to epoch timestamps.
        """
        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time must be provided.")
        
        start_time = start_time if isinstance(start_time, int) else int(start_time.timestamp())
        end_time = end_time if isinstance(end_time, int) else int(end_time.timestamp())
        return start_time, end_time
    
    def fetch_metric(self, query, start, end, step="1m"):
        """
        Fetch metrics from VictoriaMetrics.
        """
        params = {"query": query, "start": start, "end": end, "step": step}
        url = f"{self.vmselect_url}/query_range"

        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error fetching {query}: {response.status_code}, {response.text}\n")
            return None

    def build_api_filter(self):
        """
        Generate **correct** PromQL filter for multiple APIs.
        """
        if not self.api_list:
            return ""

        include_filter = f'handler=~"({"|".join(api.strip() for api in self.api_list)})"'

        # ✅ **Exclude `/v2/` & `/ui/` APIs**
        exclude_filter = 'handler!="/v2/", handler!="/ui/"'

        return f"{include_filter}, {exclude_filter}"

    def aggregate_app_metric_by_labels(self, metric_data):
        """
        Extracts and aggregates values from a metric query response by method, handler, service, and groups them by 2xx, 3xx, 4xx, and 5xx status codes.

        :param metric_data: JSON response from VictoriaMetrics
        :return: Dictionary with aggregated totals grouped by (method, handler, service) and separated by status_code categories (2xx, 3xx, 4xx, 5xx)
        """
        if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
            return {} 

        aggregated_results = {}

        for series in metric_data["data"]["result"]:
            # Extract labels
            labels = series["metric"]
            method = labels.get("method", "unknown")
            handler = labels.get("handler", "unknown")
            service = labels.get("service", "unknown")
            status_code = labels.get("status_code", "unknown")

            # Define the category (2xx, 3xx, 4xx, 5xx)
            if status_code.startswith("2"):
                category = "2xx"
            elif status_code.startswith("3"):
                category = "3xx"
            elif status_code.startswith("4"):
                category = "4xx"
            elif status_code.startswith("5"):
                category = "5xx"
            else:
                category = "unknown"

            # Unique key for aggregation (ignoring specific status codes but grouping them separately)
            key = f"{method} {service} {handler}"

            # Initialize structure if not present
            if key not in aggregated_results:
                aggregated_results[key] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "unknown": 0}

            # Sum all values in the series
            total_count = sum(float(value[1]) for value in series["values"])

            # Store in dictionary under the appropriate category
            aggregated_results[key][category] += int(total_count)  # Convert to int for readability

        return aggregated_results

    def fetch_application_request_metrics(self, start_time=None, end_time=None):
        """
        Fetch all critical application-level API metrics and calculate totals.
        """
        # if time is not in epoch format then convert it to epoch format
        start, end = self.time_to_epoch(start_time, end_time)
        api_filter = self.build_api_filter()
        
        # **🔹 Total Request Count (All 2xx,3xx,4xx,5xx)**
        
        total_api_requests_query = f"sum(increase(http_request_duration_seconds_count{{{api_filter}}}[{self.query_step_range}])) by (method, handler, service, status_code)"

        print(f"🚀 Fetching Total API Requests Query: {total_api_requests_query}\n")
        total_requests_data = self.fetch_metric(total_api_requests_query, start, end,self.query_step_range)
        total_requests = self.aggregate_app_metric_by_labels(total_requests_data)
        return total_requests
    
    def aggregate_istio_metric_by_labels(self, metric_data):
        if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
            return {}

        aggregated_results = {}

        for series in metric_data["data"]["result"]:
            # Extract labels
            labels = series["metric"]
            service_name = labels.get("destination_service_name", "unknown")
            response_code = labels.get("response_code", "unknown")
            pod = labels.get("pod", "")

            # Define the category (2xx, 3xx, 4xx, 5xx)
            if response_code.startswith("2"):
                category = "2xx"
            elif response_code.startswith("3"):
                category = "3xx"
            elif response_code.startswith("4"):
                category = "4xx"
            elif response_code.startswith("5"):
                category = "5xx"
            elif response_code.startswith("0"):
                category = "0DC"
            else:
                category = "unknown"

            # Unique key for aggregation (ignoring specific status codes but grouping them separately)
            key = f"{service_name}" + f" {pod}"

            # Initialize structure if not present
            if key not in aggregated_results:
                aggregated_results[key] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "0DC": 0, "unknown": 0}

            # Sum all values in the series
            total_count = sum(float(value[1]) for value in series["values"])

            # Store in dictionary under the appropriate category
            aggregated_results[key][category] += int(total_count)

        return aggregated_results
    

    def fetch_istio_metrics(self, start_time=None, end_time=None):
        """
        Fetch all critical application-level API metrics and calculate totals.
        """
        start, end = self.time_to_epoch(start_time, end_time)
        # **🔹 Total Request Count (All 2xx,3xx,4xx,5xx)
        total_istio_requests_query = f"sum(increase(istio_requests_total{{destination_service_name!=\"istio-telemetry\", reporter=\"destination\"}}[{self.query_step_range}])) by (destination_service_name, response_code)"
        print("🚀 Fetching Total Isto request service level: ", total_istio_requests_query,"\n")
        total_istio_requests = self.fetch_metric(total_istio_requests_query, start, end,self.query_step_range)
        aggregated_istio_requests = self.aggregate_istio_metric_by_labels(total_istio_requests)

        return aggregated_istio_requests
    
    def fetch_istio_metrics_pod_wise_errors(self, start_time=None, end_time=None):
        start, end = self.time_to_epoch(start_time, end_time)
        # **🔹 Total Request Count (All 2xx,3xx,4xx,5xx)
        total_istio_requests_query = f"sum by (destination_service_name, pod, response_code, response_flags) ((label_replace(increase(istio_requests_total{{response_code!~\"(2..|3..|4..)\", destination_service_name!=\"istio-telemetry\", reporter=\"destination\"}}[{self.query_step_range}]), \"pod_ip\", \"$1\", \"instance\", \"^(.*):[0-9]+$\") * on (pod_ip) group_left(pod) (max by (pod_ip, pod) (kube_pod_info))))"
        print("🚀 Fetching Total Isto request erros pod level: ", total_istio_requests_query,"\n")
        total_istio_requests = self.fetch_metric(total_istio_requests_query, start, end,self.query_step_range)
        aggregated_istio_requests = self.aggregate_istio_metric_by_labels(total_istio_requests)
        return aggregated_istio_requests
    

    def fetch_individual_cpu_and_memory(self, start_time=None, end_time=None,pod=None):
        start_time , end_time = self.time_to_epoch(start_time, end_time)
        services = pod if pod else ".*"
        total_cpu_usage_query = f"sum(rate(container_cpu_usage_seconds_total{{namespace=\"{self.namespace}\", image!=\"\", container!=\"POD\", image!=\"\", pod=~\"{services}\", node=~\".*\"}}[1m])) by (pod, node)  / 2 / sum(kube_pod_container_resource_requests{{unit=\"core\",namespace=\"{self.namespace}\", container!=\"POD\", pod=~\"{services}\"}}) by (pod, node) * 100"
        total_memory_usage_query = f"(sum(container_memory_working_set_bytes{{namespace=\"{self.namespace}\", image!=\"\", container!=\"POD\", image!=\"\", pod=~\"{services}\", node=~\".*\"}}) by (pod, node) / 2 / sum(kube_pod_container_resource_requests{{unit=\"byte\",namespace=\"{self.namespace}\", container!=\"POD\", pod=~\"{services}\"}}) by (pod, node) * 100)"
        print("🚀 Fetching Total CPU Usage Query: ", total_cpu_usage_query,"\n"
            "🚀 Fetching Total Memory Usage Query: ", total_memory_usage_query,"\n"
            )
        total_cpu_usage = self.fetch_metric(total_cpu_usage_query, start_time, end_time)
        total_memory_usage = self.fetch_metric(total_memory_usage_query, start_time, end_time)
        return total_cpu_usage, total_memory_usage
        
    


    def detect_and_plot_anomalies_per_pod(self, cpu_data, memory_data, threshold,output_dir="anomaly_plots"):
        """
        Detects anomalies where two consecutive data points exceed the threshold
        and plots CPU and memory usage **only** for pods that have anomalies.

        :param cpu_data: JSON response containing CPU usage metrics
        :param memory_data: JSON response containing memory usage metrics
        :param threshold: Threshold value for anomaly detection
        """
        def extract_values(metric_data):
            """Extract timestamps, values, and pods from metric data."""
            if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
                return {}

            pod_data = {}
            for series in metric_data["data"]["result"]:
                pod_name = series["metric"].get("pod", "unknown")
                node = series["metric"].get("node", "unknown")
                timestamps, values = zip(*[(int(timestamp), float(value)) for timestamp, value in series["values"]])
                pod_data[pod_name] = {"timestamps": list(timestamps), "values": list(values), "node": node}
                

            return pod_data

        def detect_anomalies(values,consecutive_datpoints=2):
            anomalies = []
            count = 0  # Counter to track consecutive threshold breaches
            for i in range(len(values) - 1):
                if values[i] > threshold:
                    count += 1
                    if count >= consecutive_datpoints:
                        anomalies.append(i)
                else:
                    count = 0  
            return anomalies
        
        def clean_directory(directory_path):
            """Removes all files inside the directory while keeping the folder."""
            os.makedirs(directory_path, exist_ok=True)  # Ensure directory exists
            for file in os.listdir(directory_path):
                file_path = os.path.join(directory_path, file)
                try:
                    os.remove(file_path)  
                except IsADirectoryError:
                    pass  

        def convert_epoch_to_time(epoch_list):
            """Convert epoch timestamps to human-readable time format."""
            return [datetime.datetime.utcfromtimestamp(ts).strftime('%H:%M') for ts in epoch_list]
        saved_files = []
        os.makedirs(output_dir, exist_ok=True)
        # clean this directory
        clean_directory(output_dir)
        cpu_pod_data = extract_values(cpu_data)
        mem_pod_data = extract_values(memory_data)

        for pod in set(cpu_pod_data.keys()).union(set(mem_pod_data.keys())):
            cpu_anomalies, mem_anomalies = [], []

            # Check CPU anomalies
            if pod in cpu_pod_data:
                cpu_anomalies = detect_anomalies(cpu_pod_data[pod]["values"])

            # Check Memory anomalies
            if pod in mem_pod_data:
                mem_anomalies = detect_anomalies(mem_pod_data[pod]["values"])

            # **Plot only if there are anomalies**
            if cpu_anomalies or mem_anomalies:
                plt.figure(figsize=(12, 6))

                if pod in cpu_pod_data:
                    cpu_timestamps = convert_epoch_to_time(cpu_pod_data[pod]["timestamps"])
                    cpu_values = cpu_pod_data[pod]["values"]

                    plt.plot(cpu_timestamps, cpu_values, label="CPU Usage (%)", marker='o', linestyle="-", color='blue')

                    if cpu_anomalies:
                        plt.scatter([cpu_timestamps[i] for i in cpu_anomalies], 
                                    [cpu_values[i] for i in cpu_anomalies], color='red', zorder=3, label="CPU Anomalies")

                if pod in mem_pod_data:
                    mem_timestamps = convert_epoch_to_time(mem_pod_data[pod]["timestamps"])
                    mem_values = mem_pod_data[pod]["values"]

                    plt.plot(mem_timestamps, mem_values, label="Memory Usage (%)", marker='o', linestyle="-", color='purple')

                    if mem_anomalies:
                        plt.scatter([mem_timestamps[i] for i in mem_anomalies], 
                                    [mem_values[i] for i in mem_anomalies], color='red', zorder=3, label="Memory Anomalies")

                plt.xlabel("Timestamp")
                plt.xticks(range(0, len(cpu_timestamps), 2), cpu_timestamps[::2], rotation=45, ha="right")
                plt.ylabel("Usage (%)")
                plt.title(f"CPU & Memory Usage for: {pod} - {cpu_pod_data[pod]['node']}")
                plt.axhline(y=threshold, color='pink', linestyle='--', label=f"Threshold: {threshold}%")
                plt.legend()
                plt.grid(True, linestyle="--", alpha=0.5)
                
                plt.tight_layout()
                # plt.show()
                file_path = os.path.join(output_dir, f"{pod}_anomalies.png")
                plt.savefig(file_path)
                plt.close()
                saved_files.append(file_path)




    def fetch_all_prom_metrics(self, start_time=None, end_time=None):
        """
        Fetch all critical application-level API metrics and calculate totals.
        """
        app_metrics = self.fetch_application_request_metrics(start_time, end_time)
        istio_metrics = self.fetch_istio_metrics(start_time, end_time)

        result = {
            "application_metrics": app_metrics,
            "istio_metrics": istio_metrics
        }
        return result
        
    
    

