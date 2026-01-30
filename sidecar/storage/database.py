"""SQLite database for settings and analysis history."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

import platformdirs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    test_type TEXT NOT NULL,
    test_type_display TEXT NOT NULL,
    filename TEXT,
    summary TEXT NOT NULL,
    full_response TEXT NOT NULL,
    liked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    test_type TEXT,
    tone TEXT,
    structure_instructions TEXT,
    closing_text TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    prompt TEXT NOT NULL,
    content TEXT NOT NULL,
    letter_type TEXT NOT NULL DEFAULT 'general'
);
CREATE INDEX IF NOT EXISTS idx_letters_created_at ON letters(created_at);
"""


def _get_db_path() -> str:
    """Return OS-appropriate path for explify.db."""
    data_dir = platformdirs.user_data_dir("Explify")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "explify.db")


class Database:
    """SQLite-backed storage for settings and history."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or _get_db_path()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
            # Migrations for existing databases
            migrations = [
                "ALTER TABLE history ADD COLUMN liked INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE history ADD COLUMN tone_preference INTEGER",
                "ALTER TABLE history ADD COLUMN detail_preference INTEGER",
            ]
            for migration in migrations:
                try:
                    conn.execute(migration)
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # Column already exists
            # Indexes that depend on migrated columns
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_liked ON history(liked)"
            )
            conn.commit()
        finally:
            conn.close()

    # --- Settings ---

    def get_setting(self, key: str) -> str | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_settings(self) -> dict[str, str]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: row["value"] for row in rows}
        finally:
            conn.close()

    def delete_setting(self, key: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    # --- History ---

    def save_history(
        self,
        test_type: str,
        test_type_display: str,
        summary: str,
        full_response: dict[str, Any],
        filename: str | None = None,
        tone_preference: int | None = None,
        detail_preference: int | None = None,
    ) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO history (test_type, test_type_display, filename, summary, full_response, tone_preference, detail_preference)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    test_type,
                    test_type_display,
                    filename,
                    summary,
                    json.dumps(full_response),
                    tone_preference,
                    detail_preference,
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            conn.close()

    def list_history(
        self,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        liked_only: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        conn = self._get_conn()
        try:
            conditions: list[str] = []
            params: list[Any] = []

            if search:
                like = f"%{search}%"
                conditions.append(
                    "(summary LIKE ? OR test_type_display LIKE ? OR filename LIKE ?)"
                )
                params.extend([like, like, like])

            if liked_only:
                conditions.append("liked = 1")

            where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM history{where_clause}",
                params,
            ).fetchone()
            total = count_row["cnt"]

            rows = conn.execute(
                f"""SELECT id, created_at, test_type, test_type_display, filename, summary, liked
                    FROM history{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()

            return [dict(row) for row in rows], total
        finally:
            conn.close()

    def get_history(self, history_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ?", (history_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["full_response"] = json.loads(result["full_response"])
            return result
        finally:
            conn.close()

    def delete_history(self, history_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM history WHERE id = ?", (history_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_history_liked(self, history_id: int, liked: bool) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE history SET liked = ? WHERE id = ?",
                (1 if liked else 0, history_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_liked_examples(
        self,
        limit: int = 2,
        test_type: str | None = None,
        tone_preference: int | None = None,
        detail_preference: int | None = None,
    ) -> list[dict]:
        conn = self._get_conn()
        try:
            conditions = ["liked = 1"]
            params: list[Any] = []
            if test_type:
                conditions.append("test_type = ?")
                params.append(test_type)
            if tone_preference is not None:
                conditions.append("tone_preference = ?")
                params.append(tone_preference)
            if detail_preference is not None:
                conditions.append("detail_preference = ?")
                params.append(detail_preference)
            where_clause = " WHERE " + " AND ".join(conditions)
            params.append(limit)
            rows = conn.execute(
                f"""SELECT full_response FROM history{where_clause}
                    ORDER BY created_at DESC LIMIT ?""",
                params,
            ).fetchall()

            examples: list[dict] = []
            for row in rows:
                try:
                    full_response = json.loads(row["full_response"])
                    explanation = full_response.get("explanation", {})
                    overall_summary = explanation.get("overall_summary", "")
                    key_findings = explanation.get("key_findings", [])[:2]
                    if overall_summary:
                        examples.append({
                            "overall_summary": overall_summary,
                            "key_findings": key_findings,
                        })
                except (json.JSONDecodeError, TypeError):
                    continue
            return examples
        finally:
            conn.close()

    # --- Templates ---

    def create_template(
        self,
        name: str,
        test_type: str | None = None,
        tone: str | None = None,
        structure_instructions: str | None = None,
        closing_text: str | None = None,
    ) -> dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO templates (name, test_type, tone, structure_instructions, closing_text)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, test_type, tone, structure_instructions, closing_text),
            )
            conn.commit()
            return self.get_template(cursor.lastrowid)  # type: ignore[return-value]
        finally:
            conn.close()

    def list_templates(self) -> tuple[list[dict[str, Any]], int]:
        conn = self._get_conn()
        try:
            count_row = conn.execute("SELECT COUNT(*) as cnt FROM templates").fetchone()
            total = count_row["cnt"]
            rows = conn.execute(
                "SELECT * FROM templates ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows], total
        finally:
            conn.close()

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM templates WHERE id = ?", (template_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_template(self, template_id: int, **kwargs: Any) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT * FROM templates WHERE id = ?", (template_id,)
            ).fetchone()
            if not existing:
                return None

            allowed = {"name", "test_type", "tone", "structure_instructions", "closing_text"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return dict(existing)

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(template_id)
            conn.execute(
                f"UPDATE templates SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                values,
            )
            conn.commit()
            return self.get_template(template_id)
        finally:
            conn.close()

    def delete_template(self, template_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM templates WHERE id = ?", (template_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # --- Letters ---

    def save_letter(
        self,
        prompt: str,
        content: str,
        letter_type: str = "general",
    ) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO letters (prompt, content, letter_type)
                   VALUES (?, ?, ?)""",
                (prompt, content, letter_type),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            conn.close()

    def list_letters(self) -> tuple[list[dict[str, Any]], int]:
        conn = self._get_conn()
        try:
            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM letters"
            ).fetchone()
            total = count_row["cnt"]
            rows = conn.execute(
                "SELECT * FROM letters ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows], total
        finally:
            conn.close()

    def get_letter(self, letter_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM letters WHERE id = ?", (letter_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_letter(self, letter_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM letters WHERE id = ?", (letter_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


_db_instance: Database | None = None


def get_db() -> Database:
    """Return the module-level Database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
