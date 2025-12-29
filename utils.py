"""
Utility functions for the TA Interview Scheduler app.
"""

from dash import dash_table
from dash_iconify import DashIconify


def get_icon(icon: str, height: int = 16):
    """Get a DashIconify icon component."""
    return DashIconify(icon=icon, height=height)


def create_data_table(table_id: str):
    """Create a styled DataTable component."""
    return dash_table.DataTable(
        id=table_id,
        style_table={
            "marginTop": "20px",
            "width": "100%",
            "overflowX": "auto"
        },
        style_header={
            "backgroundColor": "#1B3A4B",
            "color": "#FFFFFF",
            "fontWeight": "bold",
            "fontFamily": "DM Sans, sans-serif",
            "border": "1px solid #2D5A6B",
            "textAlign": "center",
        },
        style_cell={
            "textAlign": "left",
            "padding": "12px",
            "fontFamily": "DM Sans, sans-serif",
            "minWidth": "100px",
            "width": "150px",
            "maxWidth": "300px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "border": "1px solid #E0E0E0",
        },
        style_data={
            "whiteSpace": "normal",
            "height": "auto",
            "backgroundColor": "#FFFFFF",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#F5F9FA",
            },
            {
                "if": {"state": "selected"},
                "backgroundColor": "#D4E8ED",
                "border": "1px solid #1B3A4B",
            }
        ],
        page_size=10,
        sort_action="native",
        filter_action="native",
        row_selectable="single",
        selected_rows=[],
    )


def format_datetime(dt_str: str) -> str:
    """Format ISO datetime string to human-readable format."""
    from dateutil import parser
    try:
        dt = parser.parse(dt_str)
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except Exception:
        return dt_str


def format_time_slot(start_str: str, end_str: str) -> str:
    """Format time slot for display."""
    from dateutil import parser
    try:
        start = parser.parse(start_str)
        end = parser.parse(end_str)
        return f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
    except Exception:
        return f"{start_str} - {end_str}"


