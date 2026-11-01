# CCDV-F Coach

Agente de estudo para o **Claude Certified Developer – Foundations**. Ele roda dentro do Claude Code: abra a pasta e converse.

```bash
pip install requests beautifulsoup4
cd ccdv-f-coach && claude
```

| Comando | Faz |
|---|---|
| `/coletar` | raspa a doc oficial + sinais do Reddit → `corpus/` indexado por skill |
| `/gerar auto 10` | subagente escritor cria questões originais nas skills com mais déficit |
| `/revisar` | subagente revisor (independente) resolve às cegas, confere a fonte, aprova/corrige/rejeita |
| `/simulado` | 60 questões ponderadas pelo blueprint + timer de 2h em HTML |
| `/estudar 5 D5.cost` / `/estudar weak` | modo professor, questão a questão ou em lote |
| `/progresso` | acurácia por skill, evolução, "já dá pra marcar a prova?" |

Primeira vez: `/coletar` → `/gerar auto 10` (repita até ~300) → `/simulado`.

Sem Claude Code, os scripts funcionam sozinhos: `python simulado.py build`, `python tutor.py next --n 5`, `python validate_bank.py`.

**Por que não há "questões que caíram":** o NDA da prova (guia §12–13) proíbe divulgar itens, e quem usa ou espalha dump arrisca ter a credencial revogada. O banco é 100% original e ancorado na doc oficial. O Reddit serve só para saber o que a galera acha difícil.

**Estado do banco-semente:** 28 questões (as 3 amostras oficiais + 25 originais em `draft`). Rode `/revisar` primeiro: o validador apontou 16 com a correta mais longa que os distratores, um vício que entrega a resposta.
