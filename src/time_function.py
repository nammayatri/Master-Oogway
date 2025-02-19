import datetime
import pytz
from datetime import datetime, timedelta

class TimeFunction:
    def __init__(self):
        pass
        
    def get_target_datetime(self, days_before=None, target_hour=None, target_minute=None, time_delta=None):
        """
        Get a datetime object:
        - If `target_hour:target_minute` is earlier than the current time, return today's date with that time.
        - If `target_hour:target_minute` is later than the current time, return yesterday's date with that time.
        - Additionally, return `days_before` days ago with the same time.

        :param days_before: Number of days before today.
        :param target_hour: The target hour (0-23).
        :param target_minute: The target minute (0-59).
        :param time_delta: Dictionary (e.g., {"hours": 1}) defining the time range for fetching metrics.
        :return: Tuple of ([current_start_time_utc, current_end_time_utc], [past_start_time_utc, past_end_time_utc])
        """
        # Default time range of 1 hour if None provided
        if time_delta is None:
            time_delta = {"hours": 1}
        ist = pytz.timezone("Asia/Kolkata")
        utc = pytz.utc
        now = datetime.now(ist)
        days_before = 0 if days_before is None else days_before
        target_hour = now.hour if target_hour is None else target_hour
        target_minute = now.minute if target_minute is None else target_minute

        # Determine reference datetime (today or yesterday at target hour)
        if (target_hour, target_minute) <= (now.hour, now.minute):
            reference_datetime = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        else:
            reference_datetime = (now - timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Get past datetime `days_before` days ago
        past_datetime = reference_datetime - timedelta(days=days_before)

        timedelta_range = timedelta(**time_delta)

        # Compute current and past time ranges
        current_start_time = reference_datetime - timedelta_range
        current_end_time = reference_datetime
        past_start_time = past_datetime - timedelta_range
        past_end_time = past_datetime

        # Convert all times to UTC
        current_start_time_utc = current_start_time.astimezone(utc)
        current_end_time_utc = current_end_time.astimezone(utc)
        past_start_time_utc = past_start_time.astimezone(utc)
        past_end_time_utc = past_end_time.astimezone(utc)

        # ✅ Print formatted datetime info
        print(f"🕒 **IST Times:**")
        print(f"   ➤ Current: {current_start_time.strftime('%Y-%m-%d %H:%M:%S')} → {current_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   ➤ Past: {past_start_time.strftime('%Y-%m-%d %H:%M:%S')} → {past_end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        print(f"\n🌍 **UTC Times:**")
        print(f"   ➤ Current: {current_start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} → {current_end_time_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   ➤ Past: {past_start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} → {past_end_time_utc.strftime('%Y-%m-%d %H:%M:%S')}\n")

        return ([current_start_time_utc, current_end_time_utc], [past_start_time_utc, past_end_time_utc])


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
        return converted_time.strftime("%Y-%m-%d %H:%M") 
    
    def get_current_fetch_time(self, start_time = None, end_time = None,time_delta = None):
        """
        Get the current time in UTC timezone.
        """
        ist_tz = pytz.timezone("Asia/Kolkata")
        utc_tz = pytz.utc
        time_delta_default = {"minutes": 30} if time_delta is None else {"minutes": time_delta}
        if start_time and end_time:
            # Here start_time and end_time are the time only we have to return date
            now = datetime.now(ist_tz)
            current_date = now.strftime("%Y-%m-%d")
            current_time = datetime.strptime(f"{current_date} {start_time}", "%Y-%m-%d %H:%M")
            end_time = datetime.strptime(f"{current_date} {end_time}", "%Y-%m-%d %H:%M")
            return current_time.astimezone(utc_tz), end_time.astimezone(utc_tz)
        elif start_time:
            # Here start_time is the time only we have to return date
            now = datetime.now(ist_tz)
            current_date = now.strftime("%Y-%m-%d")
            current_time = datetime.strptime(f"{current_date} {start_time}", "%Y-%m-%d %H:%M")
            return current_time.astimezone(utc_tz), now.astimezone(utc_tz)
        else:
            start = datetime.now(utc_tz) - timedelta(**time_delta_default)
            end = datetime.now(utc_tz)
            return start, end
        

    
if __name__ == "__main__":
    time_function = TimeFunction()
    a,b= time_function.get_current_time("10:00","11:00")
    print(a,b)
    a,b= time_function.get_current_time("10:00")
    print(a,b)
    a,b= time_function.get_current_time(time_delta=60)
    print(a,b)

