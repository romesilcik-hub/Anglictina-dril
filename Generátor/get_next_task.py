#!/usr/bin/env python3
"""
get_next_task.py — Determines the next grammar*topic combination for AJ Dril sentence generation.

Usage (sequential mode -- default):
  python3 get_next_task.py --get-next
  python3 get_next_task.py --mark-done --level B1 --grammar "Trpny rod" --topic "Hotel a recepce"
  python3 get_next_task.py --status

Usage (frequency mode -- after first pass is complete):
  python3 get_next_task.py --freq-mode --get-next
  python3 get_next_task.py --freq-mode --mark-done --level B1 --grammar "Trpny rod" --topic "Hotel a recepce"
  python3 get_next_task.py --freq-mode --status

Frequency mode reads aj_dril_databaze.json and Frekvence anglictiny.csv to calculate
how many blocks each grammar*topic*level combination needs, then picks the one with
the highest deficit (weighted by corpus frequency).

Target blocks per grammar*topic*level:
  freq >= 5 %  ->  30 blocks  (3 passes)
  freq >= 2 %  ->  20 blocks  (2 passes)
  freq  < 2 %  ->  10 blocks  (1 pass)

Sequential mode state: aj_dril_state.json -> {"index": N}
Frequency mode state:  aj_dril_state.json -> {"freq_done": [[level, grammar, topic], ...]}
"""

import csv
import json
import sys
import argparse
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from datetime import date

# Paths -- script is in Generátor/, project root is one level up
BASE        = Path(__file__).resolve().parent.parent
TEMATA_FILE = BASE / "Generátor" / "temata.txt"
CONFIG_FILE = BASE / "aj_dril_generator_config.json"
STATE_FILE  = BASE / "aj_dril_state.json"
PROMPTY_DIR = BASE / "Prompty"
DB_FILE     = BASE / "aj_dril_databaze.json"
FREQ_FILE   = BASE / "Frekvence angličtiny.csv"

LEVEL_ORDER = ["A0", "A1", "A2", "B1"]

PAT_LABELS = {
    "affirmative": "Oznamovaci veta -- stridej osoby: I / you / he/she/it / they (person: first / second / third_singular / plural)",
    "negative":    "Zaporná veta -- stridej osoby: I / you / he/she/it / they (person: first / second / third_singular / plural)",
    "question":    'Otazka (ano/ne) -- person: ""',
    "wh_question": 'WH otazka (co/kde/kdy...) -- person: ""',
    "imperative":  'Rozkazovaci veta -- person: ""',
    "comparison":  'Srovnani -- person: ""',
    "tag_question": 'Dovetek (question tag) -- person: ""',
    "time_clause": 'Casova veta -- person: ""',
    "passive":     'Trpny rod -- person: ""',
    "indirect":    'Nepriama rec -- person: ""',
    "conditional": 'Podminkova veta -- person: ""',
}


# ============================================================
# Shared helpers
# ============================================================

