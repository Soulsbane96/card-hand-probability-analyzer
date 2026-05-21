"""
card_combinations CLI
=====================
Generate all C(deck_size, X) combinations of cards from a deck,
then report aggregate statistics and filtered results.

DECK SOURCES
  • Built-in standard 52-card deck  (default, no --deck flag)
  • CSV file   --deck my_deck.csv   (any columns, any attribute names)
  • Pre-saved combinations CSV  --load-combos hands5.csv  (skip recalculation)

CSV DECK FORMAT
  Each row is one card; column headers become attribute names.

      Rank,Suit,Color,Value
      2,Clubs,Black,2
      Ace,Spades,Black,14

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FILTER DSL   --filter / -f
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRUCTURE
  • Tokens within a clause are comma-separated and ALL must match (AND).
  • Clauses are semicolon-separated; ANY clause matching = hand matches (OR).

TOKEN REFERENCE
  all:<attr>
      Every card shares the same value for <attr>.
      e.g.  all:suit  →  flush

  unique:<attr>
      Every card has a different value for <attr>.
      e.g.  unique:rank  →  all ranks distinct

  straight:<attr>
  straight:<attr>:nowrap   (default — no wrap-around)
      The hand's values form a run of consecutive steps in the deck's
      natural order (CSV row order / built-in rank order).
      All values must be distinct.
      e.g.  straight:rank           →  3 4 5 6 7 (any suits)
            straight:rank,all:suit  →  straight flush

  straight:<attr>:wrap
      Consecutive on a circular ring — the sequence may cross the
      end-of-order boundary (e.g. A-2-3-4-5, Q-K-A-2-3 …).

  pattern:<attr>=n1+n2+…
      The sorted frequency counts of <attr> values match exactly.
      e.g.  pattern:rank=3+2   →  full house
            pattern:rank=4+1   →  four of a kind
            pattern:rank=2+2+1 →  two pair

  nof:<attr>=<n>     some value of <attr> appears exactly <n> times
  nof:<attr>>=<n>    some value of <attr> appears at least <n> times
  nof:<attr><=<n>    some value of <attr> appears at most  <n> times

  <attr>:<value>=<count>   exactly  <count> cards have attr == value
  <attr>:<value>>=<count>  at least <count> cards have attr == value
  <attr>:<value><=<count>  at most  <count> cards have attr == value

EXAMPLES
  -f "all:suit"                         # Flush
  -f "straight:rank"                    # Straight (no wrap)
  -f "straight:rank,all:suit"           # Straight flush
  -f "pattern:rank=3+2"                 # Full house
  -f "pattern:rank=4+1"                 # Four of a kind
  -f "pattern:rank=2+2+1"              # Two pair
  -f "pattern:rank=3+2;pattern:rank=4+1"  # Full house OR four of a kind
  -f "rank:5=2,suit:Hearts=3"           # Exactly 2 Fives AND 3 Hearts
  -f "straight:rank:wrap"               # Wrap-around straight

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAVING & LOADING COMBINATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Generate once and save to disk
  python card_combinations.py -n 5 --save-combos hands5.csv

  # Later: load and apply any filter instantly
  python card_combinations.py --load-combos hands5.csv -f "straight:rank,all:suit"
"""

from __future__ import annotations

import argparse
import itertools
import math
import os

from core.cards import build_standard_deck, get_sequence_order, load_deck_from_csv
from core.filters import parse_filter
from core.io import load_combinations_csv, save_combinations_csv
from core.analysis import check_filter_warnings, compute_stats, print_report
from core.parallel import parallel_compute_stats, parallel_stream_db_to_db, PARALLEL_THRESHOLD
from core.db import (
    open_results_db,
    init_results_db,
    read_stats,
    write_stats,
    export_csv_from_db,
    get_deck_hash,
    find_cache_db,
    make_cache_db_path,
    find_tier1_db,
    make_tier1_db_path,
    TIER1_SIZE_LIMIT,
)


