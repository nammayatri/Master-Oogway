from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
import tempfile
import logging
import os
from datetime import datetime, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from load_config import load_config
from time_function import TimeFunction
from reportlab.lib.enums import TA_CENTER
from master_oogway import get_master_oogway_quotes
import json


class SlackMessenger:
    def __init__(self, config_data):
        """Initialize Slack Messenger with Slack API."""
        self.slack_token = config_data.get("SLACK_BOT_TOKEN")
        self.default_channel = config_data.get("SLACK_CHANNEL_ID")
        self.days = config_data.get("TIME_OFFSET_DAYS", 7)
        self.target_hour = config_data.get("TARGET_HOURS", 10)
        self.target_minute = config_data.get("TARGET_MINUTES", 0)
        self.time_delta = config_data.get("TIME_DELTA", {"hours": 1})
        self.time_function = TimeFunction()

        if not self.slack_token:
            raise ValueError("❌ Missing Slack Bot Token.")
        if not self.default_channel:
            raise ValueError("❌ Missing Slack Channel ID.")

        self.client = WebClient(token=self.slack_token)
        logging.basicConfig(level=logging.INFO)

    def send_message(self, text, channel=None):
        """Send a simple Slack message."""
        channel = channel or self.default_channel
        try:
            result = self.client.chat_postMessage(channel=channel, text=text)
            logging.info(f"✅ Slack Message Sent: {text}")
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

    def create_pdf(self, data, filename="Anomaly_Report.pdf", start_date_time=None, end_date_time=None):
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
            
            self.add_deployment_section(content, f"🚀 Deployments in past {self.days} days", data.get("active_deployments", []), header_style, normal_style)

            # ✅ Save PDF
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
        # **🔹 Add title only if it's not nested**
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

    def send_pdf_report(self, data, filename="Anomaly_Report.pdf", start_time=None, end_time=None):
        """Generate and send a PDF anomaly report to Slack."""
        file_path = self.create_pdf(data, filename, start_date_time=start_time, end_date_time=end_time)
        self.client.files_upload_v2(
            channel=self.default_channel,
            file=file_path,
            filename=filename,
            title="🚨 Anomaly Report",
            initial_comment="📄 @here Master Oogway :oogway: has returned with wisdom - " + get_master_oogway_quotes(data),
        )
        os.remove(file_path)  # Cleanup temp file
