---
type: issue
status: backlog
tags: [tests]
kind: task
created: 2026-11-01
creator: claude
---

# Teste que garante que `scanner.py` roda no Python 3.7 só com a biblioteca padrão

`src/gitpair/scanner.py` é enviado para `python3 -` na máquina remota. A regra
(stdlib só, Python 3.7, sem importar `gitpair`) está no `AGENTS.md` e no
`CONTRIBUTING.md`, mas nenhuma ferramenta a verifica: o CI roda em 3.11+.

Proposta: um teste em `tests/test_scanner.py` que

- faz `ast.parse(source, feature_version=(3, 7))` no arquivo;
- percorre os `import`/`from ... import` e falha se algum módulo não estiver em
  `sys.stdlib_module_names` ou começar com `gitpair`.

`feature_version` não pega tudo (por exemplo, funções novas da stdlib), mas pega
sintaxe nova e imports proibidos, que são os erros mais prováveis.

Origem: fase de `AGENTS.md` do bootstrap do r2 (regra que uma ferramenta pode
verificar).
