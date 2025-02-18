import json
from load_config import load_config
from rds_metrics import RDSMetricsFetcher
from redis_metrics import RedisMetricsFetcher
from deployment_checker import DeploymentChecker
from application_metrics import ApplicationMetricsFetcher
from datetime import datetime, timedelta
import pytz


class MetricsFetcher:
    def __init__(self):
        """Initialize all metric fetchers using the loaded configuration."""
        self.config = load_config()
        self.rds_fetcher = RDSMetricsFetcher(self.config)
        self.redis_fetcher = RedisMetricsFetcher(self.config)
        self.deployment_checker = DeploymentChecker(self.config)
        self.app_metrics_fetcher = ApplicationMetricsFetcher(self.config)


    # Function to fetch and analyze RDS metrics
    def fetch_and_analyze_rds_metrics(self):
        """Fetch and analyze RDS metrics."""
        print("\n🚀 Fetching & Analyzing RDS Metrics...")
        config = self.config
        RDS_TIME_DELTA = config.get("RDS_TIME_DELTA", {"hours": 1})
        TIME_OFFSET_DAYS = config.get("TIME_OFFSET_DAYS", 7)
        TARGET_HOURS = config.get("TARGET_HOURS", 12)
        TARGET_MINUTES = config.get("TARGET_MINUTES", 30)

        print(f"\nRDS_TIME_DELTA: {RDS_TIME_DELTA} | TIME_OFFSET_DAYS: {TIME_OFFSET_DAYS} | TARGET_HOURS: {TARGET_HOURS} | TARGET_MINUTES: {TARGET_MINUTES}")
                
        # Get the current and past datetime to fetch metrics
        current_datetime, past_datetime = self.get_target_datetime(days_before=TIME_OFFSET_DAYS, target_hour=TARGET_HOURS, target_minute=TARGET_MINUTES, time_delta=RDS_TIME_DELTA)

        current_rds_metrics = self.rds_fetcher.fetch_rds_metrics(start_time=current_datetime[0], end_time=current_datetime[1])
        past_rds_metrics = self.rds_fetcher.fetch_rds_metrics(start_time=past_datetime[0], end_time=past_datetime[1])
        # print(f"Anamoly Detection for RDS Metrics", self.rds_fetcher.detect_rds_anomalies(current_rds_metrics, past_rds_metrics))
        anomaly = self.rds_fetcher.detect_rds_anomalies(current_rds_metrics, past_rds_metrics)
        return {"rds_anomaly": anomaly}

        # print(f"Current RDS Metrics: {current_rds_metrics}")
        # print(f"Past RDS Metrics: {past_rds_metrics}")


    # Function to fetch and analyze Redis metrics
    def fetch_and_analyze_redis_metrics(self):
        """Fetch and analyze Redis metrics."""
        print("\n🚀 Fetching & Analyzing Redis Metrics...")
        config = self.config
        REDIS_TIME_DELTA = config.get("REDIS_TIME_DELTA", {"hours": 1})
        TIME_OFFSET_DAYS = config.get("TIME_OFFSET_DAYS", 7)
        TARGET_HOURS = config.get("TARGET_HOURS", 12)
        TARGET_MINUTES = config.get("TARGET_MINUTES", 30)

        print(f"REDIS_TIME_DELTA: {REDIS_TIME_DELTA} | TIME_OFFSET_DAYS: {TIME_OFFSET_DAYS} | TARGET_HOURS: {TARGET_HOURS} | TARGET_MINUTES: {TARGET_MINUTES}")

        # Get the current and past datetime to fetch metrics
        current_datetime, past_datetime = self.get_target_datetime(days_before=TIME_OFFSET_DAYS, target_hour=TARGET_HOURS, target_minute=TARGET_MINUTES, time_delta=REDIS_TIME_DELTA)

        current_redis_metrics = self.redis_fetcher.get_all_redis_cluster_metrics(metrics_start_time=current_datetime[0], metrics_end_time=current_datetime[1])
        past_redis_metrics = self.redis_fetcher.get_all_redis_cluster_metrics(metrics_start_time=past_datetime[0], metrics_end_time=past_datetime[1])
        print(f"Anamoly Detection for Redis Metrics", self.redis_fetcher.detect_anomalies(current_redis_metrics, past_redis_metrics))
        anomaly = self.redis_fetcher.detect_anomalies(current_redis_metrics, past_redis_metrics)
        return {"redis_anomaly": anomaly}

        # print(f"Current Redis Metrics: {current_redis_metrics}")
        # print(f"Past Redis Metrics: {past_redis_metrics}")

    def get_recent_active_deployments(self):
        """Fetch ACTIVE deployments created between `TIME_OFFSET_DAYS` and now."""
        print("\n🚀 Fetching Recent Active Deployments...")
        active_deployments = self.deployment_checker.get_recent_active_deployments()
        print(f"Recent Active Deployments: {active_deployments}")
        return active_deployments
    
    def fetch_and_analyze_application_and_istio_metrics(self):
        """Fetch and analyze application and Istio metrics."""
        print("\n🚀 Fetching & Analyzing Application & Istio Metrics...")
        config = self.config
        APP_TIME_DELTA = config.get("APP_TIME_DELTA", {"hours": 1})
        TIME_OFFSET_DAYS = config.get("TIME_OFFSET_DAYS", 7)
        TARGET_HOURS = config.get("TARGET_HOURS", 12)
        TARGET_MINUTES = config.get("TARGET_MINUTES", 30)

        print(f"APP_TIME_DELTA: {APP_TIME_DELTA} | TIME_OFFSET_DAYS: {TIME_OFFSET_DAYS} | TARGET_HOURS: {TARGET_HOURS} | TARGET_MINUTES: {TARGET_MINUTES}")

        # Get the current and past datetime to fetch metrics
        current_datetime, past_datetime = self.get_target_datetime(days_before=TIME_OFFSET_DAYS, target_hour=TARGET_HOURS, target_minute=TARGET_MINUTES, time_delta=APP_TIME_DELTA)

        current_app_metrics = self.app_metrics_fetcher.fetch_all_prom_metrics(start_time=current_datetime[0], end_time=current_datetime[1])
        past_app_metrics = self.app_metrics_fetcher.fetch_all_prom_metrics(start_time=past_datetime[0], end_time=past_datetime[1])
        # print(f"Anamoly Detection for Application Metrics", self.app_metrics_fetcher.detect_anomalies(current_app_metrics, past_app_metrics))
        anomaly = self.app_metrics_fetcher.detect_application_istio_anomalies(current_app_metrics, past_app_metrics)
        return {"app_anomaly": anomaly}

        # print(f"Current Application Metrics: {current_app_metrics}")
        # print(f"Past Application Metrics: {past_app_metrics}")

    # Function to get the target datetime for fetching metrics
    def get_target_datetime(self, days_before=7, target_hour=10, target_minute=0, time_delta={"hours": 1}):
        """
        Get a datetime object:
        - If `target_hour:target_minute` is earlier than the current time, return today's date with that time.
        - If `target_hour:target_minute` is later than the current time, return yesterday's date with that time.
        - Additionally, return `days_before` days ago with the same time.

        :param days_before: Number of days before today.
        :param target_hour: The target hour (0-23).
        :param target_minute: The target minute (0-59).
        :param time_delta: The time range in minutes for fetching metrics.
        :return: Tuple of ([current_start_time, current_end_time], [past_start_time, past_end_time])
        """
        now = datetime.now(pytz.utc)

        # Determine reference datetime (today or yesterday at target hour)
        if (target_hour, target_minute) <= (now.hour, now.minute):
            reference_datetime = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        else:
            reference_datetime = (now - timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Get the datetime from `days_before` days ago
        past_datetime = reference_datetime - timedelta(days=days_before)
        past_datetime = past_datetime.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        timedelta_range = timedelta(**time_delta)

        # Compute current and past time ranges
        current_start_time = reference_datetime - timedelta_range
        current_end_time = reference_datetime
        past_start_time = past_datetime - timedelta_range
        past_end_time = past_datetime

        print(f"✅ Current Start Time: {current_start_time} | Current End Time: {current_end_time}" )
        print(f"✅ Past Start Time: {past_start_time} | Past End Time: {past_end_time}\n" )

        return ([current_start_time, current_end_time], [past_start_time, past_end_time])


    # Function to convert time between UTC and IST 
    def convert_time(self, time_str, from_tz="UTC"):
        """
        Convert time between UTC and IST:
        - If from_tz="IST", it assumes the input is in IST and converts to UTC.
        - If from_tz="UTC", it assumes the input is in UTC and converts to IST.
        - If from_tz="Local", it assumes the input is in the system's local timezone.

        :param time_str: Time as a string (format: "YYYY-MM-DD HH:MM:SS.ssssss" or "YYYY-MM-DD HH:MM:SS")
        :param from_tz: Source timezone ("UTC", "IST", or "Local")
        :return: Converted time as a string in "YYYY-MM-DD HH:MM:SS.ssssss"
        """
        ist_tz = pytz.timezone("Asia/Kolkata")
        utc_tz = pytz.utc

        if from_tz == "IST":
            from_zone = ist_tz
            to_zone = utc_tz  # Convert IST → UTC
        elif from_tz == "UTC":
            from_zone = utc_tz
            to_zone = ist_tz  # Convert UTC → IST
        else:
            raise ValueError("Invalid timezone. Use 'UTC', or 'IST'.")
        try:
            time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f") 
        except ValueError:
            time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")  

        time_obj = from_zone.localize(time_obj) 
        converted_time = time_obj.astimezone(to_zone) 
        return converted_time.strftime("%Y-%m-%d %H:%M:%S.%f") 

if __name__ == "__main__":
    fetcher = MetricsFetcher()
    current_datetime, past_datetime = fetcher.get_target_datetime()
    rds_anomaly = fetcher.fetch_and_analyze_rds_metrics()
    redis_anomaly = fetcher.fetch_and_analyze_redis_metrics()
    application_anomaly = fetcher.fetch_and_analyze_application_and_istio_metrics()
    # if any anomaly the check if deployment has been done 
    active_deployments = fetcher.get_recent_active_deployments()