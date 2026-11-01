#!/usr/bin/env python3
"""Simulado CCDV-F: monta prova ponderada pelo blueprint + HTML com timer, e corrige o resultado.

  python simulado.py build [--n 60] [--minutes 120] [--seed S] [--reviewed-only] [--no-shuffle]
  python simulado.py grade sessions/<id>/result.json     # registra no progress.json e lista erros por skill

Formato oficial: 53 itens / 120 min. O padrão aqui é 60 itens / 120 min (mais puxado que a prova real, de propósito).
"""
import argparse
import copy
import json
import random
import sys
import time
from collections import defaultdict

from common import SESSIONS_DIR, ROOT, load_bank, load_blueprint, load_progress, record_answer, save_progress, skills_index, now_iso


def largest_remainder(total, weights):
    s = sum(weights.values())
    raw = {k: total * w / s for k, w in weights.items()}
    base = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - base[k], reverse=True)[: total - sum(base.values())]:
        base[k] += 1
    return base


def pick(bank, sk, n, rng, seen, reviewed_only):
    pools = defaultdict(list)
    for q in bank:
        if reviewed_only and q.get("status") != "reviewed":
            continue
        if q["skill"] in sk:
            pools[q["skill"]].append(q)
    quota = largest_remainder(n, {sid: s["weight"] for sid, s in sk.items()})
    rank = lambda q: (q["id"] in seen, q.get("status") != "reviewed")

    chosen, leftovers, short = [], [], 0
    for sid, k in quota.items():
        pool = pools[sid]
        rng.shuffle(pool)
        pool.sort(key=rank)  # não vistas e reviewed primeiro; ordem estável mantém o sorteio
        chosen += pool[:k]
        leftovers += pool[k:]
        short += max(0, k - len(pool))
    if short:
        rng.shuffle(leftovers)
        leftovers.sort(key=rank)
        chosen += leftovers[:short]
    return chosen, quota, max(0, n - len(chosen))


def shuffle_options(q, rng):
    q = copy.deepcopy(q)
    if q.get("fixed_order"):
        return q
    opts = q["options"][:]
    rng.shuffle(opts)
    letters = "ABCDEF"
    remap = {o["id"]: letters[i] for i, o in enumerate(opts)}
    q["options"] = [{"id": remap[o["id"]], "text": o["text"]} for o in opts]
    q["options"].sort(key=lambda o: o["id"])
    q["correct"] = sorted(remap[c] for c in q["correct"])
    q["why_wrong"] = {remap[k]: v for k, v in q["why_wrong"].items()}
    return q


