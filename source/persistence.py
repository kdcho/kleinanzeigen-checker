import sqlite3
from typing import List, Tuple
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bots.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS bots (name TEXT PRIMARY KEY, url TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS filters (filter TEXT PRIMARY KEY)""")
    conn.commit()
    conn.close()


def add_bot(name: str, url: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO bots (name, url) VALUES (?, ?)", (name, url))
    conn.commit()
    conn.close()


def remove_bot(name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM bots WHERE name = ?", (name,))
    conn.commit()
    conn.close()


def clear_bots():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM bots")
    conn.commit()
    conn.close()


def load_bots() -> List[Tuple[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, url FROM bots")
    bots = c.fetchall()
    conn.close()
    return bots


def add_filter(filter_str: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO filters (filter) VALUES (?)", (filter_str,))
    conn.commit()
    conn.close()


def clear_filters():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM filters")
    conn.commit()
    conn.close()


def load_filters() -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filter FROM filters")
    filters = [row[0] for row in c.fetchall()]
    conn.close()
    return filters
