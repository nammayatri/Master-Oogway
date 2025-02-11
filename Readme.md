# Master Oogway - Post-Release Monitoring Service

## Overview
Master Oogway is an automated post-release monitoring service designed to detect anomalies, analyze root causes, and generate detailed reports for NammaYatri. It fetches system metrics from AWS CloudWatch and Prometheus, detects performance anomalies, conducts root cause analysis (RCA), and delivers reports via Slack.

## Features
- **Real-time Monitoring:** Periodically checks for system health and performance anomalies.
- **Metrics Fetching:** Retrieves backend, business, and frontend metrics from AWS (CloudWatch, RDS, Redis) and Prometheus.
- **Anomaly Detection:** Identifies performance issues using predefined thresholds.
- **Root Cause Analysis (RCA):** Diagnoses issues such as high DB CPU usage, Redis memory spikes, and API errors.
- **PDF Report Generation:** Compiles findings into a structured report.
- **Slack Integration:** Sends anomaly alerts and reports directly to Slack channels.

## Architecture
Master Oogway consists of the following components:

1. **API Server** - Provides endpoints to trigger monitoring and fetch results.
2. **Configuration Manager** - Loads settings from environment variables.
3. **Slack Bot** - Sends messages and reports to Slack.
4. **Metrics Fetcher** - Queries AWS CloudWatch and Prometheus for system and business metrics.
5. **Anomaly Detector** - Detects deviations based on threshold comparisons.
6. **Root Cause Analyzer (RCA)** - Diagnoses issues related to DB, Redis, and API errors.
7. **Report Generator** - Formats the analysis into a PDF report.
8. **Monitoring Loop** - Continuously monitors and checks for anomalies.

## Tech Stack
- **Backend:** Python (Flask/FastAPI)
- **Metrics Collection:** AWS SDK (boto3), Prometheus client
- **Database Monitoring:** Amazon RDS (DB CPU), Amazon ElastiCache (Redis)
- **Anomaly Detection:** Custom Python logic with threshold-based checks
- **RCA:** Query-based DB and Redis analysis
- **PDF Report Generation:** `reportlab`
- **Slack Integration:** `slack_sdk`

## Installation
### Prerequisites
- Python 3.8+
- AWS credentials configured (`boto3` access)
- Prometheus configured
- Slack API token
- `.env` file with necessary configurations

### Setup Instructions
1. Clone the repository:
   ```sh
   git clone https://github.com/your-org/master-oogway.git
   cd master-oogway
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
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   PROMETHEUS_URL=http://your-prometheus-url
   SLACK_TOKEN=your_slack_token
   SLACK_CHANNEL=#alerts
   ```
5. Run the service:
   ```sh
   python main.py
   ```

## Usage
- To trigger monitoring manually:
  ```sh
  curl -X POST http://localhost:5000/monitor
  ```
- To check service health:
  ```sh
  curl http://localhost:5000/health
  ```

## API Endpoints
| Method | Endpoint            | Description                |
|--------|--------------------|----------------------------|
| GET    | `/health`          | Checks service health      |
| POST   | `/monitor`        | Triggers monitoring cycle  |
| GET    | `/report`         | Fetches latest report      |

## Roadmap
- [ ] Improve RCA with AI-based anomaly detection
- [ ] Introduce Grafana integration
- [ ] Implement webhook support for third-party notifications

## Contributing
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Contact
For any issues or suggestions, please reach out via opening an issue on GitHub.

