#!/usr/bin/env python3
"""Valida bank/*.jsonl e mostra cobertura vs. blueprint.

  python validate_bank.py [--target 300]      # target = tamanho desejado do banco p/ calcular metas por skill
  python validate_bank.py --file bank/staging.jsonl
"""
import argparse
import json
import re
import sys
from collections import Counter

from common import BANK_DIR, ROOT, load_bank, load_blueprint, skills_index

LETTER_REF = re.compile(r"(\b(op[cç][aã]o|alternativa|option|choice|letra)\s+\(?[A-F]\)?\b|\([A-F]\)|\b[A-F]\)\s)", re.I)
REQUIRED = ["id", "domain", "skill", "type", "select", "stem", "options", "correct", "rationale", "why_wrong", "difficulty", "source", "status"]


def check(q, sk):
    errs, warns = [], []
    for k in REQUIRED:
        if k not in q:
            errs.append(f"campo ausente: {k}")
    if errs:
        return errs, warns
    if q["skill"] not in sk:
        errs.append(f"skill desconhecida: {q['skill']}")
    elif sk[q["skill"]]["domain"] != q["domain"]:
        errs.append("domain não bate com a skill")
    ids = [o["id"] for o in q["options"]]
    if len(ids) != len(set(ids)) or not (4 <= len(ids) <= 6):
        errs.append("opções: precisa de 4–6 ids únicos")
    if not set(q["correct"]) <= set(ids):
        errs.append("correct contém id inexistente")
    if q["type"] == "single" and (len(q["correct"]) != 1 or q["select"] != 1):
        errs.append("single exige 1 correta e select=1")
    if q["type"] == "multi" and (len(q["correct"]) != q["select"] or q["select"] < 2):
        errs.append("multi exige select>=2 e select == nº de corretas (a prova informa quantas escolher)")
    wrong = set(ids) - set(q["correct"])
    if set(q["why_wrong"]) != wrong:
        errs.append(f"why_wrong deve cobrir exatamente as erradas: {sorted(wrong)}")
    for field in ("stem", "rationale", *q["why_wrong"].values(), *[o["text"] for o in q["options"]]):
        if LETTER_REF.search(field):
            warns.append("texto referencia letra de opção (quebra com embaralhamento)")
            break
    lens = [len(o["text"]) for o in q["options"] if o["id"] in q["correct"]]
    others = [len(o["text"]) for o in q["options"] if o["id"] not in q["correct"]]
    if lens and others and min(lens) > 1.6 * (sum(others) / len(others)):
        warns.append("correta(s) muito mais longa(s) que distratores (vício de teste)")
    if q["status"] == "reviewed" and q["source"].get("kind") in ("official_docs", "official_blog") and not q["source"].get("url"):
        warns.append("reviewed sem URL de fonte")
    return errs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=300)
    ap.add_argument("--file")
    a = ap.parse_args()
    bp = load_blueprint()
    sk = skills_index(bp)

    if a.file:
        qs = [json.loads(l) for l in open(a.file, encoding="utf-8") if l.strip()]
    else:
        qs = load_bank()
    bad = 0
    for q in qs:
        e, w = check(q, sk)
        for m in e:
            print(f"ERRO  {q.get('id')}: {m}")
        for m in w:
            print(f"aviso {q.get('id')}: {m}")
        bad += bool(e)

    cnt = Counter(q["skill"] for q in qs if "skill" in q)
    rev = Counter(q["skill"] for q in qs if q.get("status") == "reviewed")
    print(f"\n{len(qs)} questões ({sum(rev.values())} reviewed) | {bad} com erro\n")
    print(f"{'skill':<20}{'peso%':>6}{'meta':>6}{'tem':>5}{'rev':>5}{'falta':>7}")
    tot_w = sum(s["weight"] for s in sk.values())
    for sid, s in sk.items():
        meta = round(a.target * s["weight"] / tot_w)
        print(f"{sid:<20}{s['weight']:>6}{meta:>6}{cnt[sid]:>5}{rev[sid]:>5}{max(0, meta - cnt[sid]):>7}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
