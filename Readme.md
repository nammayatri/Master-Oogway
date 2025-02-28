
# 🐢 Master Oogway - Post-Release Monitoring Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Slack Integration](https://img.shields.io/badge/Slack-Integrated-brightgreen)](https://slack.com/)

## 🚀 Overview

Master Oogway is an advanced **post-release monitoring service** for [NammaYatri](https://github.com/nammayatri), inspired by the wise turtle from *Kung Fu Panda*. Designed to ensure **system stability and performance**, Master Oogway automatically **detects anomalies, performs root cause analysis (RCA), and delivers insights via Slack**.

🔍 **What It Monitors?**  
- **AWS CloudWatch** (RDS, ElastiCache)  
- **Prometheus** (via VictoriaMetrics)  
- **Kubernetes (EKS)** deployments  
- **HTTP 5xx errors**, **ride-to-search ratios**, **memory spikes**, and more!  

💡 **How It Helps?**  
✅ Detects **CPU/memory anomalies**, **database/Redis issues**, and **HTTP failures**  
✅ Automates **root cause analysis** for fast debugging  
✅ Generates **detailed reports (PDFs & graphs)**  
✅ **Slack-first approach**—insights delivered instantly  

## 🎯 Features

✅ **Real-Time Monitoring** - Automatic & on-demand health checks  
✅ **Multi-Source Metrics** - AWS, Prometheus, Kubernetes  
✅ **Anomaly Detection** - Configurable thresholds for errors & spikes  
✅ **Root Cause Analysis (RCA)** - Tracks failures to deployments  
✅ **Graphical Reporting** - PDF reports with `matplotlib` graphs  
✅ **Slack Integration** - Slash commands, alerts, and interactive messages  
✅ **Smart AI Assistant** - Summarizes Slack threads & detects issues  

## 🏗️ Architecture

| **Component**         | **Description** |
|----------------------|---------------------------------|
| **API Server**       | FastAPI-based endpoints for monitoring |
| **Metrics Fetcher**  | Fetches data from AWS, Prometheus, Kubernetes |
| **Anomaly Detector** | Compares historical & real-time data for anomalies |
| **RCA Module**       | Correlates anomalies with deployments & failures |
| **Slack Messenger**  | Sends alerts, reports & responds to commands |
| **Report Generator** | Creates PDF reports & plots with `matplotlib` |
| **Scheduler**        | Uses `APScheduler` for periodic monitoring |

## 🔧 Tech Stack

- **Backend**: Python (FastAPI)
- **Metrics Sources**: AWS (`boto3`), Prometheus (VictoriaMetrics), Kubernetes SDK
- **Anomaly Detection**: Custom threshold-based logic
- **Visualization**: `matplotlib`, `reportlab` for PDF reports
- **Slack Integration**: `slack_sdk` for messages & commands
- **Scheduling**: `apscheduler`

## 📦 Installation & Setup

### Prerequisites

- Python 3.8+
- AWS credentials (`boto3`)
- VictoriaMetrics for Prometheus
- Kubernetes (EKS) cluster access
- **Slack Bot Token**
- `.env` file with configurations

### 🔌 Setup Instructions

1. **Clone the Repository**  
   ```bash
   git clone https://github.com/nammayatri/Master-Oogway.git
   cd Master-Oogway
   ```
2. **Set Up Virtual Environment**  
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Environment Variables**  
   Create a `.env` file:
   ```ini
   AWS_REGION=ap-south-1
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   VMSELECT_URL=http://your-victoriametrics-url/select/0/prometheus/api/v1
   SLACK_BOT_TOKEN=your_slack_token
   SLACK_CHANNEL_ID=your_channel_id
   KUBERNETES_CLUSTER_NAME=your_eks_cluster_name
   TIME_ZONE=Asia/Kolkata
   SCHEDULE_TIME=00:00
   API_KEYS=your_secure_api_key
   ```
5. **Run the Service**  
   ```bash
   python main.py
   ```

## 🛠️ Usage

### 🚀 API Triggers

```bash
curl -X GET "http://localhost:8000/api/fetch_metrics?api_key=your_api_key"
```

### 💬 Slack Commands

| **Command** | **Function** |
|------------|----------------------------------------|
| `/fetch_anomaly [days/hours]` | Runs anomaly detection |
| `/generate_current_report [hours]` | Fetches real-time metrics |
| `/generate_5xx_0dc_report [hours]` | Gets HTTP error reports |
| `@MasterOogway please summarize!` | Summarizes a Slack thread |
| `@MasterOogway detect issue!` | Finds root cause in discussions |

### ⏳ Automated Monitoring

- Runs **scheduled checks** based on `.env` configuration
- **Sends alerts & reports** via Slack

## 🔑 API Endpoints

| **Method** | **Endpoint**            | **Description** |
|-----------|-------------------------|----------------|
| GET       | `/api`                   | Home page wisdom 🐢 |
| GET       | `/api/fetch_metrics`     | Triggers metric collection |
| POST      | `/api/slack/events`      | Slack event listener |
| POST      | `/api/slack/commands`    | Handles Slack slash commands |

## 📂 Codebase Structure

```
📂 Master-Oogway
├── main.py                 # FastAPI app and scheduler
├── metrics_fetcher.py      # Fetches AWS/Prometheus/K8s metrics
├── application_metrics.py  # Monitors app-level performance
├── rds_metrics.py          # Tracks RDS performance
├── redis_metrics.py        # Analyzes Redis memory & CPU
├── deployment_checker.py   # Monitors Kubernetes deployments
├── slack.py                # Slack interactions & reports
├── report_generator.py     # PDF reports with `reportlab`
└── master_oogway.py        # AI-powered Slack responses
```

## 📊 Example Outputs

```
🚨 Master Oogway has detected an anomaly! 🐢
🔴 High CPU Usage in RDS: 89%
📉 Redis Memory Spike Detected!
📎 Report Attached.
```

## 🔮 Roadmap

🚀 **Upcoming Enhancements**  
✅ AI-powered RCA (using LLMs)  
✅ Grafana Dashboard Integration  
✅ Webhook-based Notifications  
✅ Expanded Prometheus Queries  

## 🤝 Contributing

1. **Fork the repository**: [Master Oogway](https://github.com/nammayatri/Master-Oogway)  
2. **Create a feature branch**:  
   ```bash
   git checkout -b feature-name
   ```
3. **Commit your changes**:  
   ```bash
   git commit -m "Add new feature"
   ```
4. **Push & open a PR**  
   ```bash
   git push origin feature-name
   ```

## 📜 License

This project is licensed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

## 📬 Contact

📌 **Issues**: [GitHub Issues](https://github.com/nammayatri/Master-Oogway/issues)  
📌 **Creator**: [Vijay Gupta](https://github.com/vijaygupta18)  
📌 **Organization**: [NammaYatri](https://github.com/nammayatri) 