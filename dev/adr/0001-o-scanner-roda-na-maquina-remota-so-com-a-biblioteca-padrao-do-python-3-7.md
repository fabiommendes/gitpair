---
type: adr
status: accepted
tags: [remote, scanner]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# O scanner roda na máquina remota só com a biblioteca padrão do Python 3.7

## Context

O gitpair precisa do estado dos repositórios das duas máquinas. Na remota, não
há nada instalado além de git e de um `python3` qualquer. O
`src/gitpair/scanner.py` é enviado como fonte para `python3 -` via ssh
(`docs/how-it-works.md`, passo "Scan"; docstring de `scanner.py`).

## Options

Não encontradas nos registros.

## Decision

`scanner.py` usa só a biblioteca padrão, roda no Python 3.7 e não importa nada
de `gitpair`. Motivo (`CONTRIBUTING.md`, "Code style"): ele roda "with whatever
`python3` is there", e assim a remota não precisa instalar nada.

## Consequences

- Instalar o gitpair numa máquina basta; a outra só precisa de git e python3.
- `scanner.py` não usa sintaxe nem APIs posteriores ao 3.7, e não compartilha
  código com o resto do pacote. Nenhum teste verifica isso ainda
  (`dev/issues/scanner-py37-test.md`).
- Erros de saída do scanner chegam como texto; saída que não é JSON vira
  `CommandError` (commit f2bacb3).
