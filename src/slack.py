from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
import tempfile
import logging
import os
from datetime import datetime, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from load_config import load_config
from time_function import TimeFunction
from reportlab.platypus import HRFlowable  # Import horizontal line
from master_oogway import get_master_oogway_quotes


class SlackMessenger:
    def __init__(self, config_data):
        """
        Initialize Slack Messenger with Slack API.
        """
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
        """
        Send a simple Slack message.
        """
        channel = channel or self.default_channel
        try:
            result = self.client.chat_postMessage(channel=channel, text=text)
            logging.info(f"✅ Slack Message Sent: {text}")
            return result
        except SlackApiError as e:
            logging.error(f"❌ Slack API Error: {e.response['error']}")
            return None

    def create_pdf(self, data, filename="Anomaly_Report.pdf", start_date_time=None, end_date_time=None):
        """
        Generate a structured, multi-page PDF anomaly report.
        """
        if start_date_time is None or end_date_time is None:
            start_date_time, end_date_time = self.time_function.get_target_datetime(
                days_before=self.days, target_hour=self.target_hour, target_minute=self.target_minute, time_delta=self.time_delta)
            
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        file_path = temp_file.name

        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()

            # Custom Styles
            title_style = ParagraphStyle(
                "TitleStyle", parent=styles["Title"], fontSize=24, textColor=colors.darkblue, spaceAfter=12)
            header_style = ParagraphStyle(
                "HeaderStyle", parent=styles["Heading2"], fontSize=18, textColor=colors.darkred, spaceAfter=10)
            normal_style = styles["BodyText"]
            bold_style = ParagraphStyle(
                "BoldStyle", parent=styles["BodyText"], fontSize=12, textColor=colors.red, bold=True)
            bold_style1 = ParagraphStyle(
                "BoldStyle1", parent=styles["Heading2"], fontSize=12, textColor=colors.purple, bold=True)
            red_normal_style = ParagraphStyle(
                "RedNormalStyle", parent=styles["BodyText"], fontSize=10, textColor=colors.red,bold=True)

            content = []

            # 🚀 Report Title
            content.append(
                Paragraph("🚀 Auto-Generated Anomaly Report", title_style))
            content.append(Spacer(1, 12))

            # ✅ Report Metadata
            metadata = {
                " - Report Generated at": self.time_function.convert_time((datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")), "UTC"),
                " - Total Anomalies": sum(len(v) for v in data.values() if isinstance(v, list)),
                " - Recent Deployments": len(data.get("active_deployments", [])),
                " - Current Report Period": self.time_function.convert_time(start_date_time[0].strftime("%Y-%m-%d %H:%M:%S"), "UTC") + " to " + self.time_function.convert_time(start_date_time[1].strftime("%Y-%m-%d %H:%M:%S"), "UTC"),
                " - Past Report Period": self.time_function.convert_time(end_date_time[0].strftime("%Y-%m-%d %H:%M:%S"), "UTC") + " to " + self.time_function.convert_time(end_date_time[1].strftime("%Y-%m-%d %H:%M:%S"), "UTC")
            }

            for key, value in metadata.items():
                content.append(Paragraph(f"{key}: {value}", bold_style1))
            content.append(Spacer(1, 12))

            self.add_section(content, "RDS Anomalies", data.get(
                "rds_anomaly", []), header_style, normal_style, bold_style, red_normal_style)
            self.add_section(content, "Redis Anomalies", data.get(
                "redis_anomaly", []), header_style, normal_style, bold_style, red_normal_style)
            self.add_section(content, "Application & Istio Anomalies", data.get(
                "application_anomaly", []), header_style, normal_style, bold_style, red_normal_style)
            self.add_deployment_section(content, f"🚀 Deployments Done in past {self.days} days ", data.get(
                "active_deployments", []), header_style, normal_style)
            # ✅ Save PDF
            doc.build(content)
            logging.info(f"✅ PDF Report Generated: {file_path}")

        except Exception as e:
            logging.error(f"❌ Error creating PDF: {e}")

        return file_path

    def add_section(self, content, title, anomalies, header_style, normal_style, bold_style, red_bold_style, is_nested=False, level=0):
        """
        Recursively adds an anomaly section to the PDF with indentation, red-highlighted issue values, and separators.
        """
        if not anomalies:
            return
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * level  # HTML spacing for indentation
        # **🔹 Add title only if it's not nested**
        if not is_nested:
            content.append(Paragraph(f"🔹 <b>{title}</b>", header_style))
            content.append(Spacer(1, 6))

        for anomaly in anomalies:
            if isinstance(anomaly, dict):
                for key, value in anomaly.items():
                    if isinstance(value, dict):
                        # **Handle Nested Dictionary (Indented but Not as a New Section)**
                        content.append(
                            Paragraph(f"{indent}<b>{key}:</b>", bold_style))
                        self.add_section(content, key, [
                                         value], header_style, normal_style, bold_style, red_bold_style, is_nested=True, level=level + 1)

                    elif isinstance(value, list):
                        # **Handle Nested List**
                        content.append(
                            Paragraph(f"{indent}<b>{key}:</b>", red_bold_style))
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                # **If List Item is a Dictionary, Call Recursively**
                                self.add_section(content, f"{key}", [
                                                 item], header_style, normal_style, bold_style, red_bold_style, is_nested=True, level=level + 1)
                            else:
                                # **If List Item is a Primitive Value**
                                content.append(
                                    Paragraph(f"{indent}   - {item}", normal_style))

                    else:
                        if "Issue" in key:
                            content.append(Paragraph(
                                f"{indent}<b>{key}:</b> <font color='red'><b>{value}</b></font>", red_bold_style))
                        else:
                            content.append(
                                Paragraph(f"{indent}<b>{key}:</b> {value}", normal_style))

                # **🔹 Add Horizontal Line After Each Anomaly (EXCEPT Inside Lists)**
                content.append(Spacer(1, 12))
                # Line separator
                content.append(HRFlowable(
                    width="100%", thickness=1, color=colors.black))
                content.append(Spacer(1, 12))  # Space after line

    def add_deployment_section(self, content, title, deployments, header_style, normal_style):
        """
        Add a structured table for active deployments.
        """
        if not deployments:
            return
        content.append(Paragraph(title, header_style))
        content.append(Spacer(1, 6))

        # Table Headers
        table_data = [["Deployment Name", "Created At", "Replicas"]]
        for deployment in deployments:
            table_data.append([deployment["name"], deployment["created_at"], str(
                deployment["available_replicas"])])

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

    def send_pdf_report(self, data, filename="Anomaly_Report.pdf", title="🚨 Critical Anomalies Report", start_time=None, end_time=None):
        """
        Generate and send a PDF anomaly report to Slack.
        """
        channel = self.default_channel
        file_path = self.create_pdf(data, filename, start_date_time=start_time, end_date_time=end_time)

        try:
            result = self.client.files_upload_v2(
                channel=channel,
                file=file_path,
                filename=filename,
                title=title,
                initial_comment="📄 @here Master Oogway :oogway: is back with wisdom - " + get_master_oogway_quotes(data)
            )
            logging.info(f"✅ PDF Report Sent to Slack: {filename}")
            return result
        except SlackApiError as e:
            logging.error(
                f"❌ Slack API Error (PDF Upload): {e.response['error']}")
            return None
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"🗑️ Deleted Temporary File: {file_path}")