def main():
    """CLI entry point: parse args → load deck or combinations → apply filter → print report."""
    parser = argparse.ArgumentParser(
        description="Analyse all X-card combinations from a deck.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = parser.add_mutually_exclusive_group()
    src.add_argument("--deck", "-D", type=str, default=None, metavar="CSV_FILE",
        help="CSV deck file (one row per card, headers = attributes). "
             "Omit for the built-in 52-card deck.")
    src.add_argument("--load-combos", type=str, default=None, metavar="CSV_FILE",
        help="Load a previously saved combinations CSV to skip recalculation.")

    parser.add_argument("--hand-size", "-n", type=int, default=5,
        help="Cards per combination (default: 5). Ignored with --load-combos.")
    parser.add_argument("--deck-size", "-d", type=int, default=None,
        help="Use only the first N cards of the deck.")
    parser.add_argument("--save-combos", type=str, default=None, metavar="CSV_FILE",
        help="Save all generated combinations to this CSV file for later reuse.")
    parser.add_argument("--filter", "-f", type=str, default="",
        metavar="FILTER_STRING",
        help=(
            "Filter string. Comma = AND within a clause, semicolon = OR between clauses.\n"
            "Tokens: all:<a>  unique:<a>  straight:<a>[:wrap]  pattern:<a>=n+n\n"
            "        nof:<a><op><n>  <a>:<v><op><count>   (op: =  >=  <=)"
        ),
    )
    parser.add_argument("--label-col", type=str, default=None, metavar="COLUMN",
        help="Column to use as card label in verbose output.")
    parser.add_argument("--list-attrs", action="store_true",
        help="Print attribute names and unique values, then exit.")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Print every matching hand (can be very large!).")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load / generate combinations
    # ------------------------------------------------------------------
    if args.load_combos:
        print(f"\nLoading combinations from  {args.load_combos!r} …")
        try:
            combos, attr_names, hand_size = load_combinations_csv(args.load_combos)
        except FileNotFoundError:
            parser.error(f"File not found: {args.load_combos!r}")
        except Exception as exc:
            parser.error(str(exc))
        columns    = attr_names
        print(f"  {len(combos):,} combinations loaded  |  "
              f"Hand size: {hand_size}  |  Attributes: {', '.join(attr_names)}")

    else:
        if args.deck:
            print(f"\nLoading deck from  {args.deck!r} …")
            try:
                deck, columns = load_deck_from_csv(args.deck, args.deck_size)
            except FileNotFoundError:
                parser.error(f"File not found: {args.deck!r}")
            except Exception as exc:
                parser.error(str(exc))
            print(f"  {len(deck)} cards loaded  |  Attributes: {', '.join(columns)}")
        else:
            deck, columns = build_standard_deck(args.deck_size)
            print(f"\nUsing built-in 52-card deck"
                  f"{f' (first {args.deck_size})' if args.deck_size else ''}.")

        attr_names = [c.lower() for c in columns]
        hand_size  = args.hand_size

        if args.list_attrs:
            print("\nCard attributes in this deck:")
            for col in columns:
                key   = col.lower()
                order = get_sequence_order(key)
                vals  = order if order else sorted({c.attr(key) for c in deck})
                print(f"  {col:24}  ({len(vals):>3} unique):  {', '.join(vals)}")
            return

        if hand_size > len(deck):
            parser.error(f"Hand size {hand_size} exceeds deck size {len(deck)}.")

        # Parse filter early so it can be passed to the parallel path.
        filter_spec = parse_filter(args.filter)
        if filter_spec:
            try:
                filter_spec.validate_attrs(attr_names)
            except ValueError as exc:
                parser.error(str(exc))

        warnings    = check_filter_warnings(filter_spec, hand_size) if filter_spec else []
        total_count = math.comb(len(deck), hand_size)

        deck_hash  = "standard" if not args.deck else get_deck_hash(deck, "csv")
        cache_dir  = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "CardHandAnalyzer", "cache",
        )
        filter_str = args.filter.strip()

        if total_count >= PARALLEL_THRESHOLD:
            # tier-2 cache hit (same deck + filter)
            hit = find_cache_db(cache_dir, deck_hash, hand_size, filter_str)
            conn = None
            if hit:
                print(f"\n  Cache hit (tier-2) — loading {hit!r}")
                conn  = open_results_db(hit)
                stats = read_stats(conn)
                if args.save_combos:
                    tier1_path = find_tier1_db(cache_dir, deck_hash, hand_size)
                    export_src = tier1_path or hit
                    ec = open_results_db(export_src)
                    export_csv_from_db(ec, args.save_combos, attr_names)
                    ec.close()
                conn.close()
                conn = None

            else:
                tier1_path = find_tier1_db(cache_dir, deck_hash, hand_size)

                if tier1_path and filter_spec:
                    # fast re-filter from tier-1
                    print(
                        f"\nRe-filtering tier-1 ({total_count:,} combinations) …"
                    )
                    from core.analysis import build_aggregate_checks
                    agg_checks = build_aggregate_checks(
                        attr_names, hand_size, deck, filter_spec
                    )
                    t1_conn = open_results_db(tier1_path)
                    db_path = make_cache_db_path(
                        cache_dir, deck_hash, hand_size, filter_str
                    )
                    t2_conn = open_results_db(db_path)
                    init_results_db(t2_conn, attr_names, hand_size, deck_hash, filter_str)
                    total_c_out, filtered_count = parallel_stream_db_to_db(
                        tier1_path, t2_conn, filter_spec, filter_str,
                        attr_names, agg_checks, deck, hand_size,
                        progress_cb=print,
                    )
                    print(f"  {filtered_count:,} matching / {total_c_out:,} total")
                    if args.save_combos:
                        export_csv_from_db(t1_conn, args.save_combos, attr_names)
                    t1_conn.close()
                    stats = read_stats(t2_conn)
                    conn  = t2_conn

                elif tier1_path and not filter_spec:
                    print(f"\n  Cache hit (tier-1) — loading {tier1_path!r}")
                    conn  = open_results_db(tier1_path)
                    stats = read_stats(conn)
                    if args.save_combos:
                        export_csv_from_db(conn, args.save_combos, attr_names)
                    conn.close()
                    conn = None

                elif total_count <= TIER1_SIZE_LIMIT:
                    # build tier-1 from scratch
                    print(
                        f"\nBuilding tier-1: C({len(deck)}, {hand_size}) = {total_count:,} "
                        f"combinations across {os.cpu_count()} cores …"
                    )
                    t1_db_path = make_tier1_db_path(cache_dir, deck_hash, hand_size)
                    t1_conn    = open_results_db(t1_db_path)
                    init_results_db(
                        t1_conn, attr_names, hand_size, deck_hash,
                        filter_str="", deck=deck,
                    )
                    parallel_compute_stats(
                        deck, hand_size, attr_names,
                        filter_str="", filter_spec=None,
                        progress_cb=print,
                        db_conn=t1_conn,
                        no_cap=True,
                        tier1_deck=deck,
                    )
                    print(f"  Tier-1 complete: {total_count:,} combinations stored.")

                    if filter_spec:
                        print("Deriving tier-2 (applying filter) …")
                        from core.analysis import build_aggregate_checks
                        agg_checks = build_aggregate_checks(
                            attr_names, hand_size, deck, filter_spec
                        )
                        db_path = make_cache_db_path(
                            cache_dir, deck_hash, hand_size, filter_str
                        )
                        t2_conn = open_results_db(db_path)
                        init_results_db(t2_conn, attr_names, hand_size, deck_hash, filter_str)
                        total_c_out, filtered_count = parallel_stream_db_to_db(
                            t1_db_path, t2_conn, filter_spec, filter_str,
                            attr_names, agg_checks, deck, hand_size,
                            progress_cb=print,
                        )
                        print(f"  {filtered_count:,} matching / {total_c_out:,} total")
                        if args.save_combos:
                            export_csv_from_db(t1_conn, args.save_combos, attr_names)
                        t1_conn.close()
                        stats = read_stats(t2_conn)
                        conn  = t2_conn
                    else:
                        if args.save_combos:
                            export_csv_from_db(t1_conn, args.save_combos, attr_names)
                        stats = read_stats(t1_conn)
                        conn  = t1_conn

                else:
                    # too large for tier-1; build tier-2 directly
                    print(
                        f"\nAnalysing C({len(deck)}, {hand_size}) = {total_count:,} "
                        f"combinations across {os.cpu_count()} cores … "
                        f"(deck too large for tier-1 cache)"
                    )
                    db_path = make_cache_db_path(
                        cache_dir, deck_hash, hand_size, filter_str
                    )
                    conn    = open_results_db(db_path)
                    init_results_db(conn, attr_names, hand_size, deck_hash, filter_str)
                    stats = parallel_compute_stats(
                        deck, hand_size, attr_names, filter_str, filter_spec,
                        progress_cb=print,
                        db_conn=conn,
                    )
                    if args.save_combos:
                        export_csv_from_db(conn, args.save_combos, attr_names)
                        print(
                            "  Note: exported filtered hands only (deck too large for "
                            "full-combination tier-1 cache)."
                        )

            if conn is not None:
                conn.close()
        else:
            print(f"\nGenerating C({len(deck)}, {hand_size}) = {total_count:,} combinations …")
            combos = list(itertools.combinations(deck, hand_size))
            if args.save_combos:
                save_combinations_csv(args.save_combos, combos, attr_names)
            stats = compute_stats(combos, filter_spec, attr_names, hand_size, deck)

        print_report(stats, filter_spec, hand_size, attr_names, args.label_col, args.verbose, warnings)
        return

    # ------------------------------------------------------------------
    # load_combos path: parse filter and analyse the pre-loaded list
    # ------------------------------------------------------------------
    filter_spec = parse_filter(args.filter)
    if filter_spec:
        try:
            filter_spec.validate_attrs(attr_names)
        except ValueError as exc:
            parser.error(str(exc))

    warnings = check_filter_warnings(filter_spec, hand_size) if filter_spec else []
    stats = compute_stats(combos, filter_spec, attr_names, hand_size)
    print_report(stats, filter_spec, hand_size, attr_names, args.label_col, args.verbose, warnings)


if __name__ == "__main__":
    main()
