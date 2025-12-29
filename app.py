"""
TA Interview Scheduler - Databricks App
AI-powered interview scheduling with automatic fair distribution.
"""

from datetime import datetime, timedelta
from typing import List, Dict

import dash
import dash_mantine_components as dmc
from dash import Dash, Input, Output, State, callback, dcc, html, no_update
from dash_iconify import DashIconify

# Initialize app
app = Dash(
    __name__,
    external_stylesheets=[dmc.styles.ALL],
    suppress_callback_exceptions=True
)
app.title = "TA Interview Scheduler"


def get_icon(icon: str, height: int = 16):
    """Get a DashIconify icon component."""
    return DashIconify(icon=icon, height=height)


# Databricks Brand Theme
THEME = {
    "fontFamily": "DM Sans, sans-serif",
    "primaryColor": "lava",
    "colors": {
        "lava": [
            "#ffe9e6",
            "#ffd2cd",
            "#ffa49a",
            "#ff7264",
            "#ff4936",
            "#ff2e18",
            "#ff1e07",
            "#e40f00",
            "#cc0500",
            "#b20000",
        ]
    },
}

# Databricks color palette
COLORS = {
    "bg": "#F9F7F4",
    "bg_accent": "#EEEDE9",
    "white": "#FFFFFF",
    "border": "#DCDCDC",
    "text": "#1B1B1B",
    "text_secondary": "#6B6B6B",
    "lava": "#FF3621",
}

INTERVIEW_TYPES = [
    {"label": "Technical Screen", "value": "tech_screen"},
    {"label": "System Design", "value": "system_design"},
    {"label": "Coding Interview", "value": "coding"},
    {"label": "ML/AI Deep Dive", "value": "ml_ai"},
    {"label": "Data Engineering", "value": "data"},
    {"label": "Architecture Review", "value": "architecture"},
]


