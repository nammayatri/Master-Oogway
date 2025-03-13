import json
import time
from load_config import load_config
from rds_metrics import RDSMetricsFetcher
from redis_metrics import RedisMetricsFetcher
from deployment_checker import DeploymentChecker
from application_metrics import ApplicationMetricsFetcher
from datetime import datetime, timedelta
import pytz
from slack import SlackMessenger
from time_function import TimeFunction


class MetricsFetcher:
    def __init__(self):
        """Initialize all metric fetchers using the loaded configuration."""
        self.config = load_config()
        self.rds_fetcher = RDSMetricsFetcher(self.config)
        self.redis_fetcher = RedisMetricsFetcher(self.config)
        self.deployment_checker = DeploymentChecker(self.config)
        self.app_metrics_fetcher = ApplicationMetricsFetcher(self.config)
        self.slack = SlackMessenger(self.config)
        self.time_function = TimeFunction(self.config)

    def execute_in_try_catch(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
        
    def resolve_datetime(self, days_before=None, target_hour=None, target_minute=None, start_date_time=None, end_date_time=None):
        if start_date_time and end_date_time:
            print("Start and End Date Time Provided",start_date_time,end_date_time)
            return start_date_time, end_date_time
        time_delta = self.config.get("TIME_DELTA", {"hours": 1})
        days_before = days_before or self.config.get("TIME_OFFSET_DAYS", 7)
        target_hour = target_hour or self.config.get("TARGET_HOURS", 12)
        target_minute = target_minute or self.config.get("TARGET_MINUTES", 30)
        return self.time_function.get_target_datetime(days_before=days_before, target_hour=target_hour, target_minute=target_minute, time_delta=time_delta)

    # Function to fetch and analyze RDS metrics
    def fetch_and_analyze_rds_metrics(self, start_date_time=None, end_date_time=None):
        """Fetch and analyze RDS metrics."""
        print("\n🚀 Fetching & Analyzing RDS Metrics...")
        current_datetime, past_datetime = self.resolve_datetime(start_date_time=start_date_time, end_date_time=end_date_time)
        current_rds_metrics = self.rds_fetcher.fetch_rds_metrics(start_time=current_datetime[0], end_time=current_datetime[1])
        past_rds_metrics = self.rds_fetcher.fetch_rds_metrics(start_time=past_datetime[0], end_time=past_datetime[1])
        # print(f"Anamoly Detection for RDS Metrics", self.rds_fetcher.detect_rds_anomalies(current_rds_metrics, past_rds_metrics))
        anomaly = self.rds_fetcher.detect_rds_anomalies(current_rds_metrics, past_rds_metrics)
        return anomaly

        # print(f"Current RDS Metrics: {current_rds_metrics}")
        # print(f"Past RDS Metrics: {past_rds_metrics}")

    # Function to fetch and analyze Redis metrics
    def fetch_and_analyze_redis_metrics(self, start_date_time=None, end_date_time=None):
        """Fetch and analyze Redis metrics."""
        print("\n🚀 Fetching & Analyzing Redis Metrics...")
        current_datetime, past_datetime = self.resolve_datetime(start_date_time=start_date_time, end_date_time=end_date_time)
        current_redis_metrics = self.redis_fetcher.get_all_redis_cluster_metrics(metrics_start_time=current_datetime[0], metrics_end_time=current_datetime[1])
        past_redis_metrics = self.redis_fetcher.get_all_redis_cluster_metrics(metrics_start_time=past_datetime[0], metrics_end_time=past_datetime[1])
        print(f"Anamoly Detection for Redis Metrics", self.redis_fetcher.detect_anomalies(current_redis_metrics, past_redis_metrics))
        anomaly = self.redis_fetcher.detect_anomalies(current_redis_metrics, past_redis_metrics)
        return anomaly

        # print(f"Current Redis Metrics: {current_redis_metrics}")
        # print(f"Past Redis Metrics: {past_redis_metrics}")

    def get_recent_active_deployments(self):
        """Fetch ACTIVE deployments created between `TIME_OFFSET_DAYS` and now."""
        print("\n🚀 Fetching Recent Active Deployments...")
        active_deployments = self.deployment_checker.get_recent_active_deployments()
        print(f"Recent Active Deployments: {active_deployments}")
        return active_deployments

    def fetch_and_analyze_application_and_istio_metrics(self, start_date_time=None, end_date_time=None):
        """Fetch and analyze application and Istio metrics."""
        print("\n🚀 Fetching & Analyzing Application & Istio Metrics...")
        current_datetime, past_datetime = self.resolve_datetime(start_date_time=start_date_time, end_date_time=end_date_time)
        current_app_metrics = self.app_metrics_fetcher.fetch_all_prom_metrics(start_time=current_datetime[0], end_time=current_datetime[1])
        past_app_metrics = self.app_metrics_fetcher.fetch_all_prom_metrics(start_time=past_datetime[0], end_time=past_datetime[1])
        # print(f"Anamoly Detection for Application Metrics", self.app_metrics_fetcher.detect_anomalies(current_app_metrics, past_app_metrics))
        anomaly = self.app_metrics_fetcher.detect_application_istio_anomalies(current_app_metrics, past_app_metrics)
        return anomaly

        # print(f"Current Application Metrics: {current_app_metrics}")
        # print(f"Past Application Metrics: {past_app_metrics}")
    def get_ride_to_search_metrics(self,start_date_time=None,end_date_time=None,output_dir="anomaly_graphs"):
        print("\n🚀 Fetching & Analyzing Ride to Search Metrics...")
        current_datetime, past_datetime = self.resolve_datetime(start_date_time=start_date_time, end_date_time=end_date_time)
        get_search_to_ride_metrics_current , _ = self.app_metrics_fetcher.get_search_to_ride_metrics(start_time=current_datetime[0], end_time=current_datetime[1],output_dir=output_dir)
        get_search_to_ride_metrics_past , _ = self.app_metrics_fetcher.get_search_to_ride_metrics(start_time=past_datetime[0], end_time=past_datetime[1],output_dir=output_dir)
        return get_search_to_ride_metrics_current,get_search_to_ride_metrics_past

    def fetch_and_analyze_all_metrics(self, time_offset_days=None, target_hours=None, target_minutes=None, start_date_time=None, end_date_time=None, thread_ts=None, channel_id=None, now_time_delta=None, time_delta=None):
        """Fetch and analyze all system metrics, and send Slack alerts if anomalies are detected."""
        print("\n🚀 Fetching & Analyzing All Metrics...")
        # Fetch anomalies
        if time_delta is None:
            time_delta = self.config.get("TIME_DELTA", {"hours": 1})
        else:
            time_delta = {"hours": time_delta}

        if any([time_offset_days, target_hours, target_minutes]):
            start_date_time, end_date_time = self.time_function.get_target_datetime(days_before=time_offset_days, target_hour=target_hours, target_minute=target_minutes, now_time_delta=now_time_delta, time_delta=time_delta)
            print(f"Start Date Time: {start_date_time[0].strftime('%Y-%m-%d %H:%M:%S')} → {start_date_time[1].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"End Date Time: {end_date_time[0].strftime('%Y-%m-%d %H:%M:%S')} → {end_date_time[1].strftime('%Y-%m-%d %H:%M:%S')}")
        rds_anomaly = self.fetch_and_analyze_rds_metrics(start_date_time,end_date_time)
        redis_anomaly = self.fetch_and_analyze_redis_metrics(start_date_time,end_date_time)
        application_anomaly = self.fetch_and_analyze_application_and_istio_metrics(start_date_time,end_date_time)
        output_dir = "anomaly_graphs" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        ride_to_search_anomaly_current, ride_to_search_anomaly_past = self.get_ride_to_search_metrics(start_date_time,end_date_time,output_dir)
        active_deployments = []
        if any(len(anomaly) > 0 for anomaly in [rds_anomaly, redis_anomaly, application_anomaly]):
            active_deployments = self.get_recent_active_deployments()
            file_path = self.slack.create_anomaly_pdf({"rds_anomaly": rds_anomaly, "redis_anomaly": redis_anomaly, "application_anomaly": application_anomaly, "active_deployments": active_deployments,"search_to_ride_metrics":[ride_to_search_anomaly_current,ride_to_search_anomaly_past]}, start_date_time, end_date_time)
            self.slack.send_pdf_report_on_slack(file_path=file_path, thread_ts=thread_ts, channel_id=channel_id)
        else:
            print("No anomalies detected in the specified time range 🚫.")
        self.app_metrics_fetcher.delete_directory(output_dir)
        return

    def get_current_metrics (self,start_time=None,end_time=None,time_delta=None,thread_ts=None,channel_id=None):
        current_time,end_time = self.time_function.get_current_fetch_time(start_time,end_time,time_delta)
        print(f"Current Time: {current_time} → {end_time}")
        current_rds_metrics = self.rds_fetcher.fetch_rds_metrics(start_time=current_time, end_time=end_time)
        current_redis_metrics = self.redis_fetcher.get_all_redis_cluster_metrics(metrics_start_time=current_time, metrics_end_time=end_time)
        current_app_metrics = self.app_metrics_fetcher.fetch_all_prom_metrics(start_time=current_time, end_time=end_time)
        output_dir = "anomaly_graphs" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        ride_to_search_metrics_current, _ = self.app_metrics_fetcher.get_search_to_ride_metrics(start_time=current_time, end_time=end_time, output_dir=output_dir)
        data = {"rds_metrics":current_rds_metrics,"redis_metrics":current_redis_metrics,"application_metrics":current_app_metrics,"search_to_ride_metrics":ride_to_search_metrics_current,"start":self.time_function.convert_time(current_time.strftime("%Y-%m-%d %H:%M:%S")),"end":self.time_function.convert_time(end_time.strftime("%Y-%m-%d %H:%M:%S"))}
        self.slack.generate_current_report_and_send_on_slack(data,thread_ts=thread_ts,channel_id=channel_id)
        self.app_metrics_fetcher.delete_directory(output_dir)
        return data

    def generate_slack_alert_text(self, metrics_data, pod_metrics, start_time=None, end_time=None):
        alert_messages = []
        print(metrics_data, pod_metrics, start_time, end_time, "-------------------Metrics Data")
        # Include time range if provided
        if start_time and end_time:
            alert_messages.append(
                f"📊 *Metrics Summary:* ⏰ {start_time} → {end_time}")

        # No errors case
        if not metrics_data:
            if not pod_metrics:
                return f"✅ No errors were detected in the time range ({start_time} → {end_time}) 🎉."
            else:
                Threshold_5xx = self.config.get("ERROR_5XX_THRESHOLD", 200)
                Threshold_0DC = self.config.get("ERROR_0DC_THRESHOLD", 200)
                alert_messages.append(f"⚠️ *Pod Errors Detected* in the time range ({start_time} → {end_time}) 🚨\n")
                for pod, metrics in pod_metrics.items():
                    print(f"Pod: {pod}, Metrics: {metrics}")
                    if metrics.get("0DC", 0) > Threshold_0DC or metrics.get("5xx", 0) > Threshold_5xx: 
                        alert_messages.append(
                            f"   - *Pod*: {pod}\n"
                            f"   - 0DC Errors: {metrics.get('0DC', 0)}\n"
                            f"   - 5xx Errors: {metrics.get('5xx', 0)}\n"
                        )
                return "\n".join(alert_messages)

        for service, metrics in metrics_data.items():
            total_5xx = metrics.get("5xx", 0)  # Total 5xx errors
            total_0DC = metrics.get("0DC", 0)  # Total 0DC errors
            max_5xx = int(metrics.get("5xx_max", 0))  # Continuous 5xx errors
            max_0DC = int(metrics.get("0DC_max", 0))  # Continuous 0DC errors

            # Detect significant continuous errors & compare with each other
            if max_5xx > 0 or max_0DC > 0:
                if max_5xx > max_0DC:
                    alert_messages.append(
                        f"🔴 *{service}* had a *continuous spike of 5xx errors* 🚨\n"
                        f"   - Max Consecutive 5xx: {max_5xx} (Total: {total_5xx})\n"
                        f"   - Total 0DC Errors: {total_0DC} (Max: {max_0DC})"
                    )
                elif max_0DC > max_5xx:
                    alert_messages.append(
                        f"⚠️ *{service}* had a *continuous surge in 0DC errors* 🛑\n"
                        f"   - Max Consecutive 0DC: {max_0DC} (Total: {total_0DC})\n"
                        f"   - Total 5xx Errors: {total_5xx} (Max: {max_5xx})"
                    )
                else:
                    alert_messages.append(
                        f"🔴⚠️ *{service}* had *sustained spikes in both 5xx and 0DC errors* 🚨\n"
                        f"   - Max 5xx: {max_5xx} (Total: {total_5xx})\n"
                        f"   - Max 0DC: {max_0DC} (Total: {total_0DC})"
                    )

        if not alert_messages:
            return "✅ No significant continuous errors detected."

        return "\n".join(alert_messages)

    def get_current_5xx_or_0DC(self, start_time=None, end_time=None, time_delta=None, thread_ts=None, channel_id=None):
        current_time, end_time = self.time_function.get_current_fetch_time(start_time, end_time, time_delta)
        metrix_5xx_or_0DC, istio_metrics, istio_pod_wise_errors = self.app_metrics_fetcher.fetch_all_5xx__0DC_prom_metrics(start_time=current_time, end_time=end_time)
        output_dir = "anomaly_graphs" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        result = self.app_metrics_fetcher.get_5xx_or_0dc_graph(metrix_5xx_or_0DC, istio_pod_wise_errors=istio_pod_wise_errors, start_time=current_time, end_time=end_time, output_dir=output_dir)
        current_time_ist, end_time_ist = self.time_function.convert_time(current_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC"), self.time_function.convert_time(end_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC")
        get_search_to_ride_metrics , _ = self.app_metrics_fetcher.get_search_to_ride_metrics(start_time=current_time, end_time=end_time, output_dir=output_dir)
        result["search_to_ride_metrics"] = get_search_to_ride_metrics
        slack_message = self.generate_slack_alert_text(istio_metrics,istio_pod_wise_errors, start_time=current_time_ist, end_time=end_time_ist)
        print("slack_message", slack_message)
        result["istio_metrics"] = istio_metrics
        result["istio_pod_wise_errors"] = istio_pod_wise_errors
        result["Start Time"] = self.time_function.convert_time(current_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC")
        result["End Time"] = self.time_function.convert_time(end_time.strftime("%Y-%m-%d %H:%M:%S"), from_tz="UTC")
        print(result["pod_anomalies"], result["api_anomalies"], len(result["pod_anomalies"]), len(result["api_anomalies"]), "-------------------Anomalies")
        if len(result["pod_anomalies"]) > 0 or len(result["api_anomalies"]) > 0 or len(result["search_to_ride_metrics"]) > 0 or len(result["istio_pod_wise_errors"]) > 0:
            self.slack.send_5xx_0dc_report(result, thread_ts=thread_ts, channel_id=channel_id, message=slack_message)
        else:
            self.slack.send_message(slack_message, thread_ts=thread_ts, channel=channel_id)
        self.app_metrics_fetcher.delete_directory(output_dir)
        self.app_metrics_fetcher.delete_directory(get_search_to_ride_metrics)
        return result


if __name__ == "__main__":
    metrics_fetcher = MetricsFetcher()
    metrics_fetcher.fetch_and_analyze_all_metrics()
    # metrics_fetcher.get_current_metrics()
    # (metrics_fetcher.get_current_5xx_or_0DC())  

