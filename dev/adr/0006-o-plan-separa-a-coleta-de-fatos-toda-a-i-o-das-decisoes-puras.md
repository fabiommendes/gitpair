---
type: adr
status: accepted
tags: [plan, architecture]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# O plan separa a coleta de fatos (toda a I/O) das decisões (puras)

## Context

O commit f41088b refatorou `plan.build`, que misturava acesso às máquinas e
regras de decisão.

## Options

Não encontradas nos registros.

## Decision

`plan.build` roda `_facts.gather`, que faz toda a I/O com as duas máquinas e
devolve erros como dados, e depois `_decide.decide`, que é puro e monta cada
`Item` de uma vez. Os tipos ficam em `_model`.

Motivo parcial (commit f41088b): permitir testes unitários das decisões sobre
fatos montados à mão.

## Consequences

- `tests/test_decide.py` testa as regras sem git nem ssh.
- Uma regra nova que precise de um dado novo das máquinas muda dois módulos:
  o fato em `_facts.py` e a decisão em `_decide.py`.
- `_decide.py` não pode chamar `Host` nem rodar comandos.
