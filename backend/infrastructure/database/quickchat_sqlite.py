"""Local QuickChat SQLite location shared by repositories and checkpointer."""

from pathlib import Path

DB_PATH = Path.home() / ".cache" / "searchos" / "quickchat_history.db"
