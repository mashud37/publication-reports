import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "data/publications.db")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                doi TEXT UNIQUE,
                title TEXT,
                authors TEXT,
                abstract TEXT,
                journal_name TEXT,
                journal_group TEXT,
                week_date TEXT
            );
            CREATE TABLE IF NOT EXISTS selections (
                id INTEGER PRIMARY KEY,
                article_id INTEGER REFERENCES articles(id),
                selected INTEGER,
                week_date TEXT,
                UNIQUE(article_id, week_date)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                week_date TEXT PRIMARY KEY,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS training (
                id INTEGER PRIMARY KEY,
                title TEXT,
                abstract TEXT,
                selected INTEGER
            );
        """)


def load_historical(csv_path):
    import pandas as pd
    with _conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM training").fetchone()[0] > 0:
            return
    df = pd.read_csv(csv_path)
    df = df[df["label"].notna()]
    with _conn() as conn:
        for _, row in df.iterrows():
            conn.execute(
                "INSERT INTO training (title, abstract, selected) VALUES (?, ?, ?)",
                (str(row.get("title", "")), str(row.get("abstract", "")), int(row["label"]))
            )
    print(f"Loaded {len(df)} historical labels from {csv_path}")


def save_articles(articles):
    with _conn() as conn:
        for a in articles:
            conn.execute("""
                INSERT OR IGNORE INTO articles
                    (doi, title, authors, abstract, journal_name, journal_group, week_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                a["doi"],
                a["title"],
                a["authors"],
                a["abstract"],
                a["journal_name"],
                a["journal_group"],
                a["week_date"],
            ))


def get_week_articles(week_date):
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM articles WHERE week_date = ?", (week_date,)
        ).fetchall()]


def save_session(week_date, selected_ids, all_ids):
    selected_set = set(str(i) for i in selected_ids)
    with _conn() as conn:
        for aid in all_ids:
            sel = 1 if str(aid) in selected_set else 0
            conn.execute(
                "INSERT OR IGNORE INTO selections (article_id, selected, week_date) VALUES (?, ?, ?)",
                (aid, sel, week_date)
            )
            row = conn.execute(
                "SELECT title, abstract FROM articles WHERE id = ?", (aid,)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO training (title, abstract, selected) VALUES (?, ?, ?)",
                    (row["title"], row["abstract"], sel)
                )
        conn.execute(
            "INSERT OR REPLACE INTO sessions (week_date, completed_at) VALUES (?, datetime('now'))",
            (week_date,)
        )


def session_done(week_date):
    with _conn() as conn:
        return conn.execute(
            "SELECT 1 FROM sessions WHERE week_date = ?", (week_date,)
        ).fetchone() is not None


def get_session_selections(week_date):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT article_id FROM selections WHERE week_date = ? AND selected = 1", (week_date,)
        ).fetchall()
        return {r["article_id"] for r in rows}


def get_training_data():
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT title, abstract, selected FROM training"
        ).fetchall()]
