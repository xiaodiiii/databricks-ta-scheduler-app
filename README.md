# TA Interview Scheduler

An AI-powered Databricks App for intelligent technical interview scheduling with automatic interviewer assignment and fair workload distribution.

![Status](https://img.shields.io/badge/status-development-blue)
![Platform](https://img.shields.io/badge/platform-Databricks%20Apps-orange)
![AI](https://img.shields.io/badge/AI-Multi--Agent-green)

## 🚀 Key Features

### Intelligent Auto-Scheduling
- **One-click scheduling**: Just enter candidate details, AI handles the rest
- **Multi-agent system**: Calendar Agent, Distribution Agent, and Scheduling Agent work together
- **Fair distribution**: Automatically balances interviews across all Solution Architects
- **3-week history tracking**: Ensures no one gets overloaded

### How It Works

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Calendar Agent │ -> │ Distribution    │ -> │  Scheduling     │
│                 │    │ Agent           │    │  Agent          │
│ • Query all SA  │    │ • Analyze       │    │ • Make final    │
│   calendars     │    │   workload      │    │   assignment    │
│ • Find slots    │    │ • Rank by       │    │ • Book meeting  │
│                 │    │   fairness      │    │ • Record history│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Fair Distribution Algorithm

The system considers:
1. **Interview count** in the last 3 weeks (fewer = higher priority)
2. **Deviation from fair share** (negative = under-utilized)
3. **Specialty matching** (bonus for relevant expertise)
4. **Capacity limits** (max interviews per week)

## Technologies

| Technology | Purpose |
|------------|---------|
| **Dash + Mantine** | Modern reactive UI in Python |
| **LangGraph** | Multi-agent orchestration (optional LLM mode) |
| **Google Calendar API** | Real-time availability checking |
| **Databricks SDK** | Workspace deployment |

## Project Structure

```
ta_interview_scheduler/
├── app.py                         # Main Dash application
├── app.yml                        # Databricks App config
├── requirements.txt               # Dependencies
├── example.env                    # Environment template
├── utils.py                       # UI helpers
├── services/
│   ├── __init__.py
│   ├── calendar_service.py        # Google Calendar integration
│   ├── interview_tracker.py       # History & fair distribution
│   └── scheduling_agents.py       # Multi-agent system
├── assets/
│   └── logo.svg
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Google Cloud project with Calendar API enabled (optional for demo)
- OpenAI API key (optional - rule-based mode works without it)

### Quick Start (Demo Mode)

```bash
cd ta_interview_scheduler
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000 - the app runs in demo mode with simulated calendar data.

### With Google Calendar

1. Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com/)
2. Download as `credentials.json` in project root
3. Run the app and authorize on first launch

### Deploy to Databricks

1. Push to a Databricks Git folder
2. **Compute** → **Apps** → **Create App** → **Custom**
3. Deploy from the git folder

## Usage

### One-Click Scheduling

1. Enter candidate name and email
2. Select interview type (Tech Screen, System Design, etc.)
3. Click **"🤖 Auto-Schedule Now"**
4. Done! The AI finds the best interviewer and time slot

### Preview Mode

Click **"Preview Options"** to see the top 5 recommendations before committing.

### Workload Dashboard

The left panel shows real-time workload distribution:
- 🟢 **Available**: Under fair share (gets priority)
- 🔵 **Balanced**: At fair share
- 🟠 **Busy**: Above fair share

## Architecture

### Agent Modes

1. **Rule-Based Mode** (default): Fast, deterministic scheduling using workload algorithms
2. **LLM Mode** (optional): Uses GPT-4o-mini for more nuanced decisions

### Data Storage

Currently uses local JSON file (`interview_data.json`) for persistence.

For production, connect to:
- Unity Catalog tables for interview history
- HR system for SA registry

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Enable LLM mode | Rule-based |
| `GOOGLE_CREDENTIALS_JSON` | Calendar OAuth file | Demo mode |
| `SCHEDULER_TIMEZONE` | Scheduling timezone | America/Los_Angeles |

## Extending

### Add More SAs

Edit `services/interview_tracker.py` → `_get_default_sa_registry()`

### Custom Interview Types

Edit `app.py` → `INTERVIEW_TYPES` list

### Connect to Unity Catalog

Replace `InterviewTracker._load_data()` and `_save_data()` with SQL queries

---

## License

Internal use only.
