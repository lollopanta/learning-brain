class BrainError(Exception):
    """Actionable workflow failure, safe to show without a traceback."""


class Conflict(BrainError):
    """An input changed since acquisition or review. Never overwrite it."""
