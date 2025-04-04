import json
import shutil
import matplotlib
import requests
import matplotlib.pyplot as plt
import datetime
import os
from datetime import datetime, timedelta, timezone


class ApplicationMetricsFetcher:
    def __init__(self, config):
        """Initialize the VictoriaMetrics API fetcher."""
        self.api_list = config.get("API_LIST", [])
        self.vmselect_url = config.get("VMSELECT_URL", "http://localhost:8481/select/0/prometheus/api/v1")
        self.query_step_range = config.get("QUERY_STEP_RANGE", "10m")
        self.namespace = config.get("KUBERNETES_NAMESPACE", "atlas")
        self.cpu_threshold = config.get("APPLICATION_CPU_THRESHOLD", 80)
        self.memory_threshold = config.get("APPLICATION_MEMORY_THRESHOLD", 80)
        self.app_consecutive_datapoints = config.get("APPLICATION_CONSECUTIVE_DATAPOINTS", 2)
        self.skip_memory_anomaly = config.get("SKIP_MEMORY_CHECK_SERVICES", [])
        self.skip_cpu_anomaly = config.get("SKIP_CPU_CHECK_SERVICES", [])
        self.skip_error_check_services = config.get("SKIP_ERROR_CHECK_SERVICES", [])
        self.istio_metrics = config.get("ISTIO_METRICS", [])
        self.application_metrics = config.get("APPLICATION_METRICS", [])
        self.ERROR_5XX_THRESHOLD = config.get("ERROR_5XX_THRESHOLD", 10)
        self.ERROR_0DC_THRESHOLD = config.get("ERROR_0DC_THRESHOLD", 10)
        self.API_5XX_THRESHOLD = config.get("API_5XX_THRESHOLD", 10)
        self.error_consecutive_datapoints = config.get("ERROR_CONSECUTIVE_DATAPOINTS", 2)
        matplotlib.use("Agg")


    def time_to_epoch(self, start_time, end_time):
        """Convert datetime objects to epoch timestamps."""
        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time must be provided.")

        start_time = start_time if isinstance(start_time, int) else int(start_time.timestamp())
        end_time = end_time if isinstance(end_time, int) else int(end_time.timestamp())
        return start_time, end_time
    
    def fetch_metric(self, query, start, end, step="1m"):
        """Fetch metrics from VictoriaMetrics."""
        params = {"query": query, "start": start, "end": end, "step": step}
        url = f"{self.vmselect_url}/query_range"
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error fetching {query}: {response.status_code}, {response.text}\n")
            return None

    def build_api_filter(self):
        """Generate a PromQL filter for multiple APIs."""
        if not self.api_list:
            return ""

        include_filter = f'handler=~"({"|".join(api.strip() for api in self.api_list)})"'
        exclude_filter = 'handler!="/v2/", handler!="/ui/"'
        return f"{include_filter}, {exclude_filter}"

    def aggregate_app_metric_by_labels(self, metric_data):
        """Aggregate metric values by method, handler, service, and status code categories."""
        if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
            return {}

        aggregated_results = {}
        for series in metric_data["data"]["result"]:
            labels = series["metric"]
            method = labels.get("method", "unknown")
            handler = labels.get("handler", "unknown")
            service = labels.get("service", "unknown")
            status_code = labels.get("status_code", "unknown")

            category = self._get_status_category(status_code)
            key = f"{method} {service} {handler}"
            if key not in aggregated_results:
                aggregated_results[key] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "unknown": 0}

            total_count = sum(float(value[1]) for value in series["values"])
            aggregated_results[key][category] += int(total_count)

        return aggregated_results

    def _get_status_category(self, status_code):
        """Determine status code category (2xx, 3xx, 4xx, 5xx, unknown)."""
        if status_code.startswith("2"):
            return "2xx"
        elif status_code.startswith("3"):
            return "3xx"
        elif status_code.startswith("4"):
            return "4xx"
        elif status_code.startswith("5"):
            return "5xx"
        return "unknown"
        
    def get_search_to_ride_metrics(self, start_time=None, end_time=None, output_dir="anomaly_plots"):
        """Fetch and plot Search to Ride Conversion metrics."""
        query = "(sum(rate(ride_created_count[1m])) / sum(rate(search_request_count[1m]))) * 100"
        start, end = self.time_to_epoch(start_time, end_time)
        print(f"🚀 Fetching Search to Ride Conversion Query: {query}\n")
        search_to_ride_data = self.fetch_metric(query, start, end)
        file_path = self.plot_search_to_ride_metrics(search_to_ride_data, output_dir)
        return file_path, search_to_ride_data
    
    def plot_search_to_ride_metrics(self, search_to_ride_data, output_dir="anomaly_plots"):
        """Plot the Search to Ride Conversion metrics."""
        if not search_to_ride_data or "data" not in search_to_ride_data:
            print("❌ No Search to Ride Conversion data found.")
            return None

        timestamps, values = zip(*[(int(ts), float(val)) for ts, val in search_to_ride_data["data"]["result"][0]["values"]])
        plt.figure(figsize=(12, 6))
        human_timestamps = self._convert_epoch_to_time(timestamps)
        numeric_timestamps = list(range(len(human_timestamps)))

        output_path = os.path.join(output_dir, f"search_to_ride_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        os.makedirs(output_path, exist_ok=True)

        plt.plot(numeric_timestamps, values, label="Ratio (%)", marker="o", linestyle="-", color="green")
        plt.scatter(
            [numeric_timestamps[i] for i in range(len(values)) if values[i] > 10],
            [val for val in values if val > 10],
            zorder=3,
        )
        plt.xticks(numeric_timestamps[::2], human_timestamps[::2], rotation=45, ha="right")
        plt.xlabel("Timestamp")
        plt.ylabel("Conversion Rate (%)")
        plt.title("Search to Ride Conversion Rate")
        plt.axhline(y=40, color="red", linestyle="--", label="Threshold: 40%")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()

        file_path = os.path.join(output_path, "search_to_ride.png")
        plt.savefig(file_path)
        plt.close()
        return file_path

    def _convert_epoch_to_time(self, epoch_list):
        """Convert epoch timestamps to IST human-readable format."""
        return [
            (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=5, minutes=30)).strftime("%H:%M")
            for ts in epoch_list
        ]    
    

    def fetch_application_request_metrics(self, start_time=None, end_time=None):
        """Fetch and aggregate application-level API metrics."""
        start, end = self.time_to_epoch(start_time, end_time)
        api_filter = self.build_api_filter()
        query = (
            f"sum(increase(http_request_duration_seconds_count{{{api_filter}}}"
            f"[{self.query_step_range}])) by (method, handler, service, status_code)"
        )

        print(f"🚀 Fetching Total API Requests Query: {query}\n")
        total_requests_data = self.fetch_metric(query, start, end, self.query_step_range)
        return self.aggregate_app_metric_by_labels(total_requests_data)
    
    def aggregate_istio_metric_by_labels(self, metric_data, is_pod=False):
        """Aggregate Istio metrics by service or pod and status code categories."""
        if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
            return {}

        aggregated_results = {}
        for series in metric_data["data"]["result"]:
            labels = series["metric"]
            service_name = labels.get("destination_service_name", "unknown")
            response_code = labels.get("response_code", "unknown")
            pod = labels.get("pod", "")

            category = self._get_istio_status_category(response_code)
            key = f"{service_name} {pod}".strip() if not is_pod else pod.strip()

            if key not in aggregated_results:
                aggregated_results[key] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "0DC": 0, "unknown": 0}

            total_count = sum(float(value[1]) for value in series["values"])
            aggregated_results[key][category] += int(total_count)

        return dict(sorted(aggregated_results.items(), key=lambda item: item[1]["5xx"] + item[1]["0DC"], reverse=True))

    def _get_istio_status_category(self, response_code):
        """Determine Istio response code category."""
        if response_code.startswith("2"):
            return "2xx"
        elif response_code.startswith("3"):
            return "3xx"
        elif response_code.startswith("4"):
            return "4xx"
        elif response_code.startswith("5"):
            return "5xx"
        elif response_code.startswith("0"):
            return "0DC"
        return "unknown"

    def fetch_istio_metrics(self, start_time=None, end_time=None):
        """Fetch and aggregate Istio metrics."""
        start, end = self.time_to_epoch(start_time, end_time)
        query = (
            f"sum(increase(istio_requests_total{{destination_service_name!=\"istio-telemetry\", "
            f"reporter=\"destination\"}}[{self.query_step_range}])) "
            "by (destination_service_name, response_code)"
        )
        print(f"🚀 Fetching Total Istio request service level: {query}\n")
        total_istio_requests = self.fetch_metric(query, start, end, self.query_step_range)
        aggregated_istio_requests = self.aggregate_istio_metric_by_labels(total_istio_requests)
        return aggregated_istio_requests, total_istio_requests
    
    def fetch_istio_metrics_pod_wise_errors(self, start_time=None, end_time=None, service_names=None):
        """Fetch pod-wise Istio error metrics."""
        start, end = self.time_to_epoch(start_time, end_time)
        base_query = (
            "sum by (destination_service_name, pod, response_code, response_flags) "
            "((label_replace(increase(istio_requests_total{response_code!~\"(2..|3..)\", "
            "destination_service_name!=\"istio-telemetry\", reporter=\"destination\"}"
            f"[{self.query_step_range}]), \"pod_ip\", \"$1\", \"instance\", \"^(.*):[0-9]+$\") "
            "* on (pod_ip) group_left(pod) (max by (pod_ip, pod) (kube_pod_info))))"
        )

        if service_names:
            service_filter = f"destination_service_name=~\"({'|'.join(service_names)})\", "
            query = (
                "sum by (pod, response_code, response_flags) "
                f"((label_replace(increase(istio_requests_total{{response_code!~\"(2..|3..)\", "
                f"destination_service_name!=\"istio-telemetry\", {service_filter}"
                f"reporter=\"destination\"}}[{self.query_step_range}]), \"pod_ip\", \"$1\", "
                f"\"instance\", \"^(.*):[0-9]+$\") * on (pod_ip) group_left(pod) "
                "(max by (pod_ip, pod) (kube_pod_info))))"
            )
        else:
            query = base_query

        print(f"🚀 Fetching Total Istio request errors pod level: {query}\n")
        total_istio_requests = self.fetch_metric(query, start, end, self.query_step_range)
        return self.aggregate_istio_metric_by_labels(total_istio_requests, is_pod=True)
    

    def fetch_individual_cpu_and_memory(self, start_time=None, end_time=None, pod=None, services=None):
        """Fetch CPU and memory usage metrics for pods or services."""
        start_time, end_time = self.time_to_epoch(start_time, end_time)
        services = pod if pod else f"{services}.*" if services else ".*"

        cpu_query = (
            f"sum(rate(container_cpu_usage_seconds_total{{namespace=\"{self.namespace}\", "
            f"image!=\"\", container!=\"POD\", pod=~\"{services}\", node=~\".*\"}}[1m])) "
            "by (pod, node) / 2 / sum(kube_pod_container_resource_requests{"
            f"unit=\"core\", namespace=\"{self.namespace}\", container!=\"POD\", "
            f"pod=~\"{services}\"}}) by (pod, node) * 100"
        )
        memory_query = (
            f"(sum(container_memory_working_set_bytes{{namespace=\"{self.namespace}\", "
            f"image!=\"\", container!=\"POD\", pod=~\"{services}\", node=~\".*\"}}) "
            "by (pod, node) / 2 / sum(kube_pod_container_resource_requests{"
            f"unit=\"byte\", namespace=\"{self.namespace}\", container!=\"POD\", "
            f"pod=~\"{services}\"}}) by (pod, node) * 100)"
        )

        print(f"🚀 Fetching Total CPU Usage Query: {cpu_query}\n")
        print(f"🚀 Fetching Total Memory Usage Query: {memory_query}\n")
        total_cpu_usage = self.fetch_metric(cpu_query, start_time, end_time)
        total_memory_usage = self.fetch_metric(memory_query, start_time, end_time)
        return total_cpu_usage, total_memory_usage
        
    def clean_directory(self, directory_path="anomaly_plots"):
        """Remove all files inside the directory while keeping the folder."""
        os.makedirs(directory_path, exist_ok=True)
        for file in os.listdir(directory_path):
            file_path = os.path.join(directory_path, file)
            try:
                os.remove(file_path)
            except IsADirectoryError:
                pass

    def delete_directory(self, directory_path="anomaly_plots"):
        """Delete the directory and all its contents."""
        if os.path.exists(directory_path):
            print(f"🗑️ Deleting directory: {directory_path}")
            shutil.rmtree(directory_path)
        

    def detect_and_plot_mem_cpu_anomalies_per_pod(self, cpu_data, memory_data, output_dir="anomaly_plots",istio_error_pods=None):
        """
        Detects anomalies where n consecutive data points exceed the threshold
        and plots CPU and memory usage **only** for pods that have anomalies.

        :param cpu_data: JSON response containing CPU usage metrics
        :param memory_data: JSON response containing memory usage metrics
        """
        cpu_threshold = self.cpu_threshold
        memory_threshold = self.memory_threshold
        consecutive_datapoints = self.app_consecutive_datapoints
        skip_memory_anomaly = self.skip_memory_anomaly
        skip_cpu_anomaly = self.skip_cpu_anomaly
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

        def detect_anomalies(values, threshold=80):
            anomalies = []
            count = 0  # Counter to track consecutive threshold breaches
            for i in range(len(values) - 1):
                if values[i] > threshold:
                    count += 1
                    if count >= consecutive_datapoints:
                        anomalies.append(i)
                else:
                    count = 0  
            return anomalies
        

        def convert_epoch_to_time(epoch_list):
            """Convert epoch timestamps to human-readable time format in Indian Standard Time (IST)."""
            return [
                (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%H:%M')
                for ts in epoch_list
            ]
        saved_files = []
        os.makedirs(output_dir, exist_ok=True)
        cpu_pod_data = extract_values(cpu_data)
        mem_pod_data = extract_values(memory_data)
        pods = set(cpu_pod_data.keys()).union(mem_pod_data.keys())
        pods = pods.intersection(istio_error_pods)
        for pod in pods:
                if any (pod.startswith(service) for service in skip_cpu_anomaly) or any (pod.startswith(service) for service in skip_memory_anomaly):
                    continue
            # cpu_anomalies, mem_anomalies = [], []

            # Check CPU anomalies
            # if pod in cpu_pod_data and not any (pod.startswith(service) for service in skip_cpu_anomaly):
            #     cpu_anomalies = detect_anomalies(cpu_pod_data[pod]["values"], cpu_threshold)
            # # Check Memory anomalies
            # if pod in mem_pod_data and not any (pod.startswith(service) for service in skip_memory_anomaly):
            #     mem_anomalies = detect_anomalies(mem_pod_data[pod]["values"], memory_threshold)

            # **Plot only if there are anomalies**
            # if cpu_anomalies or mem_anomalies:
                plt.figure(figsize=(12, 6))
                if pod in cpu_pod_data:
                    cpu_timestamps = convert_epoch_to_time(cpu_pod_data[pod]["timestamps"])
                    cpu_values = cpu_pod_data[pod]["values"]
                    cpu_numeric_timestamps = list(range(len(cpu_timestamps)))
                    plt.plot(cpu_numeric_timestamps, cpu_values, label="CPU Usage (%)", marker='o', linestyle="-", color='blue')

                    # if cpu_anomalies:
                    #     plt.scatter([cpu_numeric_timestamps[i] for i in cpu_anomalies], 
                    #                 [cpu_values[i] for i in cpu_anomalies], color='red', zorder=3, label="CPU Anomalies")

                if pod in mem_pod_data:
                    mem_timestamps = convert_epoch_to_time(mem_pod_data[pod]["timestamps"])
                    mem_values = mem_pod_data[pod]["values"]
                    mem_numeric_timestamps = list(range(len(mem_timestamps)))
                    plt.plot(mem_numeric_timestamps, mem_values, label="Memory Usage (%)", marker='o', linestyle="-", color='green')
                    # if mem_anomalies:
                    #     plt.scatter([mem_numeric_timestamps[i] for i in mem_anomalies], 
                    #                 [mem_values[i] for i in mem_anomalies], color='red', zorder=3, label="Memory Anomalies")

                plt.xlabel("Timestamp")
                plt.xticks(range(0, len(cpu_numeric_timestamps), 2), cpu_timestamps[::2], rotation=45, ha="right")
                plt.ylabel("Usage (%)")
                plt.title(f"CPU & Memory Usage for: {pod} - {cpu_pod_data[pod]['node']}")
                plt.axhline(y=cpu_threshold, color='pink', linestyle='--', label=f"CPU Threshold: {cpu_threshold}%")
                plt.axhline(y=memory_threshold, color='orange', linestyle='--', label=f"Memory Threshold: {memory_threshold}%")
                plt.legend()
                plt.grid(True, linestyle="--", alpha=0.5)
                
                plt.tight_layout()
                # plt.show()
                file_path = os.path.join(output_dir, f"{pod}_anomalies.png")
                plt.savefig(file_path)
                plt.close()
                saved_files.append(file_path)
        return saved_files




    def fetch_all_prom_metrics(self, start_time=None, end_time=None):
        """Fetch all application and Istio metrics."""
        app_metrics = self.fetch_application_request_metrics(start_time, end_time)
        istio_metrics,_ = self.fetch_istio_metrics(start_time, end_time)

        result = {
            "application_metrics": app_metrics,
            "istio_metrics": istio_metrics
        }
        return result
    

    def fetch_all_5xx__0DC_prom_metrics(self, start_time=None, end_time=None):
        """
        Fetch all application and Istio metrics.
        """

        def extract_data(metric_data):
            """Extract timestamps, values, and pods from metric data."""
            if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
                return {}
            service_data = {}
            for series in metric_data["data"]["result"]:
                service_name = series["metric"].get("destination_service_name", "unknown")
                response_code = series["metric"].get("response_code", "unknown")
                if response_code.startswith("5"):
                    response_code = "5xx"
                elif response_code.startswith("0"):
                    response_code = "0DC"
                else:
                    response_code = response_code
                key = f"{service_name}"
                key = key.strip()
                timestamps, values = zip(*[(int(timestamp), float(value)) for timestamp, value in series["values"]])
                if key not in service_data:
                    service_data[key] = {}
                service_data[key][response_code] = {"timestamps": list(timestamps), "values": list(values)}
            return service_data
        
        def check_anomalies(values, threshold=100):
            anomalies = []
            point_sum = 0
            max_sum = 0
            count = 0
            for i in range(len(values)):
                if values[i] > threshold:
                    count += 1
                    if count >= self.error_consecutive_datapoints:
                        anomalies.append(i)
                        point_sum += values[i]
                else:
                    max_sum = max(max_sum, point_sum)
                    point_sum = 0
                    count = 0
            max_sum = max(max_sum, point_sum)
            return anomalies, max_sum
        
        def should_skip_error_check(pod_name):
            return any(pod_name.startswith(service) for service in self.skip_error_check_services)

        def filter_pod_wise_errors(data, threshold_5xx=10, threshold_0dc=10):
            pods_data = {}
            for pod, values in data.items():
                errors_5xx = values.get("5xx", 0)
                errors_0dc = values.get("0DC", 0)
                if (errors_5xx > threshold_5xx or errors_0dc > threshold_0dc) and not should_skip_error_check(pod):
                    pods_data[pod] = values
            return pods_data
        
        istio_metrics,istio_data_points = self.fetch_istio_metrics(start_time, end_time)
        filtered_istio_metrics ={}
        filtered_5xx = []
        filtered_0DC = []
        affected_services = []
        extracted_istio_metrics = extract_data(istio_data_points)
        for service, data in extracted_istio_metrics.items():
            if data.get("5xx") and service not in self.skip_error_check_services:
                anomalies,max_5xx_count = check_anomalies(data["5xx"]["values"], self.ERROR_5XX_THRESHOLD)
                if anomalies:
                    filtered_5xx.append({service: anomalies})
                    filtered_istio_metrics[service] = istio_metrics[service]
                    filtered_istio_metrics[service]["5xx_max"] = max_5xx_count
                    affected_services.append(service)
                    
            if data.get("0DC") and service not in self.skip_error_check_services:
                anomalies,max_0dc_count = check_anomalies(data["0DC"]["values"], self.ERROR_0DC_THRESHOLD)
                if anomalies:
                    filtered_0DC.append({service: anomalies})
                    filtered_istio_metrics[service] = istio_metrics[service]
                    filtered_istio_metrics[service]["0DC_max"] = max_0dc_count
                    affected_services.append(service)
        result = {
            "5xx": filtered_5xx,
            "0DC": filtered_0DC
        }
        istio_pod_wise_errors = self.fetch_istio_metrics_pod_wise_errors(start_time, end_time,service_names=affected_services)
        istio_pod_wise_errors = filter_pod_wise_errors(istio_pod_wise_errors, threshold_5xx=self.ERROR_5XX_THRESHOLD, threshold_0dc=self.ERROR_0DC_THRESHOLD)
        return result, filtered_istio_metrics, istio_pod_wise_errors
    
    def get_5xx_or_0dc_graph(self, service_metrics=None, istio_pod_wise_errors = None,start_time=None, end_time=None,output_dir="anomaly_plots"):
        """
        Fetch all application and Istio metrics.
        """
        # Extract services that have 5xx or 0DC errors
        services_5xx = {service for entry in service_metrics.get("5xx", []) for service in entry.keys()}
        services_0DC = {service for entry in service_metrics.get("0DC", []) for service in entry.keys()}

        services = services_5xx | services_0DC  # Union of both sets (ensures uniqueness)

        cpu_memory_data = {}
        pod_anomalies = {}
        api_anomalies = []
        total_requests_data = None
        istio_error_pods = list(istio_pod_wise_errors.keys())

        # Fetch CPU and memory data only for services that have 0DC errors
        if services_0DC:
            cpu_memory_data = {
                service: {
                    "cpu": data[0],
                    "memory": data[1]
                }
                for service in services_0DC
                if (data := self.fetch_individual_cpu_and_memory(start_time, end_time, services=service))
            }

        if services:
            query = (
                f"sum(increase(http_request_duration_seconds_count{{"
                f"service=~\"{'|'.join(services)}\", status_code=~\"5[0-9]{{2}}\"}}[1m])) "
                "by (method, handler, service, status_code)"
            )
            print(f"🚀 Fetching 5xx or 0DC Error Query: {query}\n")
            start, end = self.time_to_epoch(start_time, end_time)
            total_requests_data = self.fetch_metric(query, start, end, self.query_step_range)

        for service, data in cpu_memory_data.items():
            res = self.detect_and_plot_mem_cpu_anomalies_per_pod(data["cpu"], data["memory"], output_dir, istio_error_pods)
            if res:
                pod_anomalies[service] = res

        # Detect API anomalies if request data is available
        if total_requests_data:
            api_anomalies = self.detect_and_plot_api_error_anomalies(total_requests_data, output_dir)
        return {"pod_anomalies": pod_anomalies, "api_anomalies": api_anomalies}

    def detect_and_plot_api_error_anomalies(self, api_data, output_dir="anomaly_plots"):
        """
        Detects anomalies where n consecutive data points exceed the threshold
        and plots API error rates for services that have anomalies.
        
        :param api_data: JSON response containing API error metrics
        """
        saved_files = []
        api_5xx_threshold = self.API_5XX_THRESHOLD
        def check_anomalies(values, threshold=10):
            """Check for anomalies in API error rates."""
            anomalies = []
            count = 0
            for i in range(len(values)):
                if values[i] > threshold:
                    count += 1
                    if count >= self.error_consecutive_datapoints:
                        anomalies.append(i)
                else:
                    count = 0
            return anomalies
        
        def convert_epoch_to_time(epoch_list):
            """Convert epoch timestamps to human-readable time format in Indian Standard Time (IST)."""
            return [
                (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%H:%M')
                for ts in epoch_list
            ]
        
        def extract_values(metric_data):
            """Extract timestamps, values, and pods from metric data."""
            if not metric_data or "data" not in metric_data or "result" not in metric_data["data"]:
                return {}
            api_data = {}
            for series in metric_data["data"]["result"]:
                api = series["metric"].get("handler", "")
                method = series["metric"].get("method", "")
                service = series["metric"].get("service", "")
                status_code = series["metric"].get("status_code", "")
                key = f"{method} {service} {api} {status_code}"
                key = key.strip()
                timestamps, values = zip(*[(int(timestamp), float(value)) for timestamp, value in series["values"]])
                api_data[key] = {"timestamps": list(timestamps), "values": list(values)}
            return api_data

        os.makedirs(output_dir, exist_ok=True)
        api_data = extract_values(api_data)
        for key, data in api_data.items():
            timestamps = data["timestamps"]
            values = data["values"]
            anomalies = check_anomalies(values, api_5xx_threshold)
            if anomalies:
                plt.figure(figsize=(12, 6))
                timestamps = convert_epoch_to_time(timestamps)
                numeric_timestamps = list(range(len(timestamps)))  # Create sequential indices

                plt.plot(numeric_timestamps, values, label="Error Count", marker='o', linestyle="-", color='red')
                plt.scatter([numeric_timestamps[i] for i in anomalies], 
                            [values[i] for i in anomalies], color='red', zorder=3, label="Anomalies")

                plt.xticks(numeric_timestamps[::2], timestamps[::2], rotation=45, ha="right")
                plt.xlabel("Timestamp")
                plt.xticks(range(0, len(timestamps), 2), timestamps[::2], rotation=45, ha="right")
                plt.ylabel("Error Count")
                plt.title(f"Error Rate for: {key}")
                plt.axhline(y=api_5xx_threshold, color='orange', linestyle='--', label=f"5xx Count Threshold: {api_5xx_threshold}")
                plt.legend()
                plt.grid(True, linestyle="--", alpha=0.5)
                plt.tight_layout()
                # plt.show()
                newkey=key.replace("/","")
                file_path = os.path.join(output_dir, f"{newkey}_anomalies.png")
                plt.savefig(file_path)
                plt.close()
                saved_files.append(file_path)
        return saved_files
    
        

    def detect_application_istio_anomalies(self, current_data, past_data):
        """Detect anomalies by comparing current and past metrics."""
        anomalies = []
        threshold_config = {
            "APPLICATION_METRICS": self.application_metrics,  # Loaded from config
            "ISTIO_METRICS": self.istio_metrics  # Loaded from config
        }

        # Function to detect anomalies for a given dataset (either application_metrics or istio_metrics)
        def check_anomalies(metrics_type, current_metrics, past_metrics, thresholds):
            request_thresholds = thresholds["REQUEST_COUNT_THRESHOLDS"]
            percentage_thresholds = thresholds["PERCENTAGE_CHANGE_THRESHOLDS"]

            for service, current_service_metrics in current_metrics.items():
                past_service_metrics = past_metrics.get(service, {})

                if not past_service_metrics:
                    continue  # Skip if no past data available for comparison

                for status_code, current_value in current_service_metrics.items():
                    past_value = past_service_metrics.get(status_code, 0)

                    if past_value == 0 or status_code not in request_thresholds:
                        continue  # Skip if no past value to compare or status code not defined

                    percentage_change = ((current_value - past_value) / past_value) * 100
                    min_request_threshold = request_thresholds[status_code]
                    change_threshold = percentage_thresholds[status_code]

                    # Apply conditions based on configured thresholds
                    if current_value <= min_request_threshold:
                        continue  # Skip if below minimum request threshold

                    if percentage_change > change_threshold:
                        anomalies.append({
                            "MetricsType": metrics_type,
                            "Service/API": service,
                            "Issue": f"High increase in {status_code} requests in {service}",
                            "StatusCode": status_code,
                            "Current_Avg": current_value,
                            "Past_Avg": past_value,
                            "Percentage Change": round(percentage_change, 2),
                            "Threshold": change_threshold
                        })

        # Check anomalies in application_metrics
        check_anomalies("Application API Metrics", current_data.get("application_metrics", {}), 
                        past_data.get("application_metrics", {}), threshold_config["APPLICATION_METRICS"])

        # Check anomalies in istio_metrics
        check_anomalies("Service Metrics", current_data.get("istio_metrics", {}), 
                        past_data.get("istio_metrics", {}), threshold_config["ISTIO_METRICS"])

        return anomalies
    

