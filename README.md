# TA Interview Scheduler

An AI-powered Databricks App for intelligent technical interview scheduling with automatic interviewer assignment and fair workload distribution.

![Status](https://img.shields.io/badge/status-development-blue)
![Platform](https://img.shields.io/badge/platform-Databricks%20Apps-orange)
![AI](https://img.shields.io/badge/AI-Multi--Agent-green)

## 🚀 Key Features

### Intelligent Auto-Scheduling
- **One-click scheduling**: Just enter candidate details, AI handles the rest
- **Multi-agent system**: Calendar Agent, Distribution Agent, Invite Agent work together
- **Fair distribution**: Automatically balances interviews across all Solution Architects
- **Capacity limits**: Enforces max interviews per week per SA
- **Timezone-aware**: Finds overlapping work hours between interviewer and candidate

### How It Works

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Calendar Agent │ -> │ Distribution    │ -> │  Scheduling     │ -> │  Invite Agent   │
│                 │    │ Agent           │    │  Agent          │    │                 │
│ • Check SA      │    │ • Analyze       │    │ • Make final    │    │ • Send calendar │
│   availability  │    │   workload      │    │   assignment    │    │   invites       │
│ • Find timezone │    │ • Enforce       │    │ • Record        │    │ • Create Meet   │
│   overlap       │    │   capacity      │    │   interview     │    │   link          │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Fair Distribution Algorithm

The system considers:
1. **Capacity limits** - SAs at max weekly interviews are excluded
2. **Weekly interview count** (fewer = higher priority)
3. **Deviation from fair share** (negative = under-utilized)
4. **Specialty matching** (bonus for relevant expertise)
5. **Timezone compatibility** with candidate

## Technologies

| Technology | Purpose |
|------------|---------|
| **Dash + Mantine** | Modern reactive UI in Python |
| **LangGraph** | Multi-agent orchestration (optional LLM mode) |
| **Google Calendar API** | Real-time availability checking & invites |
| **Databricks SDK** | Workspace deployment |

## Project Structure

```
ta_interview_scheduler/
├── app.py                         # Main Dash application
├── app.yml                        # Databricks App config
├── requirements.txt               # Dependencies
├── example.env                    # Environment template
├── sa_config.json                 # SA allowlist with timezones
├── services/
│   ├── __init__.py
│   ├── calendar_service.py        # Google Calendar integration
│   ├── interview_tracker.py       # History & fair distribution
│   └── scheduling_agents.py       # Multi-agent system
├── assets/
│   └── logo.svg
└── README.md
```

---

## 🔐 Google Calendar Configuration

The app supports two authentication modes for Google Calendar integration:

### Testing Environment: Personal OAuth

Use your personal Gmail account to test the calendar integration.

#### Step 1: Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Google Calendar API**:
   - APIs & Services → Library → Search "Calendar" → Enable
4. Create OAuth credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file

#### Step 2: Configure the App

```bash
# Save the OAuth credentials file as:
cp ~/Downloads/client_secret_*.json credentials.json

# Run the app - browser will open for authentication
python app.py
```

On first run:
- Browser opens for Google OAuth consent
- Grant "See, edit, share calendars" permission
- Token is saved to `token.pickle` for future use

#### Step 3: Configure Your Calendar as SA

Edit `sa_config.json`:
```json
{
  "solution_architects": [
    {
      "id": "sa1",
      "name": "Your Name",
      "email": "your.email@gmail.com",
      "calendar_id": "your.email@gmail.com",
      "specialty": "Data Engineering",
      "timezone": "America/Los_Angeles",
      "active": true,
      "max_interviews_per_week": 5
    }
  ]
}
```

---

### Production Environment: Domain-Wide Delegation

For organization-wide deployment, use a service account with domain-wide delegation to check all SA calendars.

#### Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a service account:
   - IAM & Admin → Service Accounts → Create
   - Name: `ta-scheduler-service`
   - Grant no roles (not needed for Calendar API)
3. Create a key:
   - Click the service account → Keys → Add Key → JSON
   - Save as `service_account.json`

#### Step 2: Enable Domain-Wide Delegation

1. In the service account details, click **"Show Domain-Wide Delegation"**
2. Check **"Enable G Suite Domain-wide Delegation"**
3. Note the **Client ID** (numeric)

#### Step 3: Admin Console Authorization

**Requires Google Workspace Admin:**

1. Go to [Google Admin Console](https://admin.google.com/)
2. Security → API Controls → Manage Domain-Wide Delegation
3. Add new:
   - **Client ID**: The numeric ID from Step 2
   - **OAuth Scopes**:
     ```
     https://www.googleapis.com/auth/calendar.readonly,
     https://www.googleapis.com/auth/calendar.events
     ```
4. Authorize

#### Step 4: Configure the App

```bash
# Save the service account key
cp ~/Downloads/service_account.json service_account.json
```

Edit `sa_config.json` with all SA emails:
```json
{
  "solution_architects": [
    {
      "id": "sa1",
      "name": "Alex Chen",
      "email": "alex.chen@company.com",
      "calendar_id": "alex.chen@company.com",
      "specialty": "Data Engineering",
      "timezone": "America/Los_Angeles",
      "active": true,
      "max_interviews_per_week": 5
    },
    {
      "id": "sa2",
      "name": "Jordan Rivera",
      "email": "jordan.rivera@company.com",
      "calendar_id": "jordan.rivera@company.com",
      "specialty": "ML/AI",
      "timezone": "America/New_York",
      "active": true,
      "max_interviews_per_week": 5
    }
  ]
}
```

#### Authentication Priority

The app checks for credentials in this order:
1. `service_account.json` → Domain-wide delegation mode
2. `credentials.json` → Personal OAuth mode
3. Neither → Demo mode with simulated data

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Google Cloud project with Calendar API enabled
- OpenAI API key (optional - rule-based mode works without it)

### Local Development

```bash
cd ta_interview_scheduler
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000

### Deploy to Databricks

1. Push code to a Databricks Git folder:
   ```bash
   git add .
   git commit -m "Update scheduler"
   git push origin main
   ```

2. In Databricks workspace:
   - **Compute** → **Apps** → Select your app
   - Click **"Sync"** to pull latest changes
   - Or create new: **Create App** → **Custom** → Deploy from git

3. Configure secrets (if using Calendar API):
   - Store `credentials.json` content as a Databricks secret
   - Reference in app environment variables

---

## Usage

### One-Click Scheduling

1. Enter candidate name and email
2. Select interview type and duration
3. Set date range and **candidate's timezone**
4. Click **"Find Best Slot"**
5. Done! Calendar invites are sent automatically

### Workload Dashboard

The left panel shows real-time capacity:
- 🟢 **Green**: Available capacity
- 🟡 **Yellow**: 50-80% capacity
- 🟠 **Orange**: Near capacity
- 🔴 **Red + Badge**: At max capacity (excluded from scheduling)

### SA Configuration

Edit `sa_config.json` to manage the SA allowlist:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier |
| `name` | Display name |
| `email` | SA's email address |
| `calendar_id` | Google Calendar ID (usually email) |
| `specialty` | Area of expertise for matching |
| `timezone` | SA's working timezone |
| `max_interviews_per_week` | Capacity limit |

---

## Architecture

### Agent Modes

1. **Rule-Based Mode** (default): Fast, deterministic scheduling
2. **LLM Mode** (optional): GPT-4o-mini for nuanced decisions

### Data Storage

| Environment | Storage |
|-------------|---------|
| Local/Testing | `interview_data.json` |
| Production | Unity Catalog tables (recommended) |

---

## License

Internal use only.
