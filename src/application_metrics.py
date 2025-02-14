import requests

class ApplicationMetricsFetcher:
    def __init__(self, config):
        """
        Initialize the VictoriaMetrics API fetcher.
        """
        self.api_list = config.get("API_LIST", [])  # List of API paths
        self.vmselect_url = config.get("VMSELECT_URL", f"http://localhost:8481/select/0/prometheus/api/v1")
        self.query_step_range = config.get("QUERY_STEP_RANGE", "10m")

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
        start_time = start_time if isinstance(start_time, int) else int(start_time.timestamp())
        end_time = end_time if isinstance(end_time, int) else int(end_time.timestamp())

        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time must be provided.")
        
        start, end = start_time, end_time
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
        start_time = start_time if isinstance(start_time, int) else int(start_time.timestamp())
        end_time = end_time if isinstance(end_time, int) else int(end_time.timestamp())

        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time must be provided.")
        
        start, end = start_time, end_time

        # **🔹 Total Request Count (All 2xx,3xx,4xx,5xx)
        total_istio_requests_query = f"sum(increase(istio_requests_total{{destination_service_name!=\"istio-telemetry\", reporter=\"destination\"}}[{self.query_step_range}])) by (destination_service_name, response_code)"
        print("🚀 Fetching Total Isto request service level: ", total_istio_requests_query,"\n")
        total_istio_requests = self.fetch_metric(total_istio_requests_query, start, end,self.query_step_range)
        aggregated_istio_requests = self.aggregate_istio_metric_by_labels(total_istio_requests)

        return aggregated_istio_requests
    
    def fetch_istio_metrics_pod_wise_errors(self, start_time=None, end_time=None):
        start_time = start_time if isinstance(start_time, int) else int(start_time.timestamp())
        end_time = end_time if isinstance(end_time, int) else int(end_time.timestamp())
        if not start_time or not end_time:
            raise ValueError("Both start_time and end_time must be provided.")
        
        start, end = start_time, end_time

        # **🔹 Total Request Count (All 2xx,3xx,4xx,5xx)
        total_istio_requests_query = f"sum by (destination_service_name, pod, response_code, response_flags) ((label_replace(increase(istio_requests_total{{response_code!~\"(2..|3..|4..)\", destination_service_name!=\"istio-telemetry\", reporter=\"destination\"}}[{self.query_step_range}]), \"pod_ip\", \"$1\", \"instance\", \"^(.*):[0-9]+$\") * on (pod_ip) group_left(pod) (max by (pod_ip, pod) (kube_pod_info))))"
        print("🚀 Fetching Total Isto request erros pod level: ", total_istio_requests_query,"\n")
        total_istio_requests = self.fetch_metric(total_istio_requests_query, start, end,self.query_step_range)
        aggregated_istio_requests = self.aggregate_istio_metric_by_labels(total_istio_requests)
        return aggregated_istio_requests
    

    def fetch_all_prom_metrics(self, start_time=None, end_time=None):
        """
        Fetch all critical application-level API metrics and calculate totals.
        """
        app_metrics = self.fetch_application_request_metrics(start_time, end_time)
        istio_metrics = self.fetch_istio_metrics(start_time, end_time)
        istio_pod_wise_errors = self.fetch_istio_metrics_pod_wise_errors(start_time, end_time)

        result = {
            "application_metrics": app_metrics,
            "istio_metrics": istio_metrics,
            "istio_pod_wise_errors": istio_pod_wise_errors
        }
        return result
        
    
    

