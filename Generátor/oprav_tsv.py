#!/usr/bin/env python3
"""
oprav_tsv.py — Opraví TSV soubory ve složce Prompty.

Problém: AI někdy vynechá prázdný tabulátor pro sloupec 'person'
u patternů kde je person prázdné (question, wh_question, imperative atd.).
Výsledkem je 8 sloupců místo 9.

Řešení: Projde všechny TSV soubory a doplní chybějící tabulátor
na pozici 5 (sloupec person) u každého řádku s pouze 8 sloupci.

Použití:
  python3 oprav_tsv.py
"""

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROMPTY_DIR = BASE / "Prompty"

def oprav_soubor(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    fixed = 0
    for line in lines:
        stripped = line.rstrip('\n\r')
        if not stripped:
            fixed_lines.append(line)
            continue
        cols = stripped.split('\t')
        if len(cols) == 8:
            # Chybí sloupec person (index 5) — vložíme prázdný
            cols.insert(5, '')
            fixed += 1
        elif len(cols) != 9:
            print(f'  POZOR: neočekávaný počet sloupců ({len(cols)}): {stripped[:60]}')
        fixed_lines.append('\t'.join(cols) + '\n')

    if fixed > 0:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)

    return fixed


def main():
    tsv_files = [f for f in PROMPTY_DIR.iterdir() if f.suffix == '.tsv']

    if not tsv_files:
        print("Žádné TSV soubory ve složce Prompty.")
        return

    print(f"Kontroluji {len(tsv_files)} TSV souborů...\n")
    total_fixed = 0
    total_ok = 0

    for path in sorted(tsv_files):
        fixed = oprav_soubor(path)
        if fixed > 0:
            print(f"  ✓ {path.name}: opraveno {fixed} řádků")
            total_fixed += fixed
        else:
            total_ok += 1

    print()
    if total_fixed > 0:
        print(f"Opraveno celkem: {total_fixed} řádků v {len(tsv_files) - total_ok} souborech.")
    else:
        print("Vše v pořádku — žádné opravy nebyly potřeba.")


if __name__ == "__main__":
    main()
