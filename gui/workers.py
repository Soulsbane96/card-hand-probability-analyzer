from __future__ import annotations

import hashlib
import itertools
import math
import os
import sqlite3
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

from core import (
    load_combinations_csv,
    load_deck_from_csv,
    build_standard_deck,
    save_combinations_csv,
    parse_filter,
    check_filter_warnings,
    compute_stats,
)
from core.parallel import parallel_compute_stats, PARALLEL_THRESHOLD
from core.db import (
    open_results_db,
    init_results_db,
    write_stats,
    read_stats,
    export_csv_from_db,
    get_deck_hash,
    find_cache_db,
    make_cache_db_path,
    MAX_SEARCHABLE,
)
from core.io import stream_combinations_csv_to_db


def _default_cache_dir() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(local_app_data, "CardHandAnalyzer", "cache")


# ---------------------------------------------------------------------------
# Background worker — full analysis pipeline
# ---------------------------------------------------------------------------

class AnalysisWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict, object)   # stats dict, FilterSpec | None
    error    = pyqtSignal(str)

    def __init__(self, params: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.params = params
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        try:
            p          = self.params
            source     = p["source"]
            cache_dir  = p.get("cache_dir") or _default_cache_dir()

            if source == "load_combos":
                csv_path    = p["load_path"]
                filter_str  = p.get("filter_str", "").strip()
                filter_spec = parse_filter(filter_str)

                # Peek headers first so we have hand_size for the cache key
                import csv as _csv
                with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                    reader     = _csv.DictReader(fh)
                    headers    = [h.strip() for h in (reader.fieldnames or [])]
                    card1_attrs = [h[len("card1_"):] for h in headers if h.lower().startswith("card1_")]
                    if not card1_attrs:
                        raise ValueError(
                            "Cannot parse combinations CSV — expected columns like 'card1_rank' …"
                        )
                    attr_names = card1_attrs
                    hand_size  = sum(
                        1 for h in headers
                        if h.lower().endswith(f"_{attr_names[0].lower()}")
                    )

                if filter_spec:
                    filter_spec.validate_attrs(attr_names)
                warnings = check_filter_warnings(filter_spec, hand_size) if filter_spec else []

                # Hash the CSV file content for cache keying
                csv_hash = _hash_file(csv_path)

                hit = find_cache_db(cache_dir, csv_hash, hand_size, filter_str)
                if hit:
                    self.progress.emit(f"Cache hit — opening {hit!r} …")
                    conn  = open_results_db(hit)
                    stats = read_stats(conn)
                    import json as _json
                    meta       = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
                    attr_names = _json.loads(meta.get("attr_names", "[]"))
                    hand_size  = int(meta.get("hand_size", hand_size))
                    conn.close()
                    stats["db_path"] = hit
                else:
                    db_path = make_cache_db_path(cache_dir, csv_hash, hand_size, filter_str)
                    conn    = open_results_db(db_path)
                    init_results_db(conn, attr_names, hand_size, csv_hash, filter_str)

                    self.progress.emit("Streaming CSV to database …")
                    total_count, filtered_count = stream_combinations_csv_to_db(
                        csv_path, conn, filter_spec, attr_names, hand_size,
                        progress_cb=self.progress.emit,
                    )
                    self.progress.emit(
                        f"  {filtered_count:,} matching / {total_count:,} total"
                    )

                    # Build agg_counts and attr_freq by iterating the DB
                    from core.db import query_hand_page, count_filtered_hands
                    from core.analysis import build_aggregate_checks
                    from collections import Counter
                    from core.db import INSERT_BATCH_SIZE

                    # Reconstruct a minimal unique-card set from a sample of hands.
                    sample_hands = query_hand_page(conn, 0, min(1000, filtered_count), attr_names)
                    deck_cards   = list({card for hand in sample_hands for card in hand})

                    agg_checks = build_aggregate_checks(attr_names, hand_size, deck_cards, filter_spec)
                    agg_counts = {label: 0 for label, _, _ in agg_checks}
                    attr_freq: dict = {a: Counter() for a in attr_names}

                    offset = 0
                    while True:
                        page = query_hand_page(conn, offset, INSERT_BATCH_SIZE, attr_names)
                        if not page:
                            break
                        for hand in page:
                            for label, fn, _ in agg_checks:
                                if fn and fn(hand):
                                    agg_counts[label] += 1
                            for card in hand:
                                for attr in attr_names:
                                    attr_freq[attr][card.attr(attr)] += 1
                        offset += INSERT_BATCH_SIZE

                    write_stats(conn, agg_checks, agg_counts, attr_freq, total_count, filtered_count)
                    stats = read_stats(conn)
                    conn.close()
                    stats["db_path"] = db_path

                stats["combinations"] = []

            else:
                # -----------------------------------------------------------------
                # Deck-generation path (standard or csv)
                # -----------------------------------------------------------------
                if source == "csv":
                    self.progress.emit(f"Loading deck from {p['deck_path']!r} …")
                    deck, columns = load_deck_from_csv(p["deck_path"], p["deck_size"])
                    self.progress.emit(
                        f"  {len(deck)} cards | attributes: {', '.join(columns)}"
                    )
                    deck_hash = get_deck_hash(deck, "csv")
                else:
                    deck, columns = build_standard_deck(p["deck_size"])
                    self.progress.emit("Using built-in 52-card deck.")
                    deck_hash = "standard"

                attr_names = [c.lower() for c in columns]
                hand_size  = p["hand_size"]
                filter_str  = p.get("filter_str", "").strip()
                filter_spec = parse_filter(filter_str)
                if filter_spec:
                    filter_spec.validate_attrs(attr_names)

                total_c  = math.comb(len(deck), hand_size)
                warnings = check_filter_warnings(filter_spec, hand_size) if filter_spec else []

                # ------ cache check ------
                hit = find_cache_db(cache_dir, deck_hash, hand_size, filter_str)
                if hit:
                    self.progress.emit(f"Cache hit — opening {hit!r} …")
                    conn  = open_results_db(hit)
                    stats = read_stats(conn)
                    if p.get("save_path"):
                        self.progress.emit(f"Saving combinations → {p['save_path']!r} …")
                        export_csv_from_db(conn, p["save_path"], attr_names)
                    conn.close()
                    stats["db_path"]     = hit
                    stats["combinations"] = []
                elif total_c >= PARALLEL_THRESHOLD:
                    self.progress.emit(
                        f"Analysing C({len(deck)}, {hand_size}) = {total_c:,} combinations "
                        f"across {os.cpu_count()} cores …"
                    )
                    db_path = make_cache_db_path(cache_dir, deck_hash, hand_size, filter_str)
                    conn    = open_results_db(db_path)
                    init_results_db(conn, attr_names, hand_size, deck_hash, filter_str)

                    stats = parallel_compute_stats(
                        deck, hand_size, attr_names, filter_str, filter_spec,
                        progress_cb=self.progress.emit,
                        abort_flag=lambda: self._abort,
                        db_conn=conn,
                    )
                    if p.get("save_path"):
                        self.progress.emit(f"Saving combinations → {p['save_path']!r} …")
                        export_csv_from_db(conn, p["save_path"], attr_names)
                    conn.close()
                    stats["db_path"]     = db_path
                    stats["combinations"] = []
                else:
                    self.progress.emit(
                        f"Generating C({len(deck)}, {hand_size}) = {total_c:,} combinations …"
                    )
                    combos = list(itertools.combinations(deck, hand_size))
                    if p.get("save_path"):
                        save_combinations_csv(p["save_path"], combos, attr_names)
                        self.progress.emit(f"Saved combinations → {p['save_path']!r}")
                    self.progress.emit("Computing statistics …")
                    stats = compute_stats(combos, filter_spec, attr_names, hand_size, deck)
                    stats["combinations"] = combos

            stats["warnings"]   = warnings
            stats["attr_names"] = attr_names
            stats["hand_size"]  = hand_size
            stats["label_col"]  = p.get("label_col")
            stats["verbose"]    = p.get("verbose", False)

            self.finished.emit(stats, filter_spec)
        except Exception as exc:
            self.error.emit(str(exc))


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Background worker — search and sort for the combinations table
# ---------------------------------------------------------------------------

class SearchSortWorker(QThread):
    """Off-thread search and sort so the UI never freezes on large datasets."""

    finished = pyqtSignal(list)
    aborted  = pyqtSignal()

    def __init__(
        self,
        combinations: List[Tuple],
        matched_indices: frozenset,
        search_text: str,
        show_only_matches: bool,
        sort_col: int,
        sort_order: Qt.SortOrder,
        hand_size: int,
        label_col: Optional[str],
        db_path: Optional[str] = None,
        filtered_count: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._combinations     = combinations
        self._matched_indices  = matched_indices
        self._search_text      = search_text.lower()
        self._show_only        = show_only_matches
        self._sort_col         = sort_col
        self._sort_order       = sort_order
        self._hand_size        = hand_size
        self._label_col        = label_col
        self._db_path          = db_path
        self._filtered_count   = filtered_count
        self._abort            = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        if self._db_path is not None:
            self._run_db_mode()
        else:
            self._run_list_mode()

    def _run_db_mode(self) -> None:
        from core.db import query_hand_page, INSERT_BATCH_SIZE

        conn  = open_results_db(self._db_path)
        lc    = self._label_col
        text  = self._search_text

        # Result is a list of (hand_id, hand) pairs — hand_id acts as the stable index
        # for the table model.  We emit row indices into the DB page-cache, not into
        # a Python list, so emit sequential ints 0..N-1 matching DB ORDER BY hand_id.
        total = self._filtered_count

        if total > MAX_SEARCHABLE and (text or self._show_only):
            conn.close()
            self.finished.emit(list(range(total)))
            return

        if not text and not self._show_only and self._sort_col < 0:
            conn.close()
            self.finished.emit(list(range(total)))
            return

        # Fetch all hands to search/sort (only when ≤ MAX_SEARCHABLE)
        all_hands: List[Tuple] = []
        offset = 0
        while True:
            if self._abort:
                conn.close()
                self.aborted.emit()
                return
            page = query_hand_page(conn, offset, INSERT_BATCH_SIZE, [])
            if not page:
                break
            all_hands.extend(page)
            offset += INSERT_BATCH_SIZE

        candidates = list(range(len(all_hands)))

        if text:
            filtered_idxs = []
            for i in candidates:
                if self._abort:
                    self.aborted.emit()
                    return
                if any(text in card.label(lc).lower() for card in all_hands[i]):
                    filtered_idxs.append(i)
            candidates = filtered_idxs

        if self._sort_col >= 0 and not self._abort:
            col     = self._sort_col
            reverse = self._sort_order == Qt.SortOrder.DescendingOrder
            candidates.sort(
                key=lambda i: all_hands[i][col].label(lc).lower() if col < len(all_hands[i]) else "",
                reverse=reverse,
            )

        if self._abort:
            conn.close()
            self.aborted.emit()
            return

        conn.close()
        self.finished.emit(candidates)

    def _run_list_mode(self) -> None:
        combos = self._combinations
        lc     = self._label_col

        if self._show_only:
            candidates = sorted(self._matched_indices)
        else:
            candidates = list(range(len(combos)))

        text = self._search_text
        if text:
            filtered: List[int] = []
            for i, idx in enumerate(candidates):
                if self._abort:
                    self.aborted.emit()
                    return
                if any(text in card.label(lc).lower() for card in combos[idx]):
                    filtered.append(idx)
                if i % 50_000 == 0 and self._abort:
                    self.aborted.emit()
                    return
            candidates = filtered

        if self._sort_col >= 0 and not self._abort:
            col     = self._sort_col
            reverse = self._sort_order == Qt.SortOrder.DescendingOrder
            candidates.sort(
                key=lambda i: combos[i][col].label(lc).lower(),
                reverse=reverse,
            )

        if self._abort:
            self.aborted.emit()
            return

        self.finished.emit(candidates)
