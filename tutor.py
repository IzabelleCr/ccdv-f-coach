#!/usr/bin/env python3
"""Modo professor: seleção adaptativa de questões e registro de progresso.

  python tutor.py next [--n 5] [--domain D2] [--skill D2.api] [--weak]   # imprime JSON (COM gabarito; o agente não revela antes)
  python tutor.py record Q-D2.api-001 1        # 1 = acertou, 0 = errou
  python tutor.py stats                        # acurácia por domínio/skill + skills mais fracas
"""
import argparse
import datetime as dt
import json
import random
from collections import defaultdict

from common import load_bank, load_blueprint, load_progress, record_answer, save_progress, skills_index


def priority(q, prog, sk, weak):
    a = prog["answers"].get(q["id"])
    w = sk[q["skill"]]["weight"]
    if a is None:
        base = 3.0  # nunca vista
    else:
        acc = a["correct"] / a["seen"]
        days = (dt.datetime.now() - dt.datetime.fromisoformat(a["last"])).days
        base = (1 - acc) * 2.5 + min(days, 14) / 14 + (1.0 if a["last_correct"] is False else 0)
    if q.get("status") == "reviewed":
        base += 0.3
    return base * (1 + (w / 10 if not weak else w / 5)) + random.random() * 0.3


def cmd_next(a):
    sk = skills_index(load_blueprint())
    prog = load_progress()
    pool = [q for q in load_bank()
            if (not a.domain or q["domain"] == a.domain) and (not a.skill or q["skill"] == a.skill)]
    if not pool:
        raise SystemExit("nenhuma questão para esse filtro; use /gerar")
    pool.sort(key=lambda q: priority(q, prog, sk, a.weak), reverse=True)
    for q in pool[: a.n]:
        print(json.dumps(q, ensure_ascii=False))


def cmd_record(a):
    p = load_progress()
    record_answer(p, a.id, a.correct == "1")
    save_progress(p)
    print("ok")


def cmd_stats(_a):
    bp = load_blueprint()
    sk = skills_index(bp)
    bank = {q["id"]: q for q in load_bank(include_retired=True)}
    p = load_progress()
    agg = defaultdict(lambda: [0, 0])
    for qid, a in p["answers"].items():
        if qid in bank:
            s = bank[qid]["skill"]
            agg[s][0] += a["seen"]; agg[s][1] += a["correct"]
    print(f"{'skill':<20}{'peso%':>6}{'resp':>6}{'acc':>7}")
    rows = []
    for sid, s in sk.items():
        n, c = agg[sid]
        acc = c / n if n else None
        rows.append((sid, s["weight"], n, acc))
        print(f"{sid:<20}{s['weight']:>6}{n:>6}{(f'{acc:.0%}' if acc is not None else '-'):>7}")
    weak = sorted([r for r in rows if r[3] is not None and r[2] >= 2], key=lambda r: (r[3], -r[1]))[:5]
    if weak:
        print("\nmais fracas (>=2 respostas): " + ", ".join(f"{r[0]} ({r[3]:.0%})" for r in weak))
    if p["exams"]:
        print("simulados: " + " -> ".join(f"{e['pct']}%" for e in p["exams"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next"); n.add_argument("--n", type=int, default=1); n.add_argument("--domain"); n.add_argument("--skill"); n.add_argument("--weak", action="store_true")
    r = sub.add_parser("record"); r.add_argument("id"); r.add_argument("correct", choices=["0", "1"])
    sub.add_parser("stats")
    a = ap.parse_args()
    {"next": cmd_next, "record": cmd_record, "stats": cmd_stats}[a.cmd](a)


if __name__ == "__main__":
    main()
