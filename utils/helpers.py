"""Shared formatting and UI helpers (status colours, badges, previews)."""

from datetime import datetime

from analysis import range_checker

# Colours follow the project specification:
# HIGH red, LOW orange, NORMAL green, NOT EVALUATED grey, NEEDS REVIEW yellow.
STATUS_COLORS = {
    range_checker.STATUS_HIGH: "#C62828",
    range_checker.STATUS_LOW: "#E65100",
    range_checker.STATUS_NORMAL: "#2E7D32",
    range_checker.STATUS_NOT_EVALUATED: "#616161",
    range_checker.STATUS_NEEDS_REVIEW: "#B28704",
}

# Soft backgrounds used for table rows / badges (same semantic mapping).
STATUS_BACKGROUNDS = {
    range_checker.STATUS_HIGH: "#FDECEA",
    range_checker.STATUS_LOW: "#FFF3E6",
    range_checker.STATUS_NORMAL: "#EAF5EC",
    range_checker.STATUS_NOT_EVALUATED: "#F0F0F0",
    range_checker.STATUS_NEEDS_REVIEW: "#FFF8DC",
}

# Short labels for badges (the full status string stays in data/exports).
STATUS_BADGE_LABELS = {
    range_checker.STATUS_HIGH: "HIGH",
    range_checker.STATUS_LOW: "LOW",
    range_checker.STATUS_NORMAL: "NORMAL",
    range_checker.STATUS_NOT_EVALUATED: "NOT EVALUATED",
    range_checker.STATUS_NEEDS_REVIEW: "NEEDS REVIEW",
}


def status_badge_html(status: str) -> str:
    """Small rounded badge used in result cards."""
    color = STATUS_COLORS.get(status, "#616161")
    background = STATUS_BACKGROUNDS.get(status, "#F0F0F0")
    label = STATUS_BADGE_LABELS.get(status, status)
    return (
        f'<span style="background:{background};color:{color};'
        f'border:1px solid {color};border-radius:999px;'
        f'padding:2px 12px;font-size:0.8rem;font-weight:700;'
        f'letter-spacing:0.4px;white-space:nowrap;">{label}</span>'
    )


def preview_text(text: str, limit: int = 3000) -> str:
    """Trim long text for on-screen preview."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [{len(text) - limit} more characters]"


def now_display() -> str:
    return datetime.now().strftime("%d %b %Y, %H:%M")