def cmd_build(a):
    bp = load_blueprint()
    sk = skills_index(bp)
    bank = load_bank()
    if not bank:
        sys.exit("banco vazio: rode /gerar ou adicione questões em bank/")
    seed = a.seed or str(int(time.time()))
    rng = random.Random(seed)
    prog = load_progress()
    seen = set(prog["answers"])
    chosen, quota, missing = pick(bank, sk, a.n, rng, seen, a.reviewed_only)
    if missing:
        print(f"AVISO: banco só tem {len(chosen)} questões elegíveis (pedidas: {a.n}). Gere mais com /gerar.", file=sys.stderr)
    rng.shuffle(chosen)
    exam_qs = [q if a.no_shuffle else shuffle_options(q, rng) for q in chosen]
    sid = time.strftime("%Y%m%d-%H%M%S")
    d = SESSIONS_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    exam = {
        "id": sid, "seed": seed, "minutes": a.minutes, "created": now_iso(),
        "domains": {x["id"]: {"name": x["name"], "weight": x["weight"]} for x in bp["domains"]},
        "pass_scaled": bp["exam"]["passing_scaled_score"],
        "questions": exam_qs,
    }
    (d / "exam.json").write_text(json.dumps(exam, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "exam.html").write_text(HTML.replace("__DATA__", json.dumps(exam, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    by_dom = defaultdict(int)
    for q in exam_qs:
        by_dom[q["domain"]] += 1
    print(f"Simulado {sid}: {len(exam_qs)} questões, {a.minutes} min")
    print("  por domínio: " + ", ".join(f"{k}={by_dom[k]}" for k in sorted(by_dom)))
    print(f"  abrir: {d / 'exam.html'}")
    print(f"  ao terminar, baixe result.json e rode: python simulado.py grade <caminho>/result.json")


def cmd_grade(a):
    res = json.loads(open(a.result, encoding="utf-8").read())
    prog = load_progress()
    wrong_by_skill = defaultdict(list)
    for r in res["per_question"]:
        record_answer(prog, r["id"], r["correct"])
        if not r["correct"]:
            wrong_by_skill[r["skill"]].append(r["id"])
    prog["exams"].append({"id": res["exam_id"], "date": res.get("finished_at"), "pct": res["pct"], "est_scaled": res["est_scaled"]})
    save_progress(prog)
    print(f"Simulado {res['exam_id']}: {res['pct']}% (nota escalada estimada ~{res['est_scaled']}; corte real = 720)")
    for sid, ids in sorted(wrong_by_skill.items(), key=lambda kv: -len(kv[1])):
        print(f"  {sid}: {len(ids)} erro(s) -> {', '.join(ids)}")
    print("progress.json atualizado.")


HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simulado CCDV-F</title>
<style>
:root{--bg:#fbfbfa;--fg:#1b1f27;--mut:#667085;--line:#d9dde3;--acc:#1f3a5f;--acc-fg:#fff;--card:#fff;--sel:#e8eef6}
@media(prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e6e9ee;--mut:#98a2b3;--line:#2c323b;--acc:#8fb0dd;--acc-fg:#0e1620;--card:#1a1e25;--sel:#222c3b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,'Times New Roman',serif}
.wrap{max-width:860px;margin:0 auto;padding:0 16px 80px}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:5}
.bar{max-width:860px;margin:0 auto;padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:space-between;font-family:system-ui,sans-serif;font-size:14px}
#timer{font:600 20px ui-monospace,Menlo,monospace}#timer.low{text-decoration:underline}
button{font:600 14px system-ui,sans-serif;padding:8px 14px;border:1px solid var(--acc);background:transparent;color:var(--acc);border-radius:6px;cursor:pointer}
button.pri{background:var(--acc);color:var(--acc-fg)}button:disabled{opacity:.4;cursor:default}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;margin-top:18px}
.meta{font:13px system-ui,sans-serif;color:var(--mut);margin-bottom:8px}
.stem{white-space:pre-wrap}
.opt{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-top:10px;cursor:pointer}
.opt.on{background:var(--sel);border-color:var(--acc)}.opt b{font-family:system-ui,sans-serif;min-width:1.4em}
.opt.ok{border-color:var(--acc);border-width:2px}.opt.no{border-style:dashed}
.nav{display:grid;grid-template-columns:repeat(auto-fill,minmax(38px,1fr));gap:6px;margin-top:18px}
.nav button{padding:6px 0;font-size:13px}.nav .ans{background:var(--sel)}.nav .cur{background:var(--acc);color:var(--acc-fg)}.nav .flag{outline:2px dashed var(--mut)}
.row{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}
code{font:0.9em ui-monospace,Menlo,monospace;background:var(--sel);padding:1px 5px;border-radius:4px}
pre{background:var(--sel);padding:12px;border-radius:8px;overflow:auto;font:13px ui-monospace,Menlo,monospace}
table{border-collapse:collapse;width:100%;font:14px system-ui,sans-serif}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
.rev{margin-top:14px;font-size:15px}.rev h4{margin:10px 0 4px;font:600 13px system-ui,sans-serif;color:var(--mut)}
small{color:var(--mut)}
</style></head><body>
<header><div class="bar"><span>Simulado CCDV-F <small id="prog"></small></span><span id="timer">--:--:--</span><span><button id="flagbtn" style="display:none">Marcar</button> <button class="pri" id="finish" style="display:none">Finalizar</button></span></div></header>
<div class="wrap" id="app"></div>
<script>
const E=__DATA__;
const KEY='ccdv-'+E.id;
let S={idx:0,ans:{},flag:{},end:null,start:null,done:false,fin:null};
try{const r=localStorage.getItem(KEY);if(r)S=JSON.parse(r)}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
const $=s=>document.querySelector(s),app=$('#app');
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function fmt(s){return String(s).split('```').map((p,i)=>i%2?'<pre>'+esc(p.replace(/^[a-z]*\n/,''))+'</pre>':esc(p).replace(/`([^`]+)`/g,'<code>$1</code>')).join('')}
const hms=ms=>{ms=Math.max(0,ms);const t=Math.floor(ms/1000);return [Math.floor(t/3600),Math.floor(t%3600/60),t%60].map(x=>String(x).padStart(2,'0')).join(':')};
const same=(a,b)=>a.length===b.length&&a.every(x=>b.includes(x));

function intro(){app.innerHTML=`<div class="card"><h2>${E.questions.length} questões · ${E.minutes} min</h2>
<p>Itens de múltipla resposta dizem quantas opções marcar; só vale se acertar todas. Você pode marcar questões para revisar e navegar livremente. O tempo é contínuo e a prova é finalizada sozinha quando zera. Nada de abrir docs, ok? A prova real é fechada.</p>
<button class="pri" id="go">Iniciar</button></div>`;$('#go').onclick=()=>{S.start=Date.now();S.end=S.start+E.minutes*60000;save();render()}}

function render(){
  if(S.done)return results();
  if(!S.end)return intro();
  $('#finish').style.display=$('#flagbtn').style.display='';
  const q=E.questions[S.idx],sel=S.ans[q.id]||[];
  $('#prog').textContent=`· ${Object.keys(S.ans).length}/${E.questions.length} respondidas`;
  $('#flagbtn').textContent=S.flag[q.id]?'Desmarcar':'Marcar p/ revisar';
  app.innerHTML=`<div class="card"><div class="meta">Questão ${S.idx+1} de ${E.questions.length} · selecione ${q.select}</div>
  <div class="stem">${fmt(q.stem)}</div>${q.options.map(o=>`<div class="opt ${sel.includes(o.id)?'on':''}" data-id="${o.id}"><b>${o.id}.</b><span>${fmt(o.text)}</span></div>`).join('')}</div>
  <div class="row"><button id="prev" ${S.idx?'':'disabled'}>Anterior</button><button id="next" ${S.idx<E.questions.length-1?'':'disabled'}>Próxima</button></div>
  <div class="nav">${E.questions.map((x,i)=>`<button data-i="${i}" class="${i===S.idx?'cur':S.ans[x.id]?'ans':''} ${S.flag[x.id]?'flag':''}">${i+1}</button>`).join('')}</div>`;
  document.querySelectorAll('.opt').forEach(el=>el.onclick=()=>{
    let cur=S.ans[q.id]||[];const id=el.dataset.id;
    if(q.select===1)cur=[id];else if(cur.includes(id))cur=cur.filter(x=>x!==id);else if(cur.length<q.select)cur=[...cur,id];
    S.ans[q.id]=cur;save();render()});
  $('#prev').onclick=()=>{S.idx--;save();render()};$('#next').onclick=()=>{S.idx++;save();render()};
  document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>{S.idx=+b.dataset.i;save();render()});
}
$('#flagbtn').onclick=()=>{const q=E.questions[S.idx];S.flag[q.id]=!S.flag[q.id];save();render()};
$('#finish').onclick=()=>{const un=E.questions.length-Object.keys(S.ans).length;if(confirm(un?`Faltam ${un} sem resposta. Finalizar mesmo assim?`:'Finalizar o simulado?'))finish()};

function finish(){S.done=true;S.fin=Date.now();save();results()}
function results(){
  $('#finish').style.display=$('#flagbtn').style.display='none';
  const per=E.questions.map(q=>({id:q.id,domain:q.domain,skill:q.skill,selected:S.ans[q.id]||[],correct_ids:q.correct,correct:same(S.ans[q.id]||[],q.correct)}));
  const ok=per.filter(x=>x.correct).length,pct=Math.round(1000*ok/per.length)/10,est=Math.round(100+900*ok/per.length);
  const dom={};per.forEach(x=>{(dom[x.domain]=dom[x.domain]||{n:0,ok:0});dom[x.domain].n++;dom[x.domain].ok+=x.correct?1:0});
  const used=Math.round(((S.fin||Date.now())-S.start)/60000);
  const result={exam_id:E.id,finished_at:new Date(S.fin||Date.now()).toISOString(),minutes_used:used,correct:ok,total:per.length,pct,est_scaled:est,per_question:per};
  $('#timer').textContent='fim';
  app.innerHTML=`<div class="card"><h2>${ok}/${per.length} · ${pct}%</h2>
  <p>Nota escalada <b>estimada</b>: ~${est} (corte real: ${E.pass_scaled}). É uma régua linear grosseira — a conversão oficial não é pública, então use como termômetro, não como previsão.</p>
  <table><tr><th>Domínio</th><th>Acertos</th><th>%</th></tr>${Object.keys(dom).sort().map(d=>`<tr><td>${d} · ${E.domains[d].name}</td><td>${dom[d].ok}/${dom[d].n}</td><td>${Math.round(100*dom[d].ok/dom[d].n)}%</td></tr>`).join('')}</table>
  <div class="row"><button class="pri" id="dl">Baixar result.json</button><button id="reset">Refazer (limpar)</button></div>
  <p><small>Depois: <code>python simulado.py grade result.json</code> e peça ao professor (/revisar) para destrinchar os erros.</small></p></div>
  ${E.questions.map((q,i)=>{const r=per[i];return `<div class="card"><div class="meta">${i+1}. ${q.id} · ${q.skill} · ${r.correct?'acertou':'errou'}</div><div class="stem">${fmt(q.stem)}</div>
  ${q.options.map(o=>`<div class="opt ${q.correct.includes(o.id)?'ok':''} ${r.selected.includes(o.id)&&!q.correct.includes(o.id)?'no':''}"><b>${o.id}.</b><span>${fmt(o.text)} ${q.correct.includes(o.id)?'✓':''}${r.selected.includes(o.id)?' ← sua resposta':''}</span></div>`).join('')}
  <div class="rev"><h4>POR QUE</h4>${fmt(q.rationale)}<h4>DISTRATORES</h4>${Object.entries(q.why_wrong).map(([k,v])=>`<div><b>${k}.</b> ${fmt(v)}</div>`).join('')}
  ${q.source&&q.source.url?`<h4>FONTE</h4><a href="${esc(q.source.url)}" target="_blank" rel="noopener">${esc(q.source.url)}</a>`:''}</div></div>`}).join('')}`;
  $('#dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(result,null,1)],{type:'application/json'}));a.download='result.json';a.click()};
  $('#reset').onclick=()=>{if(confirm('Apagar progresso desta sessão?')){try{localStorage.removeItem(KEY)}catch(e){}location.reload()}};
}
setInterval(()=>{if(!S.end||S.done)return;const left=S.end-Date.now();$('#timer').textContent=hms(left);$('#timer').classList.toggle('low',left<600000);if(left<=0){alert('Tempo esgotado.');finish()}},500);
render();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--n", type=int, default=60)
    b.add_argument("--minutes", type=int, default=120)
    b.add_argument("--seed")
    b.add_argument("--reviewed-only", action="store_true")
    b.add_argument("--no-shuffle", action="store_true")
    g = sub.add_parser("grade")
    g.add_argument("result")
    a = ap.parse_args()
    {"build": cmd_build, "grade": cmd_grade}[a.cmd](a)


if __name__ == "__main__":
    main()
