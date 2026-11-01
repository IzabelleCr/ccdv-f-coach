---
description: Roda o scraper (docs oficiais + sinais do Reddit) e indexa por skill
argument-hint: "[docs|reddit|all] [--only id]"
---
CLAUDE.md §4.1. Argumentos: $ARGUMENTS (padrão: all)

1. `python scraper.py <cmd>`. Leia o relatório de falhas no stderr.
2. Seeds com 404: ache a URL nova via WebSearch e corrija data/sources.json, depois rode de novo.
3. Se o Python não tiver rede, faça fallback com WebFetch salvando em corpus/*.md no mesmo formato e rode `python scraper.py index`.
4. Mostre `python scraper.py status` e destaque skills SEM COBERTURA.