def read_topics():
    topics = []
    with open(TEMATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                topics.append(line)
    return topics


def read_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def read_state():
    if not STATE_FILE.exists():
        return {"index": 0, "last_updated": str(date.today())}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_state(state):
    state["last_updated"] = str(date.today())
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def to_safe_filename(s):
    nfkd = unicodedata.normalize("NFD", s)
    no_diac = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    clean = re.sub(r"[^a-zA-Z0-9_\- ]", "", no_diac)
    return clean.strip().replace(" ", "_")


def build_tsv_path(level, grammar, topic):
    today = date.today().strftime("%Y-%m-%d")
    gr  = to_safe_filename(grammar)[:40]
    top = to_safe_filename(topic)[:30]
    filename = f"{level}_{gr}_{top}_{today}.tsv"
    return str(PROMPTY_DIR / filename)


def get_patterns_for_grammar(config, level, grammar):
    level_patterns = config["levels"][level]["patterns"]
    exclude = config.get("grammar_pattern_exclude", {}).get(grammar, [])
    return [p for p in level_patterns if p not in exclude]


def get_level_guard(config, level):
    cur_idx = LEVEL_ORDER.index(level)
    forbidden = []
    for lvl in LEVEL_ORDER[cur_idx + 1:]:
        forbidden.extend(config["levels"][lvl]["grammar_items"])
    if not forbidden:
        return ""
    return (
        "\nLEVEL RESTRICTION (strictly follow):\n"
        "Sentences must match level " + level + " -- do not use any grammar constructions above this level.\n"
        "Forbidden constructions for this level: " + ", ".join(forbidden) + ".\n"
    )


def build_all_combos(config, topics):
    """Fixed sequential order: topic -> level -> grammar (as in config)."""
    combos = []
    for topic in topics:
        for level in LEVEL_ORDER:
            for grammar in config["levels"][level]["grammar_items"]:
                combos.append((level, grammar, topic))
    return combos


def build_patterns_list(patterns):
    return "\n".join(
        "   {}. {} (pattern: {})".format(i + 1, PAT_LABELS.get(p, p), p)
        for i, p in enumerate(patterns)
    )


# ============================================================
# Frequency mode helpers
# ============================================================

def get_target_blocks(freq_pct):
    """How many total blocks a grammar*topic*level combo should have."""
    if freq_pct >= 5.0:
        return 30
    elif freq_pct >= 2.0:
        return 20
    else:
        return 10


def read_frequency_csv():
    """Return dict: grammar_name -> frequency_percent (float)."""
    freq = {}
    with open(FREQ_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)  # title row
        next(reader)  # column headers
        for row in reader:
            if len(row) < 2:
                continue
            grammar = row[0].strip()
            if not grammar or grammar == "CELKEM":
                continue
            pct_str = row[1].strip().replace(",", ".").replace("%", "")
            try:
                freq[grammar] = float(pct_str)
            except ValueError:
                pass
    return freq


def read_database_counts():
    """Return dict: (grammar, topic, level) -> number of blocks in DB."""
    if not DB_FILE.exists():
        return {}
    with open(DB_FILE, encoding="utf-8-sig") as f:
        db = json.load(f)
    counts = defaultdict(int)
    for block in db.get("blocks", []):
        key = (block.get("grammar", ""), block.get("topic", ""), block.get("level", ""))
        counts[key] += 1
    return dict(counts)


def read_freq_done(state):
    """Return set of (level, grammar, topic) tuples already generated in freq mode."""
    return {tuple(x) for x in state.get("freq_done", [])}


def write_freq_done(state, freq_done_set):
    state["freq_done"] = [list(x) for x in sorted(freq_done_set)]
    write_state(state)


def compute_priority(grammar, topic, level, freq_data, db_counts, freq_done_set):
    """
    Higher = more urgent to generate.
    Unvisited combos (0 blocks in DB) get a breadth bonus -> breadth-first.
    Returns -1 if combo is satisfied or already queued this session.
    """
    if (level, grammar, topic) in freq_done_set:
        return -1

    freq_pct = freq_data.get(grammar, 0.1)
    target   = get_target_blocks(freq_pct)
    existing = db_counts.get((grammar, topic, level), 0)
    gap      = target - existing

    if gap <= 0:
        return -1

    breadth_bonus = 500 if existing == 0 else 0
    return breadth_bonus + gap * freq_pct


# ============================================================
# Frequency mode: get-next / mark-done / status
# ============================================================

def get_next_freq(config, topics, freq_data, db_counts, freq_done_set):
    best_combo    = None
    best_priority = -1

    for topic in topics:
        for level in LEVEL_ORDER:
            for grammar in config["levels"][level]["grammar_items"]:
                p = compute_priority(grammar, topic, level, freq_data, db_counts, freq_done_set)
                if p > best_priority:
                    best_priority = p
                    best_combo    = (level, grammar, topic)

    if best_combo is None:
        return {"status": "all_done_freq"}

    level, grammar, topic = best_combo
    patterns      = get_patterns_for_grammar(config, level, grammar)
    pattern_count = len(patterns)
    total         = pattern_count * 10
    freq_pct      = freq_data.get(grammar, 0.1)
    target        = get_target_blocks(freq_pct)
    existing      = db_counts.get((grammar, topic, level), 0)

    return {
        "mode":            "freq",
        "level":           level,
        "grammar":         grammar,
        "topic":           topic,
        "patterns":        patterns,
        "pattern_count":   pattern_count,
        "blocks":          10,
        "total_sentences": total,
        "patterns_list":   build_patterns_list(patterns),
        "grammar_hint":    config.get("grammar_hints", {}).get(grammar, ""),
        "grammar_rules":   config.get("grammar_rules", {}).get(grammar, ""),
        "level_guard":     get_level_guard(config, level),
        "level_desc":      config["levels"][level]["level_desc"],
        "tsv_path":        build_tsv_path(level, grammar, topic),
        "freq_pct":        freq_pct,
        "target_blocks":   target,
        "existing_blocks": existing,
        "gap":             max(0, target - existing),
    }


def mark_done_freq(state, level, grammar, topic):
    freq_done = read_freq_done(state)
    freq_done.add((level, grammar, topic))
    write_freq_done(state, freq_done)
    print("[freq] Marked done: {} {} x {} ({} total in session)".format(
        level, grammar, topic, len(freq_done)))


def print_status_freq(config, topics, freq_data, db_counts, freq_done_set):
    total     = 0
    satisfied = 0
    in_queue  = 0
    pending   = 0

    for topic in topics:
        for level in LEVEL_ORDER:
            for grammar in config["levels"][level]["grammar_items"]:
                total += 1
                freq_pct = freq_data.get(grammar, 0.1)
                target   = get_target_blocks(freq_pct)
                existing = db_counts.get((grammar, topic, level), 0)
                if existing >= target:
                    satisfied += 1
                elif (level, grammar, topic) in freq_done_set:
                    in_queue += 1
                else:
                    pending += 1

    print("[freq-mode] Combinations total:          {}".format(total))
    print("            At or above target:           {}".format(satisfied))
    print("            Generated, awaiting import:   {}".format(in_queue))
    print("            Still pending:                {}".format(pending))

    task = get_next_freq(config, topics, freq_data, db_counts, freq_done_set)
    if task.get("status") == "all_done_freq":
        print("            Status: ALL DONE")
    else:
        print("            Next: {} -- {} x {}".format(task["level"], task["grammar"], task["topic"]))
        print("                  freq {:.2f}%  |  target {}  existing {}  gap {}".format(
            task["freq_pct"], task["target_blocks"], task["existing_blocks"], task["gap"]))


# ============================================================
# Sequential mode: get-next / mark-done / status
# ============================================================

def get_next(config, topics, state):
    combos = build_all_combos(config, topics)
    idx = state.get("index", 0)

    if idx >= len(combos):
        return {"status": "all_done"}

    level, grammar, topic = combos[idx]
    patterns      = get_patterns_for_grammar(config, level, grammar)
    pattern_count = len(patterns)
    total         = pattern_count * 10

    return {
        "level":           level,
        "grammar":         grammar,
        "topic":           topic,
        "patterns":        patterns,
        "pattern_count":   pattern_count,
        "blocks":          10,
        "total_sentences": total,
        "patterns_list":   build_patterns_list(patterns),
        "grammar_hint":    config.get("grammar_hints", {}).get(grammar, ""),
        "grammar_rules":   config.get("grammar_rules", {}).get(grammar, ""),
        "level_guard":     get_level_guard(config, level),
        "level_desc":      config["levels"][level]["level_desc"],
        "tsv_path":        build_tsv_path(level, grammar, topic),
    }


def mark_done(state, level, grammar, topic, config, topics):
    combos = build_all_combos(config, topics)
    idx = state.get("index", 0)

    if idx < len(combos):
        cur_level, cur_grammar, cur_topic = combos[idx]
        if cur_level == level and cur_grammar == grammar and cur_topic == topic:
            state["index"] = idx + 1
            write_state(state)
            print("Marked done: {} {} x {} (index -> {})".format(level, grammar, topic, idx + 1))
            return

    for i, (l, g, t) in enumerate(combos):
        if l == level and g == grammar and t == topic:
            if i >= idx:
                state["index"] = i + 1
                write_state(state)
                print("Marked done: {} {} x {} (index -> {})".format(level, grammar, topic, i + 1))
                return

    print("Combination not found or already past: {} {} x {}".format(level, grammar, topic))


def print_status(config, topics, state):
    combos = build_all_combos(config, topics)
    idx    = state.get("index", 0)
    total  = len(combos)
    print("Topics: {}".format(len(topics)))
    print("Total combinations: {}".format(total))
    print("Completed (index): {}".format(idx))
    print("Remaining: {}".format(max(0, total - idx)))
    print("Last updated: {}".format(state.get("last_updated", "?")))
    if idx < total:
        level, grammar, topic = combos[idx]
        print("Next: {} -- {} x {}".format(level, grammar, topic))


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AJ Dril next task helper")
    parser.add_argument("--freq-mode", action="store_true",
                        help="Frequency-weighted mode (reads DB + CSV, ignores sequential index)")
    parser.add_argument("--get-next",  action="store_true", help="Output next task as JSON")
    parser.add_argument("--mark-done", action="store_true", help="Mark combination as done")
    parser.add_argument("--status",    action="store_true", help="Show progress summary")
    parser.add_argument("--level",   type=str, help="Level (A0/A1/A2/B1)")
    parser.add_argument("--grammar", type=str, help="Grammar name")
    parser.add_argument("--topic",   type=str, help="Topic name")
    args = parser.parse_args()

    config = read_config()
    topics = read_topics()
    state  = read_state()

    if args.freq_mode:
        if not FREQ_FILE.exists():
            print("Error: {} not found.".format(FREQ_FILE), file=sys.stderr)
            sys.exit(1)
        if not DB_FILE.exists():
            print("Error: {} not found.".format(DB_FILE), file=sys.stderr)
            sys.exit(1)

        freq_data = read_frequency_csv()
        db_counts = read_database_counts()
        freq_done = read_freq_done(state)

        if args.get_next:
            result = get_next_freq(config, topics, freq_data, db_counts, freq_done)
            print(json.dumps(result, ensure_ascii=False))
        elif args.mark_done:
            if not (args.level and args.grammar and args.topic):
                print("Error: --mark-done requires --level, --grammar, --topic", file=sys.stderr)
                sys.exit(1)
            mark_done_freq(state, args.level, args.grammar, args.topic)
        elif args.status:
            print_status_freq(config, topics, freq_data, db_counts, freq_done)
        else:
            parser.print_help()

    else:
        if args.get_next:
            result = get_next(config, topics, state)
            print(json.dumps(result, ensure_ascii=False))
        elif args.mark_done:
            if not (args.level and args.grammar and args.topic):
                print("Error: --mark-done requires --level, --grammar, --topic", file=sys.stderr)
                sys.exit(1)
            mark_done(state, args.level, args.grammar, args.topic, config, topics)
        elif args.status:
            print_status(config, topics, state)
        else:
            parser.print_help()