def create_header():
    """Create the app header with Databricks styling."""
    return dmc.AppShellHeader(
        style={"backgroundColor": COLORS["bg"]},
        children=[
            dmc.Container(
                children=[
                    dmc.Group(
                        justify="space-between",
                        align="center",
                        h="100%",
                        children=[
                            dmc.Group(
                                gap="sm",
                                align="center",
                                children=[
                                    html.Img(
                                        src=app.get_asset_url("logo.svg"),
                                        height=28,
                                    ),
                                    dmc.Title(
                                        "TA Interview Scheduler",
                                        order=3,
                                        style={"fontWeight": 600},
                                    ),
                                ],
                            ),
                            dmc.Group(
                                gap="sm",
                                children=[
                                    dmc.Badge(
                                        id="system-status",
                                        children="Initializing...",
                                        variant="outline",
                                        leftSection=get_icon("material-symbols:sync"),
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
                fluid=False,
                h="100%",
                px=0,
            )
        ],
    )


def create_scheduling_form():
    """Create the interview scheduling form."""
    return dmc.Paper(
        shadow="sm",
        p="lg",
        radius="md",
        withBorder=True,
        style={"backgroundColor": COLORS["white"], "height": "480px", "overflow": "hidden"},
        children=[
            dmc.Stack(
                gap="sm",
                children=[
                    dmc.Title("Schedule Interview", order=4),
                    dmc.Text(
                        "Enter candidate details. The system will find the best interviewer.",
                        size="xs",
                        c="dimmed",
                    ),
                    
                    dmc.Divider(),
                    
                    # Candidate Information
                    dmc.Grid(
                        gutter="sm",
                        children=[
                            dmc.GridCol(
                                dmc.TextInput(
                                    id="candidate-name",
                                    label="Candidate Name",
                                    placeholder="Full name",
                                    leftSection=get_icon("material-symbols:person-outline"),
                                    required=True,
                                    size="sm",
                                ),
                                span=6,
                            ),
                            dmc.GridCol(
                                dmc.TextInput(
                                    id="candidate-email",
                                    label="Email",
                                    placeholder="email@company.com",
                                    leftSection=get_icon("material-symbols:mail-outline"),
                                    required=True,
                                    size="sm",
                                ),
                                span=6,
                            ),
                        ],
                    ),
                    
                    dmc.Grid(
                        gutter="sm",
                        children=[
                            dmc.GridCol(
                                dmc.Select(
                                    id="interview-type",
                                    label="Interview Type",
                                    placeholder="Select type",
                                    data=INTERVIEW_TYPES,
                                    leftSection=get_icon("material-symbols:assignment-outline"),
                                    required=True,
                                    size="sm",
                                ),
                                span=6,
                            ),
                            dmc.GridCol(
                                dmc.Select(
                                    id="interview-duration",
                                    label="Duration",
                                    value="60",
                                    data=[
                                        {"label": "30 min", "value": "30"},
                                        {"label": "45 min", "value": "45"},
                                        {"label": "60 min", "value": "60"},
                                        {"label": "90 min", "value": "90"},
                                    ],
                                    leftSection=get_icon("material-symbols:schedule-outline"),
                                    size="sm",
                                ),
                                span=6,
                            ),
                        ],
                    ),
                    
                    dmc.Grid(
                        gutter="sm",
                        children=[
                            dmc.GridCol(
                                dmc.DateInput(
                                    id="start-date",
                                    label="From Date",
                                    value=datetime.now().date(),
                                    minDate=datetime.now().date(),
                                    leftSection=get_icon("material-symbols:calendar-today"),
                                    size="sm",
                                ),
                                span=6,
                            ),
                            dmc.GridCol(
                                dmc.DateInput(
                                    id="end-date",
                                    label="To Date",
                                    value=(datetime.now() + timedelta(days=7)).date(),
                                    minDate=datetime.now().date(),
                                    leftSection=get_icon("material-symbols:event"),
                                    size="sm",
                                ),
                                span=6,
                            ),
                        ],
                    ),
                    
                    dmc.Space(h="sm"),
                    
                    dmc.Button(
                        "Find Best Slot",
                        id="auto-schedule-btn",
                        leftSection=get_icon("material-symbols:auto-awesome"),
                        fullWidth=True,
                    ),
                    dmc.Button(
                        "Preview All Options",
                        id="preview-btn",
                        variant="subtle",
                        leftSection=get_icon("material-symbols:visibility"),
                        fullWidth=True,
                        size="sm",
                    ),
                ],
            ),
        ],
    )


def create_workload_panel():
    """Create the SA workload distribution panel."""
    return dmc.Paper(
        shadow="sm",
        p="lg",
        radius="md",
        withBorder=True,
        style={"backgroundColor": COLORS["white"], "height": "320px"},
        children=[
            dmc.Stack(
                gap="md",
                children=[
                    dmc.Group(
                        justify="space-between",
                        children=[
                            dmc.Title("Team Workload", order=5),
                            dmc.Text("Last 3 weeks", size="xs", c="dimmed"),
                        ],
                    ),
                    dmc.Divider(),
                    dmc.ScrollArea(
                        h=220,
                        type="auto",
                        offsetScrollbars=True,
                        children=html.Div(id="workload-chart"),
                    ),
                ],
            ),
        ],
    )


def create_right_panel():
    """Create the right panel with Result and Upcoming Interviews stacked."""
    return dmc.Stack(
        gap="lg",
        children=[
            # Result Panel - matches Schedule Form height (480px)
            dmc.Paper(
                shadow="sm",
                p="lg",
                radius="md",
                withBorder=True,
                style={"backgroundColor": COLORS["white"], "height": "480px"},
                children=[
                    dmc.Stack(
                        gap="md",
                        style={"height": "100%"},
                        children=[
                            dmc.Group(
                                justify="space-between",
                                children=[
                                    dmc.Title("Result", order=4),
                                    dmc.Badge(
                                        id="result-status",
                                        children="Ready",
                                        variant="light",
                                    ),
                                ],
                            ),
                            dmc.Divider(),
                            html.Div(
                                style={"position": "relative", "flex": "1"},
                                children=[
                                    dmc.LoadingOverlay(
                                        id="result-loading",
                                        visible=False,
                                        loaderProps={"type": "dots"},
                                    ),
                                    dmc.ScrollArea(
                                        h=380,
                                        type="auto",
                                        offsetScrollbars=True,
                                        children=html.Div(
                                            id="result-container",
                                            children=[
                                                dmc.Center(
                                                    style={"height": "360px"},
                                                    children=dmc.Stack(
                                                        align="center",
                                                        gap="xs",
                                                        children=[
                                                            get_icon("material-symbols:calendar-month-outline", height=40),
                                                            dmc.Text("Ready to schedule", c="dimmed", size="sm"),
                                                            dmc.Text(
                                                                "Fill in candidate details and click 'Find Best Slot'",
                                                                size="xs",
                                                                c="dimmed",
                                                            ),
                                                        ],
                                                    ),
                                                )
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            
            # Upcoming Interviews Panel - matches Team Workload height (320px)
            dmc.Paper(
                shadow="sm",
                p="lg",
                radius="md",
                withBorder=True,
                style={"backgroundColor": COLORS["white"], "height": "320px"},
                children=[
                    dmc.Stack(
                        gap="md",
                        children=[
                            dmc.Group(
                                justify="space-between",
                                children=[
                                    dmc.Title("Upcoming Interviews", order=4),
                                    dmc.Badge(
                                        id="interview-count",
                                        children="0",
                                        variant="light",
                                    ),
                                ],
                            ),
                            dmc.Divider(),
                            dmc.ScrollArea(
                                h=220,
                                type="auto",
                                offsetScrollbars=True,
                                children=html.Div(id="interviews-list"),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


# App Layout
app.layout = dmc.MantineProvider(
    theme=THEME,
    children=[
        dmc.AppShell(
            header={"height": 60},
            padding="md",
            children=[
                create_header(),
                dmc.AppShellMain(
                    style={"backgroundColor": COLORS["bg"]},
                    children=dmc.Container(
                        fluid=False,
                        py="lg",
                        children=[
                            dmc.Grid(
                                gutter="lg",
                                children=[
                                    # Left Column - Form & Workload
                                    dmc.GridCol(
                                        dmc.Stack(
                                            gap="lg",
                                            children=[
                                                create_scheduling_form(),
                                                create_workload_panel(),
                                            ],
                                        ),
                                        span={"base": 12, "md": 5},
                                    ),
                                    # Right Column - Result & Upcoming Interviews
                                    dmc.GridCol(
                                        create_right_panel(),
                                        span={"base": 12, "md": 7},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),
        # Stores
        dcc.Store(id="scheduling-result-store", data=None),
        dcc.Interval(id="init-interval", interval=500, max_intervals=1),
    ],
)


# ==================== Callbacks ====================

@callback(
    [
        Output("system-status", "children"),
        Output("system-status", "leftSection"),
        Output("workload-chart", "children"),
    ],
    Input("init-interval", "n_intervals"),
)
def initialize_app(_):
    """Initialize app and show workload distribution."""
    try:
        from services.interview_tracker import get_interview_tracker
        tracker = get_interview_tracker()
        
        stats = tracker.get_workload_stats(since_days=21)
        
        # Create workload bars
        workload_items = []
        max_count = max((s['interview_count'] for s in stats.values()), default=1) or 1
        
        for sa_id, sa_stats in stats.items():
            count = sa_stats['interview_count']
            pct = (count / max_count) * 100 if max_count > 0 else 0
            
            # Determine status color
            if sa_stats['deviation'] < -0.5:
                color = "green"
            elif sa_stats['deviation'] > 0.5:
                color = "orange"
            else:
                color = "blue"
            
            workload_items.append(
                dmc.Stack(
                    gap=4,
                    mb="sm",
                    children=[
                        dmc.Group(
                            justify="space-between",
                            children=[
                                dmc.Text(sa_stats['sa_name'], size="sm"),
                                dmc.Text(f"{count}", size="sm", c="dimmed"),
                            ],
                        ),
                        dmc.Progress(
                            value=pct,
                            color=color,
                            size="sm",
                            radius="xl",
                        ),
                    ],
                )
            )
        
        return (
            "Ready",
            get_icon("material-symbols:check-circle-outline"),
            dmc.Stack(gap="xs", children=workload_items) if workload_items else dmc.Text("No data", c="dimmed", size="sm"),
        )
        
    except Exception as e:
        print(f"Init error: {e}")
        return (
            "Demo Mode",
            get_icon("material-symbols:info-outline"),
            dmc.Text("Running in demo mode", c="dimmed", size="sm"),
        )


@callback(
    [
        Output("result-container", "children"),
        Output("result-status", "children"),
        Output("result-status", "color"),
        Output("result-loading", "visible"),
        Output("scheduling-result-store", "data"),
    ],
    Input("auto-schedule-btn", "n_clicks"),
    [
        State("candidate-name", "value"),
        State("candidate-email", "value"),
        State("interview-type", "value"),
        State("interview-duration", "value"),
        State("start-date", "value"),
        State("end-date", "value"),
    ],
    prevent_initial_call=True,
)
def auto_schedule(n_clicks, candidate_name, candidate_email, interview_type, 
                  duration, start_date, end_date):
    """Run the multi-agent scheduling system."""
    if not n_clicks:
        return no_update, no_update, no_update, False, None
    
    # Validate inputs
    if not candidate_name or not candidate_email or not interview_type:
        return (
            dmc.Alert(
                "Please fill in all required fields.",
                title="Missing Information",
                color="yellow",
                icon=get_icon("material-symbols:warning-outline"),
            ),
            "Incomplete",
            "yellow",
            False,
            None,
        )
    
    try:
        from services.scheduling_agents import get_scheduling_agent
        agent = get_scheduling_agent()
        
        result = agent.schedule_interview(
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            interview_type=interview_type,
            duration_minutes=int(duration or 60),
            preferred_date_start=str(start_date) if start_date else None,
            preferred_date_end=str(end_date) if end_date else None,
        )
        
        if result['status'] == 'success' and result.get('final_assignment'):
            a = result['final_assignment']
            
            content = dmc.Stack(
                gap="lg",
                children=[
                    dmc.Alert(
                        "Interview scheduled successfully",
                        color="green",
                        icon=get_icon("material-symbols:check-circle-outline"),
                    ),
                    
                    dmc.Paper(
                        p="md",
                        radius="md",
                        withBorder=True,
                        style={"borderLeft": f"4px solid {COLORS['lava']}"},
                        children=[
                            dmc.Stack(
                                gap="md",
                                children=[
                                    # Candidate info
                                    dmc.Group(
                                        justify="space-between",
                                        children=[
                                            dmc.Stack(
                                                gap=2,
                                                children=[
                                                    dmc.Text(a['candidate_name'], fw=600, size="lg"),
                                                    dmc.Text(a['candidate_email'], size="sm", c="dimmed"),
                                                ],
                                            ),
                                            dmc.Badge(a['interview_type'], variant="light"),
                                        ],
                                    ),
                                    
                                    dmc.Divider(),
                                    
                                    # Assignment details
                                    dmc.Grid(
                                        gutter="lg",
                                        children=[
                                            dmc.GridCol(
                                                dmc.Stack(
                                                    gap=2,
                                                    children=[
                                                        dmc.Text("Interviewer", size="xs", c="dimmed"),
                                                        dmc.Group(
                                                            gap="xs",
                                                            children=[
                                                                get_icon("material-symbols:person"),
                                                                dmc.Text(a['assigned_sa_name'], fw=500),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                span=6,
                                            ),
                                            dmc.GridCol(
                                                dmc.Stack(
                                                    gap=2,
                                                    children=[
                                                        dmc.Text("When", size="xs", c="dimmed"),
                                                        dmc.Group(
                                                            gap="xs",
                                                            children=[
                                                                get_icon("material-symbols:calendar-today"),
                                                                dmc.Text(f"{a['date_display']} at {a['time_display']}", fw=500),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                span=6,
                                            ),
                                        ],
                                    ),
                                    
                                    dmc.Divider(),
                                    
                                    # Reasoning
                                    dmc.Stack(
                                        gap=4,
                                        children=[
                                            dmc.Text("Why this assignment", size="xs", c="dimmed"),
                                            dmc.Text(
                                                a.get('reasoning', 'Best available match based on workload and availability'),
                                                size="sm",
                                                style={"fontStyle": "italic"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
            
            return content, "Scheduled", "green", False, result
        else:
            return (
                dmc.Alert(
                    result.get('error', 'No available slots found. Try a different date range.'),
                    title="Could not schedule",
                    color="red",
                    icon=get_icon("material-symbols:error-outline"),
                ),
                "Failed",
                "red",
                False,
                None,
            )
            
    except Exception as e:
        print(f"Scheduling error: {e}")
        return (
            dmc.Alert(
                f"Error: {str(e)}",
                color="red",
                icon=get_icon("material-symbols:error-outline"),
            ),
            "Error",
            "red",
            False,
            None,
        )


@callback(
    [
        Output("result-container", "children", allow_duplicate=True),
        Output("result-status", "children", allow_duplicate=True),
        Output("result-status", "color", allow_duplicate=True),
        Output("result-loading", "visible", allow_duplicate=True),
    ],
    Input("preview-btn", "n_clicks"),
    [
        State("interview-type", "value"),
        State("interview-duration", "value"),
        State("start-date", "value"),
        State("end-date", "value"),
    ],
    prevent_initial_call=True,
)
def preview_options(n_clicks, interview_type, duration, start_date, end_date):
    """Preview scheduling options without booking."""
    if not n_clicks:
        return no_update, no_update, no_update, False
    
    if not interview_type:
        return (
            dmc.Alert(
                "Please select an interview type first.",
                color="yellow",
                icon=get_icon("material-symbols:warning-outline"),
            ),
            "Select Type",
            "yellow",
            False,
        )
    
    try:
        from services.scheduling_agents import get_scheduling_agent
        agent = get_scheduling_agent()
        
        preview = agent.get_scheduling_preview(
            interview_type=interview_type,
            duration_minutes=int(duration or 60),
            preferred_date_start=str(start_date) if start_date else None,
            preferred_date_end=str(end_date) if end_date else None,
            top_n=5,
        )
        
        recommendations = preview.get('recommendations', [])
        
        if not recommendations:
            return (
                dmc.Alert(
                    "No available slots found. Try expanding the date range.",
                    color="yellow",
                    icon=get_icon("material-symbols:event-busy"),
                ),
                "No Slots",
                "yellow",
                False,
            )
        
        # Create recommendation list
        rec_items = []
        for i, rec in enumerate(recommendations):
            is_best = i == 0
            
            rec_items.append(
                dmc.Paper(
                    p="sm",
                    radius="sm",
                    withBorder=True,
                    mb="xs",
                    style={
                        "borderLeft": f"3px solid {COLORS['lava'] if is_best else COLORS['border']}",
                        "backgroundColor": COLORS["bg"] if is_best else COLORS["white"],
                    },
                    children=[
                        dmc.Group(
                            justify="space-between",
                            children=[
                                dmc.Stack(
                                    gap=2,
                                    children=[
                                        dmc.Group(
                                            gap="xs",
                                            children=[
                                                dmc.Text(rec['best_sa_name'], fw=500, size="sm"),
                                                dmc.Badge(
                                                    "Best" if is_best else f"#{i+1}",
                                                    size="xs",
                                                    variant="filled" if is_best else "light",
                                                    color="lava" if is_best else "gray",
                                                ),
                                            ],
                                        ),
                                        dmc.Text(
                                            f"{rec['best_sa_interview_count']} recent interviews",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                ),
                                dmc.Stack(
                                    gap=0,
                                    align="flex-end",
                                    children=[
                                        dmc.Text(rec['date'], size="sm", fw=500),
                                        dmc.Text(rec['time'], size="xs", c="dimmed"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            )
        
        content = dmc.Stack(
            gap="md",
            children=[
                dmc.Text(
                    f"Found {preview['total_slots_found']} slots. Top {len(recommendations)} options:",
                    size="sm",
                    c="dimmed",
                ),
                dmc.ScrollArea(
                    h=300,
                    children=dmc.Stack(gap="xs", children=rec_items),
                ),
            ],
        )
        
        return content, f"{len(recommendations)} options", "blue", False
        
    except Exception as e:
        print(f"Preview error: {e}")
        return (
            dmc.Alert(f"Error: {str(e)}", color="red"),
            "Error",
            "red",
            False,
        )


@callback(
    [
        Output("interviews-list", "children"),
        Output("interview-count", "children"),
    ],
    [
        Input("init-interval", "n_intervals"),
        Input("scheduling-result-store", "data"),
    ],
)
def update_interviews_list(_, scheduling_result):
    """Update the list of scheduled interviews."""
    try:
        from services.interview_tracker import get_interview_tracker
        tracker = get_interview_tracker()
        
        upcoming = tracker.get_upcoming_interviews()
        
        if not upcoming:
            return (
                dmc.Center(
                    py="xl",
                    children=dmc.Stack(
                        align="center",
                        gap="xs",
                        children=[
                            get_icon("material-symbols:event-available", height=32),
                            dmc.Text("No upcoming interviews", c="dimmed", size="sm"),
                        ],
                    ),
                ),
                "0",
            )
        
        interview_items = []
        for interview in upcoming[:8]:
            from dateutil import parser as date_parser
            
            try:
                scheduled = date_parser.parse(interview['scheduled_time'])
                date_str = scheduled.strftime("%b %d")
                time_str = scheduled.strftime("%I:%M %p")
            except:
                date_str = "TBD"
                time_str = ""
            
            interview_items.append(
                dmc.Paper(
                    p="sm",
                    radius="sm",
                    withBorder=True,
                    mb="xs",
                    style={"borderLeft": f"3px solid {COLORS['lava']}"},
                    children=[
                        dmc.Group(
                            justify="space-between",
                            children=[
                                dmc.Stack(
                                    gap=2,
                                    children=[
                                        dmc.Text(interview['candidate_name'], fw=500, size="sm"),
                                        dmc.Badge(
                                            interview.get('interview_type', 'Interview'),
                                            size="xs",
                                            variant="light",
                                        ),
                                    ],
                                ),
                                dmc.Stack(
                                    gap=0,
                                    align="flex-end",
                                    children=[
                                        dmc.Text(date_str, size="sm", fw=500),
                                        dmc.Text(time_str, size="xs", c="dimmed"),
                                        dmc.Text(
                                            interview.get('assigned_sa_name', 'TBD'),
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            )
        
        return (
            dmc.Stack(gap="xs", children=interview_items),
            str(len(upcoming)),
        )
        
    except Exception as e:
        print(f"Interview list error: {e}")
        return dmc.Text("Error loading interviews", c="dimmed", size="sm"), "0"


# Run the app
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
