# Master Oogway - Post-Release Monitoring Service

## Overview
Master Oogway is an advanced, automated post-release monitoring service designed to detect anomalies, perform root cause analysis (RCA), and deliver actionable insights for NammaYatri. It integrates with AWS CloudWatch, Prometheus (via VictoriaMetrics), and Kubernetes (EKS) to monitor system health, fetch metrics, and provide real-time anomaly detection and reporting through Slack.

## Features
- **Real-time Monitoring:** Continuously tracks system health with scheduled and on-demand checks.
- **Metrics Fetching:** Collects metrics from AWS CloudWatch (RDS, ElastiCache), Prometheus (application and Istio metrics), and Kubernetes deployments.
- **Anomaly Detection:** Identifies deviations in CPU, memory, Redis, database, and HTTP error rates (5xx/0DC) using configurable thresholds.
- **Root Cause Analysis (RCA):** Analyzes issues related to DB CPU, Redis memory, application errors, and deployments.
- **Graphical Reports:** Generates PDF reports and plots (e.g., CPU/memory usage, error rates) for anomalies.
- **Slack Integration:** Delivers alerts, summaries, and detailed reports via Slack commands and event triggers.
- **Interactive Commands:** Supports Slack slash commands and app mentions for manual metric fetches and summaries.

## Architecture
Master Oogway is built with the following components:

1. **API Server** - FastAPI-based server providing endpoints for monitoring and health checks.
2. **Configuration Manager** - Loads settings from environment variables via `load_config`.
3. **Slack Messenger** - Handles messaging, PDF uploads, and interactive responses via Slack API.
4. **Metrics Fetcher** - Aggregates data from AWS (RDS, Redis), Prometheus (application/Istio), and Kubernetes (EKS).
5. **Anomaly Detector** - Compares current and past metrics to detect anomalies based on thresholds.
6. **Root Cause Analyzer (RCA)** - Correlates metrics with deployments and error spikes for diagnosis.
7. **Report Generator** - Creates PDF reports and matplotlib-based graphs for anomalies and trends.
8. **Scheduler** - Uses APScheduler to run monitoring tasks at configurable intervals.

## Tech Stack
- **Backend:** Python (FastAPI)
- **Metrics Collection:** AWS SDK (`boto3`), Prometheus API (VictoriaMetrics), Kubernetes SDK
- **Monitoring Sources:** AWS CloudWatch (RDS, ElastiCache), Prometheus (application/Istio metrics), EKS (deployments)
- **Anomaly Detection:** Custom threshold-based logic with consecutive data point analysis
- **Visualization:** `matplotlib` for graphs, `reportlab` for PDF reports
- **Slack Integration:** `slack_sdk` for messaging and file uploads
- **Scheduling:** `apscheduler` for automated monitoring

## Installation
### Prerequisites
- Python 3.8+
- AWS credentials configured (`boto3` access)
- VictoriaMetrics configured for Prometheus metrics
- Slack API token
- Kubernetes cluster (EKS) access
- `.env` file with configurations

### Setup Instructions
1. Clone the repository:
   ```sh
   git clone https://github.com/nammayatri/Master-Oogway.git
   cd Master-Oogway
   ```
2. Create and activate a virtual environment:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Set up environment variables in `.env`:
   ```ini
   AWS_REGION=ap-south-1
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   VMSELECT_URL=http://your-victoriametrics-url/select/0/prometheus/api/v1
   SLACK_BOT_TOKEN=your_slack_token
   SLACK_CHANNEL=#namma-yatri-sre
   KUBERNETES_CLUSTER_NAME=your_eks_cluster_name
   TIME_ZONE=Asia/Kolkata
   SCHEDULE_TIME=00:00
   ```
5. Run the service:
   ```sh
   python main.py
   ```

## Usage
- **Manual Trigger via API:**
  ```sh
  curl -X GET "http://localhost:8000/api/fetch_metrics?api_key=your-secure-api-key"
  ```
- **Slack Slash Commands:**
  - `/fetch_anamoly [now_days past_days hours]` - Triggers anomaly detection.
  - `/generate_current_report [hours]` - Fetches current metrics report.
  - `/generate_5xx_0dc_report [hours]` - Fetches 5xx/0DC error report.
- **Slack App Mention:**
  - `@MasterOogway please summarize!` - Summarizes thread content.
  - `@MasterOogway detect issue!` - Analyzes thread for issues.
  - `@MasterOogway usedolphin` - Invokes an alternate response model.

## API Endpoints
| Method | Endpoint                  | Description                     |
|--------|---------------------------|---------------------------------|
| GET    | `/api`                    | Home page with Oogway wisdom    |
| GET    | `/api/fetch_metrics`      | Triggers metrics fetch          |
| POST   | `/api/slack/events`       | Handles Slack events            |
| POST   | `/api/slack/commands`     | Handles Slack slash commands    |

## Slack Integration
- Monitors Slack messages for specific triggers (e.g., "cloudwatch alarm", "5xx").
- Responds to app mentions with summaries or issue detection.
- Uploads PDF reports and graphs to specified channels.

## Roadmap
- Enhance RCA with AI-driven insights.
- Add Grafana dashboard integration.
- Support webhook-based notifications for external systems.
- Expand metric coverage (e.g., additional Prometheus queries).

## Contributing
1. Fork the repository: [https://github.com/nammayatri/Master-Oogway](https://github.com/nammayatri/Master-Oogway).
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Contact
For issues or suggestions, please open an issue on GitHub: [https://github.com/nammayatri/Master-Oogway](https://github.com/nammayatri/Master-Oogway).

## Creator
Developed by [Vijay Gupta](https://github.com/vijaygupta18).