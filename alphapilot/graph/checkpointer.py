import sqlite3
import os
from importlib import import_module

def get_checkpointer():
    """Return SQLite checkpointer if available, else in-memory fallback."""
    try:
        sqlite_module = import_module("langgraph.checkpoint.sqlite")
        sqlite_saver_cls = getattr(sqlite_module, "SqliteSaver")
    except ModuleNotFoundError:
        memory_module = import_module("langgraph.checkpoint.memory")
        memory_saver_cls = getattr(memory_module, "InMemorySaver")
        return memory_saver_cls()

    os.makedirs("./checkpoints", exist_ok=True)
    conn = sqlite3.connect("./checkpoints/alphapilot.db", check_same_thread=False)
    return sqlite_saver_cls(conn)