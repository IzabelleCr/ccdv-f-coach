---
description: Monta um simulado CCDV-F ponderado pelo blueprint (padrão 60 questões / 120 min) com timer em HTML
argument-hint: "[n=60] [min=120] [reviewed-only]"
---
Modo Simulado (CLAUDE.md §2). Argumentos: $ARGUMENTS

1. `python validate_bank.py`: se faltar volume, diga quanto falta e pergunte se roda /gerar antes ou faz um simulado proporcional menor.
2. `python simulado.py build` com --n/--minutes/--reviewed-only conforme os argumentos.
3. Entregue o exam.html e explique em 3 linhas: timer contínuo, só vale acertar tudo nas de múltipla resposta, baixar o result.json no fim.
4. Não comente o conteúdo das questões até ele terminar.
