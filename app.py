"""Interface Streamlit do CCDV-F Coach (100% local, não usa Claude/crédito).

  pip install streamlit
  streamlit run app.py
"""
import json
import random
import time
from collections import defaultdict

import streamlit as st

from common import (ROOT, load_bank, load_blueprint, load_progress, now_iso, record_answer,
                    save_progress, skills_index)
from simulado import pick, shuffle_options
from tutor import priority

st.set_page_config(page_title="CCDV-F Coach", page_icon="🎓", layout="centered")

BP = load_blueprint()
SK = skills_index(BP)
BANK = load_bank()
DOMAINS = {d["id"]: d["name"] for d in BP["domains"]}
PASS = BP["exam"]["passing_scaled_score"]


@st.cache_data
def load_pt():
    """Traduções PT-BR (data/pt/*.json), indexadas pelo id da questão."""
    out = {}
    for f in sorted((ROOT / "data" / "pt").glob("*.json")):
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


PT = load_pt()
BY_ID = {q["id"]: q for q in BANK}


def pt_version(q):
    """Tradução da questão com os ids das opções alinhados à versão (possivelmente embaralhada) exibida."""
    t = PT.get(q["id"])
    orig = BY_ID.get(q["id"])
    if not t or not orig:
        return None
    orig_id = {o["text"]: o["id"] for o in orig["options"]}
    new_to_orig = {o["id"]: orig_id[o["text"]] for o in q["options"]}
    return {
        "stem": t["stem"],
        "o": {nid: t["o"][oid] for nid, oid in new_to_orig.items()},
        "r": t["r"],
        "w": {nid: t["w"][oid] for nid, oid in new_to_orig.items() if oid in t["w"]},
    }


def ss(key, default):
    return st.session_state.setdefault(key, default)


def fmt(text):
    """Streamlit já renderiza markdown (``` e `code`); só protege o '$' de virar LaTeX."""
    return text.replace("$", r"\$")


def is_correct(selected, q):
    return sorted(selected) == sorted(q["correct"])


