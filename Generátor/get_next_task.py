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
from collections import Counter

# Paths — script is in Generátor/, project root is one level up
BASE = Path(__file__).resolve().parent.parent
TEMATA_FILE   = BASE / "Generátor" / "temata.txt"
CONFIG_FILE   = BASE / "aj_dril_generator_config.json"
PROGRESS_FILE = BASE / "aj_dril_topics_progress.json"
PROMPTY_DIR   = BASE / "Prompty"
DB_FILE       = BASE / "aj_dril_databaze.json"

LEVEL_ORDER = ["A0", "A1", "A2", "B1"]

# Cílové frekvence gramatik (corpus research — Krámský 1969, BNC/COCA)
GRAMMAR_TARGETS = {
    'Přítomný čas prostý': 14.0, 'Členy (a/an/the)': 10.0, 'Minulý čas prostý': 7.5,
    'Sloveso být (to be)': 6.5, 'Zájmena': 5.5, 'Předložky místa a času': 5.0,
    'Přítomný čas průběhový': 4.0, 'Způsobová — can/could': 3.5, 'Budoucí čas (will)': 3.0,
    'Předpřítomný čas': 2.5, 'Some / any / much / many': 2.0, 'Způsobová — must/have to': 1.8,
    'Způsobová — should/ought to': 1.5, 'Budoucí čas (going to)': 1.5, 'Frázová slovesa': 1.5,
    'Příslovce frekvence': 1.3, 'Způsobová — might/may': 1.2, 'Infinitiv': 1.2,
    'Číslovky': 1.0, 'Množné číslo': 1.0, 'Gerundium': 0.9, 'Vedlejší věty': 0.9,
    'Podmínka 1. typ': 0.8, 'Nepravidelná slovesa': 0.8, 'Minulý čas průběhový': 0.7,
    'Sponová slovesa': 0.7, 'Stupňování přídavných jmen': 0.7, 'Trpný rod': 0.6,
    'There is / There are': 0.6, 'Rozkazy a návrhy': 0.6, 'Souhlasné reakce': 0.5,
    'Kvantifikátory (all/both/each)': 0.5, 'Podmínka 2. typ': 0.5, 'Přímá a nepřímá řeč': 0.5,
    'Předpřítomný průběhový': 0.5, 'Tvoření slov': 0.5, 'Slovesa se dvěma předměty': 0.4,
    'Předminulý čas': 0.4, 'Used to': 0.4, 'Podmínka 3. typ': 0.3,
    'Způsobová minulá (could have...)': 0.3, 'Budoucí průběhový': 0.2, 'Wish': 0.2,
    'Would rather': 0.2, 'Dovětky (question tags)': 0.2, 'Have something done': 0.15,
    "It's time": 0.15,
}
_t = sum(GRAMMAR_TARGETS.values())
GRAMMAR_TARGETS = {k: v / _t for k, v in GRAMMAR_TARGETS.items()}


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
        f"\nLEVEL RESTRICTION (strictly follow):\n"
        f"Sentences must match level {level} — do not use any grammar constructions above this level.\n"
        f"Forbidden constructions for this level: {', '.join(forbidden)}.\n"
    )


def compute_deficits():
    """Spočítá deficit každé gramatiky: cílový podíl - skutečný podíl.
    Bere v úvahu JSON databázi i TSV soubory ve složce Prompty (ještě neimportované)."""
    counts = Counter()

    if DB_FILE.exists():
        with open(DB_FILE, "r", encoding="utf-8-sig") as f:
            try:
                data = json.load(f)
                for block in data.get("blocks", []):
                    counts[block["grammar"]] += len(block.get("sentences", []))
            except Exception:
                pass

    for tsv in PROMPTY_DIR.glob("*.tsv"):
        try:
            with open(tsv, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2 and parts[0]:
                        counts[parts[0]] += 1
        except Exception:
            pass

    total = sum(counts.values()) or 1
    deficits = {}
    for grammar, target in GRAMMAR_TARGETS.items():
        actual = counts.get(grammar, 0) / total
        deficits[grammar] = target - actual

    return deficits


def get_all_combos(config, topics):
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

    all_combos = get_all_combos(config, topics)
    deficits = compute_deficits()

    # Varianta A: dokončí jedno téma kompletně před přechodem na další.
    # V rámci tématu seřadí gramatiky podle deficitu (největší chybí = první).

    topic_done = {t: 0 for t in topics}
    topic_total = {t: 0 for t in topics}
    for (level, grammar, topic) in all_combos:
        topic_total[topic] += 1
        if (level, grammar, topic) in completed_set:
            topic_done[topic] += 1

    # Vyber první nedokončené téma podle pořadí v temata.txt
    active_topic = None
    for topic in topics:
        if topic_done[topic] < topic_total[topic]:
            active_topic = topic
            break

    if active_topic is None:
        return {"status": "all_done"}

    # Pending kombinace pro aktivní téma, seřazené podle deficitu
    pending = [
        (level, grammar, topic)
        for (level, grammar, topic) in all_combos
        if topic == active_topic and (level, grammar, topic) not in completed_set
    ]
    pending.sort(key=lambda c: -deficits.get(c[1], 0))

    for (level, grammar, topic) in pending:
        patterns = get_patterns_for_grammar(config, level, grammar)
        pattern_count = len(patterns)
        total = pattern_count * 10

        pat_labels = {
            "affirmative": "Oznamovací věta — střídej osoby: I / you / he/she/it / they (person: first / second / third_singular / plural)",
            "negative":    "Záporná věta — střídej osoby: I / you / he/she/it / they (person: first / second / third_singular / plural)",
            "question":    'Otázka (ano/ne) — person: ""',
            "wh_question": 'WH otázka (co/kde/kdy...) — person: ""',
            "imperative":  'Rozkazovací věta — person: ""',
            "comparison":  'Srovnání — person: ""',
            "tag_question":'Dovětek (question tag) — person: ""',
            "time_clause": 'Časová věta — person: ""',
            "passive":     'Trpný rod — person: ""',
            "indirect":    'Nepřímá řeč — person: ""',
            "conditional": 'Podmínková věta — person: ""',
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
