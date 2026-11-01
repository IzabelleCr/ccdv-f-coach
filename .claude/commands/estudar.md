---
description: Modo Professor, questão a questão ou em lote, com explicação didática
argument-hint: "[n=1] [skill D2.api | domínio D5 | weak | tema livre]"
---
Modo Professor (CLAUDE.md §3). Leia professor.md primeiro. Argumentos: $ARGUMENTS

- Número → tamanho do lote. `Dx` → --domain. `Dx.y` → --skill. "weak" → --weak. Texto livre → mapeie para a skill mais próxima pelo blueprint (keywords) e confirme em 1 linha.
- `python tutor.py next ...` → mostre só enunciado + opções (nunca o gabarito).
- Corrija com o roteiro do professor.md e registre cada resposta com `python tutor.py record <id> 0|1`.
- Ao final do lote: resumo de 4 linhas + sugestão do próximo foco (`python tutor.py stats`).
