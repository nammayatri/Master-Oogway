# 🐢 Master Oogway - Post-Release Monitoring Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.13%2B-blue)](https://www.python.org/)
[![Slack Integration](https://img.shields.io/badge/Slack-Integrated-brightgreen)](https://slack.com/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue)](https://www.docker.com/)

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

### 🔄 Real-Time Monitoring
- Automatic health checks at configurable intervals
- On-demand metric collection via Slack commands
- Customizable monitoring windows and thresholds

### 📊 Multi-Source Metrics
- **AWS CloudWatch**
  - RDS CPU utilization and connections
  - Redis memory and capacity metrics
  - Custom CloudWatch alarms
- **Prometheus/VictoriaMetrics**
  - Application-level metrics
  - HTTP status codes (2xx, 3xx, 4xx, 5xx)
  - Custom Prometheus queries
- **Kubernetes**
  - Deployment status
  - Pod health
  - Resource utilization

### 🚨 Anomaly Detection
- Configurable thresholds for:
  - CPU utilization
  - Memory usage
  - Database connections
  - HTTP error rates
  - Redis capacity
- Historical comparison for trend analysis
- Customizable anomaly detection rules

### 🔍 Root Cause Analysis
- Automatic correlation with recent deployments
- Timeline-based analysis
- Multi-metric correlation
- Deployment impact assessment

### 📈 Reporting
- PDF reports with detailed metrics
- Matplotlib graphs for visualization
- Custom report generation
- Historical data comparison

### 💬 Slack Integration
- Real-time alerts
- Interactive commands
- Thread-based conversations
- Custom message formatting

### 🤖 AI Assistant
- Thread summarization using Gemini API
- Issue detection and analysis
- Context-aware responses
- Multiple AI model support (Gemini, Dolphin)

## 🏗️ Architecture

### Core Components

| **Component**         | **Description** |
|----------------------|---------------------------------|
| **API Server**       | FastAPI-based endpoints for monitoring |
| **Metrics Fetcher**  | Fetches data from AWS, Prometheus, Kubernetes |
| **Anomaly Detector** | Compares historical & real-time data for anomalies |
| **RCA Module**       | Correlates anomalies with deployments & failures |
| **Slack Messenger**  | Sends alerts, reports & responds to commands |
| **Report Generator** | Creates PDF reports & plots with `matplotlib` |
| **Scheduler**        | Uses `APScheduler` for periodic monitoring |

### Data Flow
1. **Collection**: Metrics gathered from multiple sources
2. **Processing**: Data normalized and analyzed
3. **Detection**: Anomalies identified using configurable rules
4. **Analysis**: Root cause determined through correlation
5. **Reporting**: Results formatted and delivered via Slack

## 🔧 Tech Stack

### Backend
- **Python 3.13**
- **FastAPI** for API endpoints
- **APScheduler** for task scheduling
- **Boto3** for AWS integration
- **Kubernetes Python Client** for EKS
- **Slack SDK** for messaging

### Visualization
- **Matplotlib** for graphs
- **ReportLab** for PDF generation

### AI Integration
- **Gemini API** for insights
- **Dolphin API** for advanced analysis

## 📦 Installation & Setup

### Prerequisites

- Python 3.13+
- AWS credentials with appropriate permissions
- VictoriaMetrics for Prometheus
- Kubernetes (EKS) cluster access
- Slack Bot Token
- Docker (optional)

### Configuration

Create a `config.json` file with the following structure:

```json
{
    "AWS_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "your-access-key",
    "HOST": "0.0.0.0",
    "API_ENDPOINT": "/api/oogway",
    "PORT": 8000,
    "KUBERNETES_CLUSTER_NAME": "your-cluster",
    "RDS_CLUSTER_IDENTIFIERS": ["cluster-1", "cluster-2"],
    "REDIS_CLUSTER_IDENTIFIERS": ["redis-cluster"],
    "DEFAULT_PERIOD": 60,
    "MAX_BIGKEY_SIZE_MB": 10,
    "RDS_CPU_DIFFERENCE_THRESHOLD": 10,
    "RDS_CONNECTIONS_DIFFERENCE_THRESHOLD": 100,
    "REPLICA_THRESHOLD": 1,
    "ALLOW_INSTANCE_ANOMALIES": false,
    "REDIS_CPU_DIFFERENCE_THRESHOLD": 10,
    "REDIS_MEMORY_DIFFERENCE_THRESHOLD": 10,
    "REDIS_CAPACITY_DIFFERENCE_THRESHOLD": 10,
    "TIME_DELTA": {"hours": 1},
    "DEFAULT_TIME_DELTA": {"minutes": 30},
    "TIME_OFFSET_DAYS": 7,
    "TARGET_HOURS": 17,
    "TARGET_MINUTES": 0,
    "PROMETHEUS_URL": "http://your-prometheus:9090",
    "KUBERNETES_NAMESPACE": "your-namespace",
    "SLACK_BOT_TOKEN": "your-token",
    "SLACK_CHANNEL_ID": "your-channel",
    "ALERT_CHANNEL_NAME": "#your-alert-channel",
    "GEMINI_API_KEY": "your-gemini-key",
    "GEMINI_MODEL": "2.0",
    "DOLPHIN_API_KEY": "your-dolphin-key",
    "ALLOWED_USER_IDS": ["user1", "user2"],
    "IGNORED_USER_IDS": ["user3"],
    "CACHE_TTL": 5,
    "MAX_SIZE_BYTES": 10,
    "SLACK_THREAD_API": "https://slack.com/api/conversations.replies",
    "QUERY_STEP_RANGE": "1m",
    "API_LIST": ["/api1", "/api2"],
    "APP_TIME_DELTA": {"hours": 1},
    "ISTIO_METRICS": {
        "REQUEST_COUNT_THRESHOLDS": {
            "2xx": 5000,
            "3xx": 5000,
            "4xx": 5000,
            "5xx": 500,
            "0DC": 500
        },
        "PERCENTAGE_CHANGE_THRESHOLDS": {
            "2xx": 100,
            "3xx": 100,
            "4xx": 100,
            "5xx": 100,
            "0DC": 100
        }
    },
    "APPLICATION_METRICS": {
        "REQUEST_COUNT_THRESHOLDS": {
            "2xx": 10000,
            "3xx": 1000,
            "4xx": 1000,
            "5xx": 500,
            "0DC": 500
        },
        "PERCENTAGE_CHANGE_THRESHOLDS": {
            "2xx": 50,
            "3xx": 50,
            "4xx": 50,
            "5xx": 50,
            "0DC": 50
        }
    },
    "APPLICATION_CPU_THRESHOLD": 80,
    "APPLICATION_MEMORY_THRESHOLD": 90,
    "APPLICATION_CONSECUTIVE_DATAPOINTS": 3,
    "SKIP_MEMORY_CHECK_SERVICES": ["service1", "service2"]
}
```

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

4. **Configure Environment**  
   - Copy `config/config_template.json` to `config/config.json`
   - Update configuration values
   - Set up AWS credentials
   - Configure Slack bot

5. **Run the Service**  
   ```bash
   python src/main.py
   ```

### 🐳 Docker Deployment

1. **Build the Image**  
   ```bash
   docker build -t master-oogway .
   ```

2. **Run the Container**  
   ```bash
   docker run -d \
     -p 8000:8000 \
     -v $(pwd)/config:/app/config \
     -e CONFIG_ENV_DATA=$(base64 -w0 config/config.json) \
     master-oogway
   ```

## 🛠️ Usage

### 🚀 API Endpoints

| **Method** | **Endpoint**            | **Description** |
|-----------|-------------------------|----------------|
| GET       | `/api`                   | Home page wisdom 🐢 |
| GET       | `/api/fetch_metrics`     | Triggers metric collection |
| POST      | `/api/slack/events`      | Slack event listener |
| POST      | `/api/slack/commands`    | Handles Slack slash commands |

### 💬 Slack Commands

| **Command** | **Function** |
|------------|----------------------------------------|
| `/fetch_anomaly [days/hours]` | Runs anomaly detection |
| `/generate_current_report [hours]` | Fetches real-time metrics |
| `/generate_5xx_0dc_report [hours]` | Gets HTTP error reports |
| `@MasterOogway please summarize!` | Summarizes a Slack thread |
| `@MasterOogway detect issue!` | Finds root cause in discussions |

### ⚙️ Configuration Options

#### Time Settings
- `TIME_DELTA`: Default time range for metrics (e.g., {"hours": 1})
- `TIME_OFFSET_DAYS`: Days to look back for comparison
- `TARGET_HOURS`: Target hour for scheduled checks
- `TARGET_MINUTES`: Target minute for scheduled checks

#### Thresholds
- `RDS_CPU_DIFFERENCE_THRESHOLD`: CPU usage change threshold
- `RDS_CONNECTIONS_DIFFERENCE_THRESHOLD`: Connection count threshold
- `REDIS_CPU_DIFFERENCE_THRESHOLD`: Redis CPU threshold
- `REDIS_MEMORY_DIFFERENCE_THRESHOLD`: Memory usage threshold
- `ERROR_5XX_THRESHOLD`: HTTP 5xx error threshold
- `ERROR_0DC_THRESHOLD`: 0DC error threshold

#### Monitoring Settings
- `DEFAULT_PERIOD`: Default metric collection period
- `MAX_BIGKEY_SIZE_MB`: Maximum Redis key size
- `REPLICA_THRESHOLD`: RDS replica count threshold
- `APPLICATION_CPU_THRESHOLD`: App CPU threshold
- `APPLICATION_MEMORY_THRESHOLD`: App memory threshold

## 🔍 Monitoring Metrics

### RDS Metrics
- CPU Utilization
- Database Connections
- Replica Count
- Writer/Reader Status

### Redis Metrics
- Memory Usage
- CPU Utilization
- Capacity
- Key Size Distribution

### Application Metrics
- HTTP Status Codes (2xx, 3xx, 4xx, 5xx)
- 0DC Errors
- CPU Usage
- Memory Usage
- Ride-to-Search Ratio

### Kubernetes Metrics
- Deployment Status
- Pod Health
- Resource Utilization
- Error Rates

## 🛡️ Security

### API Security
- API key authentication
- Rate limiting
- Input validation
- Secure configuration handling

### AWS Security
- IAM role-based access
- Secure credential storage
- Least privilege principle

### Slack Security
- Bot token security
- Channel access control
- User authentication

## 🧪 Testing

### Local Testing
```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=src tests/
```

### Integration Testing
- AWS CloudWatch integration
- Prometheus connectivity
- Kubernetes cluster access
- Slack message delivery

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

### Planned Features
- [ ] AI-powered RCA enhancement
- [ ] Grafana dashboard integration
- [ ] Webhook-based notifications
- [ ] Expanded Prometheus queries
- [ ] Custom alert rules
- [ ] Multi-cluster support

### Performance Improvements
- [ ] Caching layer
- [ ] Async metric collection
- [ ] Batch processing
- [ ] Optimized queries

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

### Development Guidelines
- Follow PEP 8 style guide
- Write unit tests for new features
- Document all public APIs
- Update README for new features
- Use meaningful commit messages

## 📜 License

This project is licensed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

## 📬 Contact

📌 **Issues**: [GitHub Issues](https://github.com/nammayatri/Master-Oogway/issues)  
📌 **Creator**: [Vijay Gupta](https://github.com/vijaygupta18)  
📌 **Organization**: [NammaYatri](https://github.com/nammayatri) 

## 🙏 Acknowledgments

- Inspired by the wisdom of Master Oogway from Kung Fu Panda
- Built with ❤️ for the NammaYatri community
- Thanks to all contributors and users 