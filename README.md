# CCDV-F Coach

App de estudo em Streamlit para o **Claude Certified Developer – Foundations** (53 questões, 120 min, corte 720/1000). Roda 100% local, sem API e sem custo.

## Como rodar

Requer Python 3.10+.

```bash
pip install streamlit
streamlit run app.py
```

Abre em `http://localhost:8501`.

## O que tem

- **Estudar:** uma questão por vez, com filtro por domínio e skill e modo "focar nas fracas". Depois de responder, mostra a explicação em português e o porquê de cada distrator.
- **Simulado:** prova com timer, navegação entre questões e marcação para revisar. Nota estimada e erros por domínio no final.
- **Progresso:** acurácia por skill e evolução dos simulados.
- **Glossário:** inglês técnico que aparece nos enunciados.

## Estrutura

```
app.py              interface Streamlit
common.py           leitura do banco, blueprint e progresso
simulado.py         sorteio ponderado das questões do simulado
tutor.py            priorização de questões (modo "fracas")
bank/*.jsonl        banco de questões, uma por linha
data/blueprint.json domínios, skills e pesos
data/pt/            traduções em português
data/glossary.json  glossário
.streamlit/         tema
```

O histórico fica em `data/progress.json`, criado no primeiro uso e ignorado pelo git.

## Sobre as questões

São originais, não são itens da prova real (protegida por NDA). A "nota escalada estimada" é uma régua linear aproximada; a conversão oficial não é pública.
