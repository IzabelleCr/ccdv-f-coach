#!/usr/bin/env python3
"""Coleta corpus de estudo para o CCDV-F.

Comandos:
  python scraper.py docs   [--only ID] [--max-pages N] [--refresh]   # documentação oficial -> corpus/*.md
  python scraper.py reddit                                           # sinais de tópicos (NÃO questões)
  python scraper.py index                                            # corpus/*.md -> corpus/chunks.jsonl (tag por skill)
  python scraper.py search --skill D2.api [--k 8]                    # trechos relevantes p/ gerar questões
  python scraper.py status                                           # o que já foi coletado / cobertura por skill
  python scraper.py all

Boas maneiras: respeita robots.txt, rate limit, cache por hash. Falhas de rede são reportadas, nunca silenciadas.
"""
import argparse
import collections
import hashlib
import json
import re
import sys
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from common import ROOT, load_blueprint, skills_index

CORPUS = ROOT / "corpus"
SOURCES = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
UA = SOURCES.get("user_agent", "ccdv-f-coach/1.0")
DELAY = float(SOURCES.get("delay_seconds", 1.5))

_robots = {}
_last_hit = 0.0
_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xml,application/json;q=0.9,*/*;q=0.5"})
FAILS = []


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    rp = _robots.get(host)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(host + "/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[host] = rp
    return rp.can_fetch(UA, url)


def get(url, tries=3):
    global _last_hit
    if not allowed(url):
        FAILS.append((url, "bloqueado por robots.txt"))
        return None
    for i in range(tries):
        wait = DELAY - (time.time() - _last_hit)
        if wait > 0:
            time.sleep(wait)
        _last_hit = time.time()
        try:
            r = _session.get(url, timeout=25)
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                time.sleep(5 * (i + 1))
                err = f"HTTP {r.status_code}"
                continue
            FAILS.append((url, f"HTTP {r.status_code}"))
            return None
        time.sleep(2 * (i + 1))
    FAILS.append((url, err))
    return None


# ---------------------------------------------------------------- docs
def norm(url):
    return urldefrag(url)[0].rstrip("/")


def from_sitemap(sm_url, prefixes):
    r = get(sm_url)
    if not r:
        return []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []
    urls = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
    out = []
    for u in urls:
        if u.endswith(".xml") and "sitemap" in u:  # sitemap index
            out += from_sitemap(u, prefixes)
        elif any(u.startswith(p) for p in prefixes):
            out.append(u)
    return out


def discover(src, limit):
    prefixes = src["include_prefixes"]
    found, queue, seen = [], [], set()
    if src.get("sitemap"):
        for u in from_sitemap(src["sitemap"], prefixes):
            if norm(u) not in seen:
                seen.add(norm(u)); found.append(u)
    for s in src["seeds"]:
        if norm(s) not in seen:
            seen.add(norm(s)); found.insert(0, s) if s not in found else None
    if len(found) < limit:  # fallback: BFS 1 nível a partir dos seeds
        for s in src["seeds"]:
            r = get(s)
            if not r:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                u = norm(urljoin(r.url, a["href"]))
                if any(u.startswith(p.rstrip("/")) for p in prefixes) and u not in seen:
                    seen.add(u); found.append(u)
    return found[:limit]


def extract(html, url):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    title = (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else (soup.title.string if soup.title else url)).strip()
    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "table"]):
        if any(p.name in ("li", "pre", "table") for p in el.parents):
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            lines.append("\n" + "#" * int(el.name[1]) + " " + el.get_text(" ", strip=True))
        elif el.name == "pre":
            lines.append("\n```\n" + el.get_text("\n").strip("\n") + "\n```")
        elif el.name == "li":
            lines.append("- " + re.sub(r"\s+", " ", el.get_text(" ", strip=True)))
        elif el.name == "table":
            for tr in el.find_all("tr"):
                lines.append("| " + " | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])) + " |")
        else:
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if txt:
                lines.append(txt)
    return title, "\n".join(lines).strip()


def slugify(url):
    p = urlparse(url)
    s = re.sub(r"[^a-z0-9]+", "-", (p.netloc + p.path).lower()).strip("-")
    return s[:110] + "-" + hashlib.sha1(url.encode()).hexdigest()[:6]


def cmd_docs(args):
    CORPUS.mkdir(exist_ok=True)
    total = 0
    for src in SOURCES["docs"]:
        if args.only and src["id"] != args.only:
            continue
        limit = args.max_pages or src.get("max_pages", 50)
        urls = discover(src, limit)
        print(f"[{src['id']}] {len(urls)} URLs candidatas")
        for u in urls:
            path = CORPUS / f"{slugify(u)}.md"
            if path.exists() and not args.refresh:
                continue
            r = get(u)
            if not r:
                continue
            title, body = extract(r.text, r.url)
            if len(body) < 400:
                continue
            fm = (f"---\nurl: {r.url}\ntitle: {json.dumps(title, ensure_ascii=False)}\nsource: {src['id']}\n"
                  f"kind: {src['kind']}\nfetched: {time.strftime('%Y-%m-%d')}\n"
                  f"sha256: {hashlib.sha256(body.encode()).hexdigest()[:16]}\n---\n\n")
            path.write_text(fm + body, encoding="utf-8")
            total += 1
            print(f"  + {title[:70]}")
    print(f"docs: {total} páginas novas")


# ---------------------------------------------------------------- reddit (sinais)
def cmd_reddit(_args):
    cfg = SOURCES["reddit"]
    if not cfg.get("enabled"):
        print("reddit desabilitado em sources.json"); return
    CORPUS.mkdir(exist_ok=True)
    leak = re.compile("|".join(cfg["leak_flag_patterns"]), re.I)
    out, seen = [], set()
    for sub in cfg["subreddits"]:
        for q in cfg["queries"]:
            url = (f"https://www.reddit.com/r/{sub}/search.json?q={requests.utils.quote(q)}"
                   f"&restrict_sr=1&sort=top&t=year&limit={cfg['limit_per_query']}")
            r = get(url)
            if not r:
                continue
            try:
                posts = r.json()["data"]["children"]
            except (ValueError, KeyError):
                continue
            for p in posts:
                d = p["data"]
                if d["id"] in seen:
                    continue
                seen.add(d["id"])
                text = f"{d.get('title','')}\n{d.get('selftext','')}"
                out.append({
                    "id": d["id"], "subreddit": sub, "title": d.get("title"), "score": d.get("score"),
                    "num_comments": d.get("num_comments"), "url": "https://www.reddit.com" + d.get("permalink", ""),
                    "excerpt": (d.get("selftext") or "")[:1200],
                    "possible_exam_leak": bool(leak.search(text)),
                })
    with open(CORPUS / "reddit_signals.jsonl", "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    flagged = sum(o["possible_exam_leak"] for o in out)
    print(f"reddit: {len(out)} posts salvos ({flagged} marcados como possível vazamento -> IGNORAR no conteúdo)")


# ---------------------------------------------------------------- index / search
def split_chunks(body, max_chars=1800):
    parts, cur, head = [], [], ""
    for line in body.splitlines():
        if re.match(r"^#{1,4} ", line):
            if cur:
                parts.append((head, "\n".join(cur).strip())); cur = []
            head = line.lstrip("# ").strip()
        cur.append(line)
        if sum(len(x) for x in cur) > max_chars:
            parts.append((head, "\n".join(cur).strip())); cur = []
    if cur:
        parts.append((head, "\n".join(cur).strip()))
    return [(h, t) for h, t in parts if len(t) > 200]


def score_skills(text, sk_idx):
    low = text.lower()
    scores = {}
    for sid, s in sk_idx.items():
        sc = sum(low.count(k.lower()) for k in s["keywords"])
        if sc:
            scores[sid] = sc
    return scores


def cmd_index(_args):
    sk = skills_index(load_blueprint())
    n = 0
    with open(CORPUS / "chunks.jsonl", "w", encoding="utf-8") as out:
        for f in sorted(CORPUS.glob("*.md")):
            raw = f.read_text(encoding="utf-8")
            m = re.match(r"---\n(.*?)\n---\n", raw, re.S)
            meta = dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l) if m else {}
            body = raw[m.end():] if m else raw
            for head, text in split_chunks(body):
                sc = score_skills(head + "\n" + text, sk)
                if not sc:
                    continue
                top = sorted(sc, key=sc.get, reverse=True)[:3]
                out.write(json.dumps({"file": f.name, "url": meta.get("url"), "title": meta.get("title"),
                                      "heading": head, "skills": top, "score": sc[top[0]], "text": text},
                                     ensure_ascii=False) + "\n")
                n += 1
    print(f"index: {n} chunks em corpus/chunks.jsonl")


def cmd_search(args):
    path = CORPUS / "chunks.jsonl"
    if not path.exists():
        sys.exit("rode `python scraper.py index` antes")
    hits = []
    for line in path.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        if args.skill in c["skills"]:
            hits.append(c)
    hits.sort(key=lambda c: c["score"], reverse=True)
    for c in hits[: args.k]:
        print(json.dumps(c, ensure_ascii=False))
    if not hits:
        print(f"// nenhum chunk para {args.skill}; rode docs/index ou amplie as fontes", file=sys.stderr)


def cmd_status(_args):
    sk = skills_index(load_blueprint())
    pages = list(CORPUS.glob("*.md"))
    print(f"páginas no corpus: {len(pages)}")
    cov = collections.Counter()
    p = CORPUS / "chunks.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            for s in json.loads(line)["skills"]:
                cov[s] += 1
    print(f"{'skill':<20}{'peso%':>6}{'chunks':>8}")
    for sid, s in sk.items():
        flag = "  <- SEM COBERTURA" if cov[sid] == 0 else ""
        print(f"{sid:<20}{s['weight']:>6}{cov[sid]:>8}{flag}")
    if (CORPUS / "reddit_signals.jsonl").exists():
        print("reddit_signals.jsonl presente")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("docs"); d.add_argument("--only"); d.add_argument("--max-pages", type=int); d.add_argument("--refresh", action="store_true")
    sub.add_parser("reddit"); sub.add_parser("index"); sub.add_parser("status"); sub.add_parser("all")
    s = sub.add_parser("search"); s.add_argument("--skill", required=True); s.add_argument("--k", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "all":
        a.only = a.max_pages = None; a.refresh = False
        cmd_docs(a); cmd_reddit(a); cmd_index(a); cmd_status(a)
    else:
        {"docs": cmd_docs, "reddit": cmd_reddit, "index": cmd_index, "search": cmd_search, "status": cmd_status}[a.cmd](a)
    if FAILS:
        print(f"\n{len(FAILS)} falhas de coleta (primeiras 15):", file=sys.stderr)
        for u, why in FAILS[:15]:
            print(f"  - {why}: {u}", file=sys.stderr)


if __name__ == "__main__":
    main()
