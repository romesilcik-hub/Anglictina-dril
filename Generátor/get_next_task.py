#!/usr/bin/env python3
"""
get_next_task.py — Determines the next grammar×topic combination for AJ Dril sentence generation.

Usage:
  python3 get_next_task.py --get-next
  python3 get_next_task.py --mark-done --level B1 --grammar "Trpný rod" --topic "Hotel a recepce"
  python3 get_next_task.py --status

The script reads temata.txt for topics, aj_dril_generator_config.json for grammar/pattern rules,
and aj_dril_topics_progress.json for completed combinations.
"""

import json
import sys
import argparse
import re
import unicodedata
from pathlib import Path
from datetime import date

# Paths — script is in Generátor/, project root is one level up
BASE = Path(__file__).resolve().parent.parent
TEMATA_FILE   = BASE / "Generátor" / "temata.txt"
CONFIG_FILE   = BASE / "aj_dril_generator_config.json"
PROGRESS_FILE = BASE / "aj_dril_topics_progress.json"
PROMPTY_DIR   = BASE / "Prompty"

LEVEL_ORDER = ["A0", "A1", "A2", "B1"]


def read_topics():
    """Read topics from temata.txt (skip comments and blank lines)."""
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


def read_progress():
    if not PROGRESS_FILE.exists():
        return {"last_updated": str(date.today()), "completed": []}
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_progress(progress):
    progress["last_updated"] = str(date.today())
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def to_safe_filename(s):
    """Remove diacritics and special chars, replace spaces with underscores."""
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
    """Return the list of patterns for a given grammar, applying exclusions."""
    level_patterns = config["levels"][level]["patterns"]
    exclude = config.get("grammar_pattern_exclude", {}).get(grammar, [])
    return [p for p in level_patterns if p not in exclude]


def get_level_guard(config, level):
    """Return forbidden grammar constructions for a given level (all levels above current)."""
    cur_idx = LEVEL_ORDER.index(level)
    forbidden = []
    for lvl in LEVEL_ORDER[cur_idx + 1:]:
        forbidden.extend(config["levels"][lvl]["grammar_items"])
    if not forbidden:
        return ""
    return (
        f"\nLEVEL RESTRICTION (strictly follow):\n"
        f"Sentences must match level {level} — do not use any grammar constructions above this level.\n"
        f"Forbidden constructions for this level: {', '.join(forbidden)}.\n"
    )


def get_all_combos(config, topics):
    """Return all (level, grammar, topic) combinations in order (topic-first).
    All grammars A0→B1 are generated for one topic before moving to the next topic."""
    combos = []
    for topic in topics:
        for level in LEVEL_ORDER:
            for grammar in config["levels"][level]["grammar_items"]:
                combos.append((level, grammar, topic))
    return combos


def get_next(config, topics, progress):
    completed_set = {
        (c["level"], c["grammar"], c["topic"])
        for c in progress["completed"]
    }
    for (level, grammar, topic) in get_all_combos(config, topics):
        if (level, grammar, topic) not in completed_set:
            patterns = get_patterns_for_grammar(config, level, grammar)
            pattern_count = len(patterns)
            total = pattern_count * 10

            # Pattern labels for the prompt
            pat_labels = {
                "affirmative": "Affirmative sentence",
                "negative": "Negative sentence",
                "question": "Yes/No question",
                "wh_question": "WH question",
                "first_person": "1st person (I/we)",
                "second_person": "2nd person (you)",
                "third_person": "3rd person (he/she/it)",
                "plural": "Plural (they/we)",
                "imperative": "Imperative",
                "comparison": "Comparison",
                "tag_question": "Tag question",
                "time_clause": "Time clause",
                "passive": "Passive voice",
                "indirect": "Reported speech",
                "conditional": "Conditional",
            }
            patterns_list = "\n".join(
                f"   {i+1}. {pat_labels.get(p, p)} (pattern: {p})"
                for i, p in enumerate(patterns)
            )

            grammar_hint = config.get("grammar_hints", {}).get(grammar, "")
            grammar_rules = config.get("grammar_rules", {}).get(grammar, "")
            level_guard = get_level_guard(config, level)
            level_desc = config["levels"][level]["level_desc"]

            return {
                "level": level,
                "grammar": grammar,
                "topic": topic,
                "patterns": patterns,
                "pattern_count": pattern_count,
                "blocks": 10,
                "total_sentences": total,
                "patterns_list": patterns_list,
                "grammar_hint": grammar_hint,
                "grammar_rules": grammar_rules,
                "level_guard": level_guard,
                "level_desc": level_desc,
                "tsv_path": build_tsv_path(level, grammar, topic),
            }
    return {"status": "all_done"}


def mark_done(progress, level, grammar, topic):
    for c in progress["completed"]:
        if c["level"] == level and c["grammar"] == grammar and c["topic"] == topic:
            print(f"Already marked done: {level} {grammar} × {topic}")
            return
    progress["completed"].append({"level": level, "grammar": grammar, "topic": topic})
    write_progress(progress)
    print(f"Marked done: {level} {grammar} × {topic}")


def print_status(config, topics, progress):
    completed_set = {
        (c["level"], c["grammar"], c["topic"])
        for c in progress["completed"]
    }
    total_combos = len(get_all_combos(config, topics))
    done = len(completed_set)
    pending = total_combos - done
    print(f"Topics in temata.txt: {len(topics)}")
    print(f"Grammar items: {sum(len(config['levels'][l]['grammar_items']) for l in LEVEL_ORDER)}")
    print(f"Total combinations: {total_combos}")
    print(f"Completed: {done}")
    print(f"Pending: {pending}")
    if done > 0:
        print(f"Last updated: {progress.get('last_updated', '?')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AJ Dril next task helper")
    parser.add_argument("--get-next",  action="store_true", help="Output next task as JSON")
    parser.add_argument("--mark-done", action="store_true", help="Mark a combination as done")
    parser.add_argument("--status",    action="store_true", help="Show progress summary")
    parser.add_argument("--level",   type=str, help="Level (A0/A1/A2/B1)")
    parser.add_argument("--grammar", type=str, help="Grammar name")
    parser.add_argument("--topic",   type=str, help="Topic name")
    args = parser.parse_args()

    config   = read_config()
    topics   = read_topics()
    progress = read_progress()

    if args.get_next:
        result = get_next(config, topics, progress)
        print(json.dumps(result, ensure_ascii=False))

    elif args.mark_done:
        if not (args.level and args.grammar and args.topic):
            print("Error: --mark-done requires --level, --grammar, --topic", file=sys.stderr)
            sys.exit(1)
        mark_done(progress, args.level, args.grammar, args.topic)

    elif args.status:
        print_status(config, topics, progress)

    else:
        parser.print_help()
