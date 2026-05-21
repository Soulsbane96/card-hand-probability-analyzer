from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter
from typing import Dict, List, Optional, Tuple

from core.cards import Card


INSERT_BATCH_SIZE = 10_000
PAGE_CACHE_SIZE   = 500
MAX_SEARCHABLE    = 2_000_000


def open_results_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_results_db(
    conn: sqlite3.Connection,
    attr_names: List[str],
    hand_size: int,
    deck_hash: str,
    filter_str: str,
) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS filtered_hands (
            hand_id   INTEGER PRIMARY KEY,
            hand_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agg_counts (
            label     TEXT PRIMARY KEY,
            count     INTEGER NOT NULL,
            is_filter INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attr_freq (
            attr  TEXT NOT NULL,
            value TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (attr, value)
        );
    """)
    conn.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("attr_names", json.dumps(attr_names)),
            ("hand_size",  str(hand_size)),
            ("deck_hash",  deck_hash),
            ("filter_str", filter_str),
        ],
    )
    conn.commit()


def insert_filtered_hands_batch(
    conn: sqlite3.Connection,
    hands: List[Tuple[Card, ...]],
    attr_names: List[str],
) -> None:
    if not hands:
        return
    rows = [
        (json.dumps([{a: card.attr(a) for a in attr_names} for card in hand]),)
        for hand in hands
    ]
    conn.executemany("INSERT INTO filtered_hands (hand_json) VALUES (?)", rows)
    conn.commit()


def write_stats(
    conn: sqlite3.Connection,
    agg_checks,
    agg_counts: Dict[str, int],
    attr_freq,
    total: int,
    filtered_count: int,
) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO agg_counts (label, count, is_filter) VALUES (?, ?, ?)",
        [
            (label, agg_counts.get(label, 0), 1 if is_filter else 0)
            for label, _, is_filter in agg_checks
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO attr_freq (attr, value, count) VALUES (?, ?, ?)",
        [
            (attr, value, count)
            for attr, freq in attr_freq.items()
            for value, count in freq.items()
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("total_count",    str(total)),
            ("filtered_count", str(filtered_count)),
        ],
    )
    conn.commit()


def query_hand_page(
    conn: sqlite3.Connection,
    offset: int,
    limit: int,
    attr_names: List[str],
) -> List[Tuple[Card, ...]]:
    rows = conn.execute(
        "SELECT hand_json FROM filtered_hands ORDER BY hand_id LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    result = []
    for (hand_json,) in rows:
        cards_data = json.loads(hand_json)
        hand = tuple(Card(d) for d in cards_data)
        result.append(hand)
    return result


def count_filtered_hands(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM filtered_hands").fetchone()
    return row[0] if row else 0


def read_stats(conn: sqlite3.Connection) -> dict:
    meta = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
    attr_names     = json.loads(meta.get("attr_names", "[]"))
    total          = int(meta.get("total_count",    0))
    filtered_count = int(meta.get("filtered_count", 0))

    agg_rows   = conn.execute(
        "SELECT label, count, is_filter FROM agg_counts ORDER BY rowid"
    ).fetchall()
    agg_counts = {label: count for label, count, _ in agg_rows}
    agg_checks = [
        (label, None, bool(is_filter)) for label, _, is_filter in agg_rows
    ]

    freq_rows  = conn.execute("SELECT attr, value, count FROM attr_freq").fetchall()
    attr_freq: Dict[str, Counter] = {a: Counter() for a in attr_names}
    for attr, value, count in freq_rows:
        if attr in attr_freq:
            attr_freq[attr][value] = count

    return {
        "total_combinations": total,
        "filtered_count":     filtered_count,
        "agg_checks":         agg_checks,
        "agg_counts":         agg_counts,
        "attr_freq":          attr_freq,
        "filtered_hands":     [],
    }


def export_csv_from_db(
    conn: sqlite3.Connection,
    csv_path: str,
    attr_names: List[str],
) -> None:
    first = conn.execute(
        "SELECT hand_json FROM filtered_hands LIMIT 1"
    ).fetchone()
    if not first:
        print("  (no combinations to export)")
        return
    hand_size = len(json.loads(first[0]))
    headers   = [f"card{i+1}_{a}" for i in range(hand_size) for a in attr_names]
    total     = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT hand_json FROM filtered_hands ORDER BY hand_id LIMIT ? OFFSET ?",
                (INSERT_BATCH_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            for (hand_json,) in rows:
                cards_data = json.loads(hand_json)
                writer.writerow([d[a] for d in cards_data for a in attr_names])
                total += 1
            offset += INSERT_BATCH_SIZE
    print(f"  Exported {total:,} combinations  →  {csv_path!r}")


def get_deck_hash(deck: List[Card], deck_source: str) -> str:
    if deck_source == "standard":
        return "standard"
    content = "|".join(
        ":".join(f"{k}={card.attr(k)}" for k in sorted(card._attrs.keys()))
        for card in deck
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def find_cache_db(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
    filter_str: str,
) -> Optional[str]:
    if not os.path.isdir(cache_dir):
        return None
    filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:8]
    db_path     = os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_{filter_hash}.db")
    if not os.path.isfile(db_path):
        return None
    try:
        c   = sqlite3.connect(db_path)
        row = c.execute(
            "SELECT value FROM metadata WHERE key = 'total_count'"
        ).fetchone()
        c.close()
        if row and int(row[0]) > 0:
            return db_path
    except Exception:
        pass
    return None


def make_cache_db_path(
    cache_dir: str,
    deck_hash: str,
    hand_size: int,
    filter_str: str,
) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:8]
    return os.path.join(cache_dir, f"{deck_hash}_h{hand_size}_{filter_hash}.db")
