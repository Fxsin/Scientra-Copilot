"""Asset status definitions and transition rules."""

ASSET_STATUSES = [
    "registered",
    "pending",
    "processing",
    "processed",
    "failed",
    "skipped",
]

VALID_TRANSITIONS: dict[str, list[str]] = {
    "registered": ["pending", "skipped"],
    "pending": ["processing", "skipped"],
    "processing": ["processed", "failed"],
    "processed": [],
    "failed": ["pending"],
    "skipped": ["pending"],
}


def can_transition(current: str, target: str) -> bool:
    """Check if a status transition is valid."""
    if current not in VALID_TRANSITIONS:
        return False
    return target in VALID_TRANSITIONS[current]
