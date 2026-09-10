"""SQLite 持久化：书籍、理解卡、风格画像、生成的书评。"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

# 名称末尾的括号后缀，去重时忽略（视为同一张卡的不同版本）
_RE_SUFFIX = re.compile(r"[（(][^）)]*[）)]\s*$")


def _dedupe_key(name: str) -> str:
    return _RE_SUFFIX.sub("", (name or "").strip())

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash     TEXT UNIQUE NOT NULL,
    title         TEXT,
    author        TEXT,
    fmt           TEXT,
    source_path   TEXT,
    chapter_count INTEGER,
    total_chars   INTEGER,
    created_at    REAL
);
CREATE TABLE IF NOT EXISTS digests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    book_hash  TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS style_profiles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    payload      TEXT NOT NULL,
    sample_count INTEGER DEFAULT 0,
    created_at   REAL,
    updated_at   REAL
);
CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    book_hash  TEXT,
    book_title TEXT,
    profile_id INTEGER,
    length_key TEXT,
    focus_key  TEXT,
    content    TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_digests_book ON digests(book_hash);
CREATE INDEX IF NOT EXISTS idx_reviews_book ON reviews(book_hash);
"""


class DB:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "bookreview.db"
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- books ----------
    def upsert_book(self, book) -> int:
        cur = self.conn.execute(
            """INSERT INTO books (file_hash,title,author,fmt,source_path,chapter_count,total_chars,created_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(file_hash) DO UPDATE SET
                 title=excluded.title, author=excluded.author, fmt=excluded.fmt,
                 source_path=excluded.source_path, chapter_count=excluded.chapter_count,
                 total_chars=excluded.total_chars""",
            (book.file_hash, book.title, book.author, book.fmt, book.source_path,
             book.chapter_count, book.total_chars, time.time()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_books(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM books ORDER BY created_at DESC").fetchall()

    # ---------- digests ----------
    def save_digest(self, book_hash: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO digests (book_hash,payload,created_at) VALUES (?,?,?)",
            (book_hash, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self.conn.commit()

    def get_digest(self, book_hash: str) -> dict | None:
        row = self.conn.execute(
            "SELECT payload FROM digests WHERE book_hash=? ORDER BY id DESC LIMIT 1",
            (book_hash,),
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def clear_digest(self, book_hash: str) -> None:
        self.conn.execute("DELETE FROM digests WHERE book_hash=?", (book_hash,))
        self.conn.commit()

    # ---------- style profiles ----------
    def save_profile(self, name: str, payload: dict, sample_count: int = 0,
                     profile_id: int | None = None) -> int:
        now = time.time()
        blob = json.dumps(payload, ensure_ascii=False)
        if profile_id:
            self.conn.execute(
                "UPDATE style_profiles SET name=?,payload=?,sample_count=?,updated_at=? WHERE id=?",
                (name, blob, sample_count, now, profile_id),
            )
            self.conn.commit()
            return profile_id
        cur = self.conn.execute(
            "INSERT INTO style_profiles (name,payload,sample_count,created_at,updated_at)"
            " VALUES (?,?,?,?,?)",
            (name, blob, sample_count, now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_profiles(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM style_profiles ORDER BY updated_at DESC").fetchall()

    def get_profile(self, profile_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM style_profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return None
        d = json.loads(row["payload"])
        d["id"] = row["id"]
        d["name"] = row["name"]
        d["sample_count"] = row["sample_count"]
        return d

    def rename_profile(self, profile_id: int, name: str) -> None:
        self.conn.execute(
            "UPDATE style_profiles SET name=?, updated_at=? WHERE id=?",
            (name, time.time(), profile_id),
        )
        self.conn.commit()

    def find_profile_by_name(self, name: str) -> sqlite3.Row | None:
        """按名称精确查找，同名时返回 id 最大的（最新的）那张。"""
        return self.conn.execute(
            "SELECT * FROM style_profiles WHERE name=? ORDER BY id DESC",
            (name,),
        ).fetchone()

    def plan_dedupe_profiles(self) -> list[dict]:
        """找出重复的风格卡。

        分组键会去掉名称末尾的括号后缀，所以
        「非帅·推理向」「非帅·推理向(防泄底)」「非帅·推理向(防泄底v3)」
        会被视为同一张卡的三个版本，只保留 id 最大的（最新的）。
        """
        rows = self.conn.execute(
            "SELECT id, name, updated_at FROM style_profiles ORDER BY id ASC"
        ).fetchall()
        groups: dict[str, list[int]] = {}
        names: dict[int, str] = {}
        for r in rows:
            groups.setdefault(_dedupe_key(r["name"]), []).append(r["id"])
            names[r["id"]] = r["name"]
        out: list[dict] = []
        for key, ids in groups.items():
            if len(ids) < 2:
                continue
            keep = max(ids)
            out.append({
                "key": key,
                "keep": keep,
                "keep_name": names[keep],
                "remove": [i for i in ids if i != keep],
                "remove_names": [names[i] for i in ids if i != keep],
            })
        return out

    def apply_dedupe_profiles(self, plan: list[dict]) -> int:
        """执行去重：把被删卡片的书评改指向保留的那张，再删除旧卡。"""
        n = 0
        for g in plan:
            for old in g["remove"]:
                self.conn.execute(
                    "UPDATE reviews SET profile_id=? WHERE profile_id=?",
                    (g["keep"], old),
                )
                self.conn.execute("DELETE FROM style_profiles WHERE id=?", (old,))
                n += 1
        self.conn.commit()
        return n

    def delete_profile(self, profile_id: int) -> None:
        self.conn.execute("DELETE FROM style_profiles WHERE id=?", (profile_id,))
        self.conn.commit()

    # ---------- reviews ----------
    def save_review(self, book_hash: str, book_title: str, profile_id: int | None,
                    length_key: str, focus_key: str, content: str) -> int:
        cur = self.conn.execute(
            """INSERT INTO reviews (book_hash,book_title,profile_id,length_key,focus_key,content,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (book_hash, book_title, profile_id, length_key, focus_key, content, time.time()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_reviews(self, book_hash: str | None = None) -> list[sqlite3.Row]:
        if book_hash:
            return self.conn.execute(
                "SELECT * FROM reviews WHERE book_hash=? ORDER BY created_at DESC",
                (book_hash,)).fetchall()
        return self.conn.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC").fetchall()

    def close(self) -> None:
        self.conn.close()
