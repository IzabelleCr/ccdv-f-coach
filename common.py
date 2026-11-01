"""Utilitários compartilhados: blueprint, banco de questões, progresso."""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK_DIR = ROOT / "bank"
DATA_DIR = ROOT / "data"
SESSIONS_DIR = ROOT / "sessions"
PROGRESS_PATH = DATA_DIR / "progress.json"


def load_blueprint():
    return json.loads((DATA_DIR / "blueprint.json").read_text(encoding="utf-8"))


def skills_index(bp):
    """skill_id -> {domain, name, weight, topics, keywords}"""
    idx = {}
    for d in bp["domains"]:
        for s in d["skills"]:
            idx[s["id"]] = {**s, "domain": d["id"], "domain_name": d["name"]}
    return idx


def load_bank(include_retired=False):
    """Lê todos os bank/*.jsonl (ignora staging.jsonl). Retorna lista de dicts."""
    out, seen = [], set()
    for f in sorted(BANK_DIR.glob("*.jsonl")):
        if f.name.startswith("staging"):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                q = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"JSON inválido em {f.name}:{n}: {e}")
            if q.get("status") == "retired" and not include_retired:
                continue
            if q["id"] in seen:
                raise SystemExit(f"id duplicado: {q['id']} ({f.name}:{n})")
            seen.add(q["id"])
            out.append(q)
    return out


def now_iso():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {"answers": {}, "exams": []}


def save_progress(p):
    DATA_DIR.mkdir(exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def record_answer(progress, qid, correct):
    a = progress["answers"].setdefault(qid, {"seen": 0, "correct": 0, "last": None, "last_correct": None})
    a["seen"] += 1
    a["correct"] += 1 if correct else 0
    a["last"] = now_iso()
    a["last_correct"] = bool(correct)