CSS = """
<style>
.block-container {max-width: 760px; padding-top: 2.2rem; padding-bottom: 4rem;}
#MainMenu, footer, [data-testid="stToolbar"] {visibility: hidden;}
h1, h2, h3 {letter-spacing: -0.02em;}
[data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #e6e8f0;}

/* cartão do enunciado */
.st-key-stem {background:#fff; border:1px solid #e6e8f0; border-radius:16px;
  padding:1.2rem 1.4rem; box-shadow:0 1px 3px rgba(31,36,51,.05); margin:.3rem 0 1rem; font-size:1.05rem;}

/* opções clicáveis */
.st-key-optlist button {width:100%; justify-content:flex-start; text-align:left; background:#fff;
  border:1.5px solid #dfe2ee; border-radius:14px; padding:.85rem 1.1rem; min-height:3.2rem;
  color:#1f2433; transition:all .12s ease; box-shadow:0 1px 2px rgba(31,36,51,.04);}
.st-key-optlist button:hover {border-color:#5b4bdb; background:#f3f1ff; transform:translateY(-1px);}
.st-key-optlist button[data-testid="stBaseButton-primary"] {background:#eeebff; border-color:#5b4bdb;
  box-shadow:0 0 0 3px rgba(91,75,219,.18); color:#1f2433;}
.st-key-optlist button p {text-align:left; margin:0; font-size:1rem; line-height:1.45;}

/* opções após responder */
.st-key-optlist-done [class*="st-key-opt-"] {border:1.5px solid #dfe2ee; border-radius:14px;
  padding:.8rem 1.1rem; margin-bottom:.55rem; background:#fff;}
.st-key-optlist-done [class*="st-key-opt-"] p {margin:0;}
.st-key-optlist-done .st-key-opt-ok {background:#e8f8ee; border-color:#2fb36b;}
.st-key-optlist-done .st-key-opt-bad {background:#fdecec; border-color:#e0524f;}
.st-key-optlist-done .st-key-opt-dim {opacity:.6;}

/* botões de ação */
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {border-radius:12px;}
.stButton > button {border-radius:12px; font-weight:600;}
[data-testid="stMetric"] {background:#fff; border:1px solid #e6e8f0; border-radius:14px; padding:.8rem 1rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def render_options(q, key, disabled=False):
    """Opções como cartões clicáveis. Retorna a lista de ids selecionados.

    A seleção fica em st.session_state[key] (lista). Para select>1, o clique alterna
    a opção; ao passar do limite, a mais antiga sai.
    """
    need = q["select"]
    st.session_state.setdefault(key, [])

    def toggle(oid):
        cur = list(st.session_state[key])
        if oid in cur:
            cur.remove(oid)
        elif need == 1:
            cur = [oid]
        else:
            cur = (cur + [oid])[-need:]
        st.session_state[key] = cur

    if need > 1:
        st.caption(f"Selecione **{need}** opções · {len(st.session_state[key])}/{need} escolhidas")
    with st.container(key="optlist"):
        for o in q["options"]:
            chosen = o["id"] in st.session_state[key]
            st.button(f"**{o['id']}**  {fmt(o['text'])}", key=f"{key}_{o['id']}",
                      type="primary" if chosen else "secondary", on_click=toggle, args=(o["id"],),
                      disabled=disabled, width="stretch")
    return list(st.session_state[key])


def render_result_options(q, selected):
    """Opções travadas, com certa em verde e erro do aluno em vermelho."""
    with st.container(key="optlist-done"):
        for o in q["options"]:
            right, mine = o["id"] in q["correct"], o["id"] in selected
            cls = "ok" if right else "bad" if mine else "dim"
            note = " ✓" if right else " ✗ sua resposta" if mine else ""
            with st.container(key=f"opt-{cls}-{o['id']}"):
                st.markdown(f"**{o['id']}**  {fmt(o['text'])}{note}")


def render_review(q, selected):
    ok = is_correct(selected, q)
    (st.success if ok else st.error)(
        ("Acertou! " if ok else "Errou. ") + "Resposta certa: " + ", ".join(sorted(q["correct"])))
    t = pt_version(q)
    if t:
        st.markdown("🇧🇷 **Em português**")
        st.markdown(fmt(t["stem"]))
        for o in q["options"]:
            tag = " ✓" if o["id"] in q["correct"] else ""
            st.markdown(f"**{o['id']}.** {fmt(t['o'][o['id']])}{tag}")
        st.markdown("**Por que a certa é certa**")
        st.markdown(fmt(t["r"]))
        st.markdown("**Por que cada distrator engana**")
        for k, v in sorted(t["w"].items()):
            st.markdown(f"- **{k}.** {fmt(v)}")
        with st.expander("🇺🇸 Original em inglês"):
            _render_review_en(q)
    else:
        _render_review_en(q)
    url = (q.get("source") or {}).get("url")
    if url:
        st.caption(f"Fonte: {url}")


def _render_review_en(q):
    st.markdown("**Why the correct answer is correct**")
    st.markdown(fmt(q["rationale"]))
    st.markdown("**Why each distractor misleads**")
    for k, v in sorted(q.get("why_wrong", {}).items()):
        st.markdown(f"- **{k}.** {fmt(v)}")


def q_header(q):
    s = SK.get(q["skill"], {})
    st.caption(f"{q['id']} · {q['domain']} · {s.get('name', q['skill'])}")


# ───────────────────────── Estudar ─────────────────────────
def page_study():
    st.header("Estudar")
    c1, c2, c3 = st.columns(3)
    dom = c1.selectbox("Domínio", ["Todos"] + list(DOMAINS), format_func=lambda d: d if d == "Todos" else f"{d} · {DOMAINS[d]}")
    skills = [s for s, v in SK.items() if dom == "Todos" or v["domain"] == dom]
    skill = c2.selectbox("Skill", ["Todas"] + skills, format_func=lambda s: s if s == "Todas" else SK[s]["name"])
    weak = c3.toggle("Focar nas fracas", help="Prioriza o que você mais erra, ponderado pelo peso da skill.")

    def next_question():
        pool = [q for q in BANK
                if (dom == "Todos" or q["domain"] == dom) and (skill == "Todas" or q["skill"] == skill)]
        if not pool:
            st.session_state.study_q = None
            return
        prog = load_progress()
        pool.sort(key=lambda q: priority(q, prog, SK, weak), reverse=True)
        st.session_state.study_q = pool[0]
        st.session_state.study_n = ss("study_n", 0) + 1
        st.session_state.study_done = False

    filt = (dom, skill, weak)
    if st.session_state.get("study_filter") != filt:
        st.session_state.study_filter = filt
        next_question()
    if "study_q" not in st.session_state:
        next_question()

    q = st.session_state.study_q
    if q is None:
        st.warning("Não há questões para esse filtro. Peça `/gerar` ao Claude para completar o banco.")
        return

    # embaralha as opções uma vez por questão exibida
    shuf_key = (q["id"], st.session_state.get("study_n"))
    if st.session_state.get("study_shuf_key") != shuf_key:
        st.session_state.study_shuf_key = shuf_key
        st.session_state.study_qs = shuffle_options(q, random.Random())
    q = st.session_state.study_qs

    q_header(q)
    with st.container(key="stem"):
        st.markdown(fmt(q["stem"]))
    done = st.session_state.get("study_done", False)
    if done:
        render_result_options(q, st.session_state.study_sel)
        sel = st.session_state.study_sel
    else:
        sel = render_options(q, f"study_opt_{st.session_state.get('study_n')}")
    if not done and (t := pt_version(q)):
        with st.expander("🇧🇷 Ver enunciado e opções em português (dica)"):
            st.markdown(fmt(t["stem"]))
            for o in q["options"]:
                st.markdown(f"**{o['id']}.** {fmt(t['o'][o['id']])}")

    if not done:
        if st.button("Responder", type="primary", disabled=len(sel) != q["select"]):
            p = load_progress()
            record_answer(p, q["id"], is_correct(sel, q))
            save_progress(p)
            st.session_state.study_done = True
            st.session_state.study_sel = sel
            st.rerun()
    else:
        render_review(q, st.session_state.study_sel)
        if st.button("Próxima questão", type="primary"):
            next_question()
            st.rerun()


# ───────────────────────── Simulado ─────────────────────────
def build_exam(n, minutes, reviewed_only):
    rng = random.Random(int(time.time()))
    seen = set(load_progress()["answers"])
    chosen, _quota, missing = pick(BANK, SK, n, rng, seen, reviewed_only)
    rng.shuffle(chosen)
    return {"qs": [shuffle_options(q, rng) for q in chosen], "minutes": minutes, "missing": missing,
            "idx": 0, "ans": {}, "flag": set(), "end": None, "done": False, "id": time.strftime("%Y%m%d-%H%M%S")}


def finish_exam(ex):
    ex["done"] = True
    prog = load_progress()
    ok = 0
    for q in ex["qs"]:
        c = is_correct(ex["ans"].get(q["id"], []), q)
        ok += c
        record_answer(prog, q["id"], c)
    total = len(ex["qs"])
    prog["exams"].append({"id": ex["id"], "date": now_iso(), "pct": round(100 * ok / total, 1),
                          "est_scaled": round(100 + 900 * ok / total)})
    save_progress(prog)


@st.fragment(run_every=1)
def timer(ex):
    left = int(ex["end"] - time.time())
    if left <= 0:
        finish_exam(ex)
        st.rerun()
    h, m, s = left // 3600, left % 3600 // 60, left % 60
    st.metric("Tempo restante", f"{h:02d}:{m:02d}:{s:02d}")


def page_exam():
    st.header("Simulado")
    ex = st.session_state.get("exam")

    if ex is None:
        n = st.number_input("Nº de questões", 5, 60, 53, help="53 = formato da prova real")
        minutes = st.number_input("Minutos", 5, 120, 120)
        rev = st.checkbox("Só questões revisadas", value=False)
        if len(BANK) < n:
            st.warning(f"O banco tem só {len(BANK)} questões; o simulado vai ter menos que {n}.")
        if st.button("Iniciar simulado", type="primary"):
            ex = build_exam(int(n), int(minutes), rev)
            ex["end"] = time.time() + ex["minutes"] * 60
            st.session_state.exam = ex
            st.rerun()
        return

    if ex["done"]:
        return exam_results(ex)

    qs, i = ex["qs"], ex["idx"]
    q = qs[i]
    top = st.columns([2, 1, 1])
    with top[0]:
        timer(ex)
    top[1].metric("Respondidas", f"{len(ex['ans'])}/{len(qs)}")
    if top[2].button("Finalizar", type="primary"):
        st.session_state.confirm_finish = True
    if st.session_state.get("confirm_finish"):
        st.warning(f"Faltam {len(qs) - len(ex['ans'])} sem resposta. Finalizar mesmo assim?")
        a, b = st.columns(2)
        if a.button("Sim, finalizar"):
            st.session_state.confirm_finish = False
            finish_exam(ex)
            st.rerun()
        if b.button("Voltar à prova"):
            st.session_state.confirm_finish = False
            st.rerun()

    st.divider()
    st.caption(f"Questão {i + 1} de {len(qs)}" + (" · 🚩 marcada" if q["id"] in ex["flag"] else ""))
    with st.container(key="stem"):
        st.markdown(fmt(q["stem"]))
    key = f"exam_{ex['id']}_{q['id']}"
    if key not in st.session_state and q["id"] in ex["ans"]:
        st.session_state[key] = list(ex["ans"][q["id"]])
    sel = render_options(q, key)
    if sel:
        ex["ans"][q["id"]] = sel
    else:
        ex["ans"].pop(q["id"], None)

    c = st.columns(3)
    if c[0].button("← Anterior", disabled=i == 0):
        ex["idx"] -= 1
        st.rerun()
    if c[1].button("🚩 Desmarcar" if q["id"] in ex["flag"] else "🚩 Marcar p/ revisar"):
        ex["flag"] ^= {q["id"]}
        st.rerun()
    if c[2].button("Próxima →", disabled=i == len(qs) - 1):
        ex["idx"] += 1
        st.rerun()

    with st.expander("Navegação"):
        cols = st.columns(10)
        for j, x in enumerate(qs):
            mark = ("🚩" if x["id"] in ex["flag"] else "✅" if x["id"] in ex["ans"] else "⬜")
            if cols[j % 10].button(f"{mark}{j + 1}", key=f"nav{j}"):
                ex["idx"] = j
                st.rerun()


def exam_results(ex):
    qs = ex["qs"]
    per = [(q, ex["ans"].get(q["id"], [])) for q in qs]
    ok = sum(is_correct(s, q) for q, s in per)
    total = len(qs)
    st.subheader(f"{ok}/{total} · {100 * ok / total:.1f}%")
    st.info(f"Nota escalada **estimada**: ~{round(100 + 900 * ok / total)} (corte real: {PASS}). "
            "É uma régua linear grosseira; a conversão oficial não é pública.")

    dom = defaultdict(lambda: [0, 0])
    skill_err = defaultdict(int)
    for q, s in per:
        good = is_correct(s, q)
        dom[q["domain"]][0] += good
        dom[q["domain"]][1] += 1
        if not good:
            skill_err[q["skill"]] += 1
    st.markdown("**Por domínio**")
    st.dataframe([{"Domínio": f"{d} · {DOMAINS[d]}", "Acertos": f"{a}/{n}", "%": round(100 * a / n)}
                  for d, (a, n) in sorted(dom.items())], hide_index=True, width="stretch")
    if skill_err:
        costly = sorted(skill_err, key=lambda s: -skill_err[s] * SK[s]["weight"])[:3]
        st.markdown("**Conceitos mais caros:** " + ", ".join(
            f"{SK[s]['name']} ({skill_err[s]} erro(s))" for s in costly))

    if st.button("Novo simulado", type="primary"):
        st.session_state.exam = None
        st.rerun()
    st.divider()
    only_wrong = st.toggle("Mostrar só os erros", value=True)
    for n, (q, s) in enumerate(per, 1):
        if only_wrong and is_correct(s, q):
            continue
        with st.expander(f"{n}. {q['id']} · {'✅' if is_correct(s, q) else '❌'}"):
            st.markdown(fmt(q["stem"]))
            for o in q["options"]:
                tag = (" ✓" if o["id"] in q["correct"] else "") + (" ← sua resposta" if o["id"] in s else "")
                st.markdown(f"**{o['id']}.** {fmt(o['text'])}{tag}")
            render_review(q, s)


# ───────────────────────── Progresso ─────────────────────────
def page_progress():
    st.header("Progresso")
    prog = load_progress()
    bank = {q["id"]: q for q in load_bank(include_retired=True)}
    agg = defaultdict(lambda: [0, 0])
    for qid, a in prog["answers"].items():
        if qid in bank:
            agg[bank[qid]["skill"]][0] += a["seen"]
            agg[bank[qid]["skill"]][1] += a["correct"]
    total = sum(v[0] for v in agg.values())
    right = sum(v[1] for v in agg.values())
    c1, c2, c3 = st.columns(3)
    c1.metric("Respostas", total)
    c2.metric("Acurácia geral", f"{100 * right / total:.0f}%" if total else "-")
    c3.metric("Questões vistas", f"{len(prog['answers'])}/{len(BANK)}")

    rows = []
    for sid, s in SK.items():
        n, c = agg[sid]
        nbank = sum(1 for q in BANK if q["skill"] == sid)
        rows.append({"Skill": f"{sid} · {s['name']}", "Peso %": s["weight"], "No banco": nbank,
                     "Respostas": n, "Acurácia %": round(100 * c / n) if n else None})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption("“No banco” baixo = skill com pouca questão (peça `/gerar` ao Claude).")

    if prog["exams"]:
        st.markdown("**Simulados**")
        st.line_chart({"%": [e["pct"] for e in prog["exams"]]})

    with st.expander("Zerar histórico"):
        if st.button("Apagar todo o progresso"):
            save_progress({"answers": {}, "exams": []})
            st.rerun()


# ───────────────────────── Glossário ─────────────────────────
def page_glossary():
    st.header("Glossário de inglês técnico")
    st.caption("Palavras que aparecem nos enunciados e nos distratores, e conceitos que a prova cobra.")
    terms = json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))
    q = st.text_input("Buscar", placeholder="ex.: tempts, stateless, hook").strip().lower()
    groups = list(dict.fromkeys(t["group"] for t in terms))
    group = st.selectbox("Grupo", ["Todos"] + groups)
    shown = [t for t in terms
             if (group == "Todos" or t["group"] == group)
             and (not q or q in (t["term"] + t["pt"] + t["note"]).lower())]
    for t in shown:
        st.markdown(f"**{t['term']}** — {t['pt']}  \n{t['note']}")
    st.caption(f"{len(shown)} termos")


PAGES = {"📖 Estudar": page_study, "📝 Simulado": page_exam, "📊 Progresso": page_progress, "🔤 Glossário": page_glossary}
with st.sidebar:
    st.title("CCDV-F Coach")
    page = st.radio("Menu", list(PAGES), label_visibility="collapsed")
    st.caption(f"{len(BANK)} questões no banco")
PAGES[page]()
