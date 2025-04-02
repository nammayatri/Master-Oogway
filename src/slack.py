import os
import re
import json
import tempfile
import logging
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, 
                                TableStyle, Image, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_CENTER
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from load_config import load_config
from time_function import TimeFunction
from master_oogway import get_master_oogway_quotes



class SlackMessenger:
    def __init__(self, config_data):
        """Initialize Slack Messenger with Slack API."""
        self.slack_token = config_data.get("SLACK_BOT_TOKEN")
        self.default_channel = config_data.get("SLACK_CHANNEL_ID")
        self.days = config_data.get("TIME_OFFSET_DAYS", 7)
        self.target_hour = config_data.get("TARGET_HOURS", 10)
        self.target_minute = config_data.get("TARGET_MINUTES", 0)
        self.time_delta = config_data.get("TIME_DELTA", {"hours": 1})
        self.time_function = TimeFunction(config_data)

        if not self.slack_token:
            raise ValueError("❌ Missing Slack Bot Token.")
        if not self.default_channel:
            raise ValueError("❌ Missing Slack Channel ID.")

        self.client = WebClient(token=self.slack_token)
        logging.basicConfig(level=logging.INFO)

    def send_message(self, text, channel=None, thread_ts=None):
        """Send a formatted Slack message."""
        channel = channel or self.default_channel
        text = self.slackify(text)
        try:
            result = self.client.chat_postMessage(
                channel=channel,
                text=text,  
                thread_ts=thread_ts,
                mrkdwn=True,  
                parse="full"  
            )
            return result
        except SlackApiError as e:
            logging.error(f"❌ Slack API Error: {e.response['error']}")
            return None

    def format_time(self, timestamp):
        """Helper function to format timestamps."""
        return self.time_function.convert_time(timestamp.strftime("%Y-%m-%d %H:%M:%S"), "UTC")

    def format_value(self,value, normal_style):
        if isinstance(value, list):
            if all(isinstance(item, dict) for item in value):  
                formatted_items = [
                    f"<br/><b>Metrics {i+1}:</b><br/>{json.dumps(item, indent=4, ensure_ascii=False).replace('\n', '<br/>')}" 
                    for i, item in enumerate(value)
                ]
                formatted_value = "<br/><br/>".join(formatted_items)
            else:
                formatted_value = ", ".join(str(item) for item in value) 
        elif isinstance(value, dict):
            formatted_value = json.dumps(value, indent=4, ensure_ascii=False).replace("\n", "<br/>")  
        else:
            formatted_value = str(value) 

        return Paragraph(f"<pre>{formatted_value}</pre>", normal_style)
    
    def slackify(self,text):
        if not text:
            return ""
            
        text = text.strip()
        code_blocks = {}
        code_pattern = r"```([\s\S]*?)```"
        code_matches = re.finditer(code_pattern, text)
        
        for i, match in enumerate(code_matches):
            placeholder = f"__CODE_BLOCK_{i}__"
            code_blocks[placeholder] = match.group(0)
            text = text.replace(match.group(0), placeholder)
        inline_code = {}
        inline_pattern = r"`([^`]+)`"
        inline_matches = re.finditer(inline_pattern, text)
        
        for i, match in enumerate(inline_matches):
            placeholder = f"__INLINE_CODE_{i}__"
            inline_code[placeholder] = match.group(0)
            text = text.replace(match.group(0), placeholder)
        text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
        text = re.sub(r"\*([^*]+)\*", r"_\1_", text)
        text = re.sub(r"^> (.+)$", r"> \1", text, flags=re.MULTILINE)
        text = re.sub(r"^- (.+)$", r"• \1", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"<\2|\1>", text)
        for placeholder, code_block in code_blocks.items():
            text = text.replace(placeholder, code_block)
        for placeholder, code in inline_code.items():
            text = text.replace(placeholder, code)
        
        return text
    
    def create_anomaly_pdf(self, data, start_date_time=None, end_date_time=None):
        """Generate a structured, multi-page PDF anomaly report."""
        if not start_date_time or not end_date_time:
            start_date_time, end_date_time = self.time_function.get_target_datetime(
                days_before=self.days, target_hour=self.target_hour, target_minute=self.target_minute, time_delta=self.time_delta
            )
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        file_path = temp_file.name

        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()

            # Custom Styles
            title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=24, textColor=colors.darkblue, spaceAfter=12)
            header_style = ParagraphStyle("HeaderStyle", parent=styles["Heading2"], fontSize=18, textColor=colors.darkred, spaceAfter=10, alignment=TA_CENTER)
            normal_style = styles["BodyText"]
            bold_style = ParagraphStyle("BoldStyle", parent=styles["BodyText"], fontSize=11, textColor=colors.black, bold=True)
            red_bold_style = ParagraphStyle("RedBoldStyle", parent=styles["BodyText"], fontSize=11, textColor=colors.red, bold=True)
            bold_style1 = ParagraphStyle("BoldStyle1", parent=styles["Heading2"], fontSize=12, textColor=colors.purple, bold=True)
            content = []
            content.append(Paragraph("🚀 Auto-Generated Anomaly Report", title_style))
            content.append(Spacer(1, 12))

            metadata = {
                "📅 Report Generated At": self.format_time(datetime.now(timezone.utc)),
                "🔍 Total Anomalies Detected": sum(len(v) for v in data.values() if isinstance(v, list)),
                "📌 Recent Deployments": len(data.get("active_deployments", [])),
                "🕒 Current Metrics Fetch Period": f"{self.format_time(start_date_time[0])} → {self.format_time(start_date_time[1])}",
                "📉 Past Metrics Fetch Period": f"{self.format_time(end_date_time[0])} → {self.format_time(end_date_time[1])}"
            }

            for key, value in metadata.items():
                content.append(Paragraph(f"{key}: {value}", bold_style1))
            content.append(Spacer(1, 12))

            self.add_section(content, "RDS Anomalies", data.get("rds_anomaly", []), header_style, normal_style, bold_style, red_bold_style)
            self.add_section(content, "Redis Anomalies", data.get("redis_anomaly", []), header_style, normal_style, bold_style, red_bold_style)
            self.add_section(content, "Application & Istio Anomalies", data.get("application_anomaly", []), header_style, normal_style, bold_style, red_bold_style)
            content.append(PageBreak())

            if "search_to_ride_metrics" in data:
                ride_to_search_metrics_current , ride_to_search_metrics_past = data["search_to_ride_metrics"]
                content.append(Paragraph("📌 Ride to Search Metrics", header_style))
                content.append(Spacer(1, 12))
                content.append(Paragraph("🔹 <b>Currrent Ride to Search Ratio Metrics</b>", bold_style))
                img = Image(ride_to_search_metrics_current, width=500, height=300)
                content.append(img)
                content.append(Spacer(1, 12))
                content.append(PageBreak())
                content.append(Spacer(1, 12))
                content.append(Paragraph("🔹 <b>Past Ride to Search Ratio Metrics</b>", bold_style))
                img = Image(ride_to_search_metrics_past, width=500, height=300)
                content.append(img)
                content.append(Spacer(1, 12))
                content.append(PageBreak())

            self.add_deployment_section(content, f"🚀 Deployments in past {self.days} days", data.get("active_deployments", []), header_style, normal_style)
            doc.build(content)
            logging.info(f"✅ PDF Report Generated: {file_path}")

        except Exception as e:
            logging.error(f"❌ Error creating PDF: {e}")

        return file_path
    

    def add_section(self, content, title, anomalies, header_style, normal_style, bold_style, red_bold_style, is_nested=False, level=0):
        """
        Recursively adds an anomaly section to the PDF with indentation, red-highlighted issue values, and separators.
        Now, each anomaly is displayed inside a bordered table.
        """
        if not anomalies:
            return
        if not is_nested:
            content.append(Paragraph(f"🔹 <b>{title}</b>", header_style))
            content.append(Spacer(1, 12))

        for anomaly in anomalies:
            if isinstance(anomaly, dict):
                table_data = []  # Store anomaly data for table representation

                for key, value in anomaly.items():
                    if isinstance(value, dict):
                        table_data.append([
                            Paragraph(f"{key}", normal_style),
                            Paragraph("🔽 Nested Details Below", normal_style)
                        ])
                        self.add_section(content, key, [value], header_style, normal_style, bold_style, red_bold_style, is_nested=True, level=level + 1)

                    elif isinstance(value, list):
                        table_data.append([
                            Paragraph(f"<b>{key}:</b>", red_bold_style),
                            self.format_value(value, bold_style)
                        ])
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                self.add_section(content, f"{key}", [item], header_style, normal_style, bold_style, red_bold_style, is_nested=True, level=level + 1)
                    else:
                        if "Issue" in key:
                            table_data.append([
                                Paragraph(f"<b>{key}:</b>", red_bold_style),
                                Paragraph(f"<font color='red'><b>{value}</b></font>", red_bold_style)
                            ])
                        else:
                            table_data.append([
                                Paragraph(f"<b>{key}:</b>", normal_style),
                                Paragraph(f"{value}", normal_style)
                            ])

                # **Create Table for Each Anomaly**
                table = Table(table_data, colWidths=[180, 360])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),  # Box around each anomaly
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))

                content.append(table)
                content.append(Spacer(1, 20))
                content.append(HRFlowable(width="100%", thickness=1, color=colors.black))
                content.append(Spacer(1, 20))  # Space after line

    def add_deployment_section(self, content, title, deployments, header_style, normal_style):
        """Add a structured table for active deployments."""
        if not deployments:
            return

        content.append(Paragraph(title, header_style))
        content.append(Spacer(1, 6))

        table_data = [["Deployment Name", "Created At", "Replicas"]]
        for deployment in deployments:
            table_data.append([deployment["name"], deployment["created_at"], str(deployment["available_replicas"])])

        table = Table(table_data, colWidths=[300, 150, 80])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))

        content.append(table)
        content.append(Spacer(1, 12))

    def send_pdf_report_on_slack(self, filename="Anomaly_Report.pdf",file_path=None,thread_ts=None,channel_id=None, message = None ):
        """Generate and send a PDF anomaly report to Slack."""
        initial_comment = (
            f"@here 🚨 *Master Oogway has returned with insights!* 🐢\n\n"
            f"{message or ("*Wisdom of the day:* " + get_master_oogway_quotes())}\n\n"
            f"📎 *The latest anomaly report is attached.*"
        )
        self.client.files_upload_v2(
            channel=channel_id or self.default_channel,
            file=file_path,
            filename=filename,
            title="🚨 "+filename,
            initial_comment=initial_comment,
            thread_ts=thread_ts
        )
        os.remove(file_path) 
        logging.info(f"✅ PDF Report Sent to Slack: {filename}")
        return file_path
    

    def generate_current_report_and_send_on_slack(self, data, filename="System_Metrics_Report.pdf", thread_ts=None, channel_id=None):
        """
        Generates a structured PDF report and sends it to Slack, embedding RDS and Redis graphs.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        file_path = temp_file.name

        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            wrap_style = ParagraphStyle(
                "wrap_style",
                fontSize=10,
                leading=12,
                textColor=colors.black,
                wordWrap="CJK",  # Enables word wrap for long text
            )
            # Custom Styles
            title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=20, textColor=colors.darkblue, spaceAfter=12, alignment=1, underline=True)
            header_style = ParagraphStyle("HeaderStyle", parent=styles["Heading2"], fontSize=16, textColor=colors.darkred, spaceAfter=10, alignment=1, underline=True)
            header_style1 = ParagraphStyle("HeaderStyle", parent=styles["Heading2"], fontSize=14, textColor=colors.magenta, spaceAfter=10, alignment=1, underline=True)
            bold_style = ParagraphStyle("BoldStyle", parent=styles["BodyText"], fontSize=12, textColor=colors.purple, bold=True)
            bold_style1 = ParagraphStyle("BoldStyle", parent=styles["BodyText"], fontSize=14, textColor=colors.black, bold=True)

            content = []

            # 🚀 Report Title
            content.append(Paragraph("🚀 System Metrics Report", title_style))
            content.append(Spacer(1, 10))

            # ✅ Report Metadata
            metadata = {
                " - Report Generated at": self.format_time(datetime.now(timezone.utc)),
                " - Monitoring Period": f"{data['start']} to {data['end']}",
            }

            for key, value in metadata.items():
                content.append(Paragraph(f"<b> {key} </b>: {value}", bold_style1))
            content.append(Spacer(1, 12))

            # 📊 **Add RDS Metrics**
            if "rds_metrics" in data:
                content.append(Paragraph("📌 RDS Metrics", header_style))
                content.append(Spacer(20, 20))
                for cluster, details in data["rds_metrics"].items():
                    content.append(Paragraph(f"🔹 <b> <u>{cluster} </u></b>", bold_style))
                    content.append(Spacer(1, 12))
                    table_data = [["Instance", "Role", "CPU%", "Connections"]]
                    for instance, values in details["Instances"].items():
                        table_data.append([
                            Paragraph(instance, wrap_style),
                            values["Role"],
                            f"{values['CPUUtilization']}%",
                            f"{values['DatabaseConnections']}"
                        ])
                    table = Table(table_data, colWidths=[200, 80, 80, 100])
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    content.append(table)
                    content.append(Spacer(1, 12))

            # 🔥 **Add Redis Metrics**
            if "redis_metrics" in data:
                content.append(Paragraph("📌 Redis Metrics", header_style))
                content.append(Spacer(1, 12))
                for cluster, nodes in data["redis_metrics"].items():
                    content.append(Paragraph(f"🔹 <b>{cluster}</b>", bold_style))
                    content.append(Spacer(1, 12))
                    table_data = [["Instance", "Role", "CPU%", "Memory%", "Capacity%"]]
                    for instance, values in nodes.items():
                        if isinstance(values, dict) and "CPUUtilization" in values:
                            table_data.append([
                                Paragraph(instance, wrap_style),
                                values["Role"],
                                f"{values['CPUUtilization']}%",
                                f"{values['MemoryUsage']}%",
                                f"{values['DatabaseCapacityUsage']}%",
                            ])
                    table = Table(table_data, colWidths=[200, 80, 80, 80, 80])
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    content.append(table)
                    content.append(Spacer(1, 12))
                    content.append(PageBreak())

            if "search_to_ride_metrics" in data:
                ride_to_search_metrics = data["search_to_ride_metrics"]
                content.append(Paragraph(" 📌 Ride to Search Metrics", header_style))
                content.append(Spacer(1, 12))
                img = Image(ride_to_search_metrics, width=500, height=300)
                content.append(img)
                content.append(Spacer(1, 12))
                content.append(PageBreak())

             # Embed RDS Graphs
            if "rds_graph" in data and data["rds_graph"]:
                content.append(Paragraph("📊 RDS Graphs", header_style))
                content.append(Spacer(1, 12))
                for graph_path in data["rds_graph"]:
                    if os.path.exists(graph_path):
                        img = Image(graph_path, width=500, height=300)
                        content.append(img)
                        content.append(Spacer(1, 12))
                content.append(PageBreak())

            # Embed Redis Graphs
            if "redis_graph" in data and data["redis_graph"]:
                content.append(Paragraph("📊 Redis Graphs", header_style))
                content.append(Spacer(1, 12))
                for graph_path in data["redis_graph"]:
                    if os.path.exists(graph_path):
                        img = Image(graph_path, width=500, height=300)
                        content.append(img)
                        content.append(Spacer(1, 12))
                content.append(PageBreak())

            # 📈 **Add Application Metrics**
            if "application_metrics" in data:
                content.append(Paragraph("📌 Application API Metrics", header_style))
                content.append(Spacer(1, 12))
                for metric, value in data["application_metrics"].items():
                    content.append(Paragraph(f"🔹 <b>{metric.upper()}</b>", header_style1))
                    content.append(Spacer(1, 12))
                    for service, status_codes in value.items():
                        content.append(Paragraph(f"🔸 <b>{service}</b>", bold_style))
                        content.append(Spacer(1, 12))
                        table_data = [["Status Code", "Requests"]]
                        for code, count in status_codes.items():
                            table_data.append([code, count])
                        table = Table(table_data, colWidths=[100, 100])
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ]))
                        content.append(table)
                        content.append(Spacer(1, 12))

            # ✅ Save PDF
            doc.build(content)
            logging.info(f"✅ PDF Report Generated: {file_path}")

        except Exception as e:
            logging.error(f"❌ Error creating PDF: {e}")
            return None

        try:
            self.send_pdf_report_on_slack(filename, file_path, thread_ts=thread_ts, channel_id=channel_id)
        except SlackApiError as e:
            logging.error(f"❌ Slack API Error (PDF Upload): {e.response['error']}")

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"🗑️ Deleted Temporary File: {file_path}")



    def generate_5xx_0dc_report(self,data, output_pdf="Anomaly_Report.pdf"):
        """
        Generates a structured PDF report from anomaly data.
        - Istio Metrics at the top.
        - Pod-wise errors in the middle.
        - Pod-wise anomalies at the bottom.
        """

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            output_pdf = temp_file.name
        doc = SimpleDocTemplate(output_pdf, pagesize=A4)
        styles = getSampleStyleSheet()
        content = []

        # Custom Styles
        title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=22, textColor=colors.darkblue, spaceAfter=12, alignment=1, underline=True)
        header_style = ParagraphStyle("HeaderStyle", parent=styles["Heading2"], fontSize=18, textColor=colors.darkred, spaceAfter=10, underline=True,alignment=1)
        bold_style = ParagraphStyle("BoldStyle", parent=styles["BodyText"], fontSize=12, textColor=colors.black, bold=True)
        bold_style1 = ParagraphStyle("BoldStyle", parent=styles["BodyText"], fontSize=16, textColor=colors.black, bold=True)
        wrap_style = ParagraphStyle(
                "wrap_style",
                fontSize=10,
                leading=12,
                textColor=colors.black,
                bold=True,
                wordWrap="CJK",  
            )

        # Report Title
        content.append(Paragraph("🚀 Current Anomaly Detection Report", title_style))
        content.append(Spacer(1, 12))

        # Report Metadata (Start & End Time)
        content.append(Paragraph(f"📅 <b>Start Time:</b> {data.get('Start Time', 'N/A')}", bold_style1))
        content.append(Paragraph(f"📅 <b>End Time:</b> {data.get('End Time', 'N/A')}", bold_style1))
        content.append(Spacer(1, 12))

        if "istio_metrics" in data and len(data["istio_metrics"]) > 0:
            content.append(Paragraph("🔹 Istio Metrics", header_style))
            content.append(Spacer(1, 6))

            table_data = [["Service", "2xx", "3xx", "4xx", "5xx", "0DC", "Unknown"]]  # Table Headers
            for service, metrics in data["istio_metrics"].items():
                table_data.append([
                    Paragraph(service, wrap_style),
                    metrics.get("2xx", 0),
                    metrics.get("3xx", 0),
                    metrics.get("4xx", 0),
                    metrics.get("5xx", 0),
                    metrics.get("0DC", 0),
                    metrics.get("unknown", 0),
                ])

            table = Table(table_data, colWidths=[200, 50, 50, 50, 50, 50, 50])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))

            content.append(table)
            content.append(Spacer(1, 12))
            content.append(PageBreak())

        if "istio_pod_wise_errors" in data and len(data["istio_pod_wise_errors"]) > 0:
            content.append(Paragraph("🔹 Pod Errors", header_style))
            content.append(Spacer(1, 6))

            pod_metric_table = [["Service", "4xx", "5xx", "0DC", "Unknown"]]
            for pod, metrics in data["istio_pod_wise_errors"].items():
                pod_metric_table.append([
                    Paragraph(pod, wrap_style),
                    metrics.get("4xx", 0),
                    metrics.get("5xx", 0),
                    metrics.get("0DC", 0),
                    metrics.get("unknown", 0),
                ])

            table = Table(pod_metric_table, colWidths=[220, 50, 50, 50, 50])
            table.setStyle(TableStyle([ 
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            content.append(table)
            content.append(Spacer(1, 12))
            content.append(PageBreak())

        if "search_to_ride_metrics" in data and len(data["search_to_ride_metrics"]) > 0:
            content.append(Paragraph("🔹 Search to Ride Metrics", header_style))
            content.append(Spacer(1, 6))
            img = Image(data["search_to_ride_metrics"], width=550, height=270)
            content.append(img)
            content.append(Spacer(1, 12))
            content.append(PageBreak())


        if "pod_anomalies" in data and len(data["pod_anomalies"]) > 0:
            content.append(Paragraph("🔹 Pods CPU/Memory Graph", header_style))
            content.append(Spacer(1, 6))

            for pod, image_paths in data["pod_anomalies"].items():
                content.append(Paragraph(f"<b>Service: {pod} </b>", header_style))
                content.append(Spacer(1, 6))

                for image_path in image_paths:
                    if os.path.exists(image_path):
                        img = Image(image_path, width=550, height=270)
                        content.append(img)
                        content.append(Spacer(1, 12))

            content.append(PageBreak())

        if "api_anomalies" in data and len(data["api_anomalies"]) > 0:
            content.append(Paragraph("🔹 API Anomalies", header_style))
            content.append(Spacer(1, 6))
            for image_path in data["api_anomalies"]:
                if os.path.exists(image_path):
                    img = Image(image_path, width=550, height=270)
                    content.append(img)
                    content.append(Spacer(1, 12))
            content.append(PageBreak())

        # Generate PDF
        doc.build(content)
        return output_pdf
    
    def send_5xx_0dc_report(self,data, filename="Current_Errors_Anomaly_Report.pdf",thread_ts=None,channel_id=None , message = None):
        """
        Generate a structured PDF report for 5xx and 0DC anomalies and send it to Slack.
        """
        print("\n🚀 Generating & Sending Current Anomaly Report to Slack...")
        file_path = self.generate_5xx_0dc_report(data, filename)
        try:
            self.send_pdf_report_on_slack(filename, file_path,thread_ts=thread_ts,channel_id=channel_id, message = message)
        except SlackApiError as e:
            logging.error(f"❌ Slack API Error (PDF Upload): {e.response['error']}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"🗑️ Deleted Temporary File: {file_path}")

