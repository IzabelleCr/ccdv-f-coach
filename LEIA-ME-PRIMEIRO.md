# CCDV-F Coach: como usar

Estudo para o **Claude Certified Developer – Foundations**. O banco de questões e a documentação oficial já vêm prontos, então você não precisa raspar nada.

## O que você precisa
- **Python 3.10 ou mais novo** (`python --version`)
- **Claude Code** (`claude` no terminal, no app desktop ou na extensão do VS Code)
- Opcional: `pip install requests beautifulsoup4`. Só é necessário se quiser que o professor busque trechos da doc (`scraper.py search`) ou atualizar o corpus. O simulado e o tutor funcionam sem isso.

## Começando
1. Descompacte o .zip.
2. Abra o Claude Code **dentro da pasta `ccdv-f-coach`** (não na pasta de cima). É isso que faz o agente ler o `CLAUDE.md` e enxergar os comandos `/simulado`, `/estudar` etc.
   ```bash
   cd ccdv-f-coach
   claude
   ```
3. Converse normalmente ou use os comandos:

| Comando | O que faz |
|---|---|
| `/simulado` | prova de 60 questões ponderada pelo edital, com timer de 2h numa página HTML |
| `/simulado 53 120` | mesmo formato da prova real (53 itens / 120 min) |
| `/estudar 5 D5` | modo professor: 5 questões do domínio 5, corrigidas e explicadas |
| `/estudar weak` | ataca as suas skills mais fracas (use depois de ~30 respostas) |
| `/progresso` | acurácia por skill e "já dá pra marcar a prova?" |
| "me explica prompt caching" | aula sobre o tema + questões do banco |

## Fluxo do simulado
1. `/simulado` gera `sessions/<id>/exam.html`. Abra no navegador.
2. Faça a prova. O progresso fica salvo no navegador, então recarregar a página não perde nada.
3. No final, clique em **Baixar result.json** e diga ao Claude onde o arquivo está (ou rode `python simulado.py grade caminho/result.json`).
4. O agente mostra onde você está perdendo pontos e sugere uma sessão de professor focada nisso.

## Sem Claude Code (só terminal)
```bash
python simulado.py build --n 60 --minutes 120   # gera o HTML da prova
python tutor.py next --n 5 --domain D2          # ATENÇÃO: imprime o gabarito junto
python tutor.py stats
```

## Bom saber
- O seu histórico fica em `data/progress.json` (é criado no primeiro uso). Ele é só seu.
- As questões são **originais** e ancoradas na doc oficial. Não são questões da prova real, que é protegida por NDA.
- A "nota escalada estimada" é uma régua aproximada. A conversão oficial não é pública.
- Para gerar mais questões ou atualizar a doc: `/coletar`, `/gerar auto 10`, `/revisar` (precisa das libs opcionais e de internet).
