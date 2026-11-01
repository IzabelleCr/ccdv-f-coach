---
description: Gera questões originais para as skills com maior déficit no banco
argument-hint: "[skill D2.api | auto] [n=10]"
---
Fábrica, etapa de geração (CLAUDE.md §4.2). Argumentos: $ARGUMENTS

1. Se "auto" ou vazio: `python validate_bank.py --target 300` e escolha as 3 skills com maior (falta × peso).
2. Confirme que o corpus cobre a skill (`python scraper.py search --skill X --k 3`). Se não cobrir, rode /coletar primeiro.
3. Para cada skill, delegue ao subagente question-writer (skill, n). Rode em paralelo se forem skills diferentes.
4. Em seguida, rode /revisar automaticamente. Questão sem revisão não vai para simulado com --reviewed-only.
