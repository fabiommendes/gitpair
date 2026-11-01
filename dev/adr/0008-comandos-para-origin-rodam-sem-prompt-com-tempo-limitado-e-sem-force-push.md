---
type: adr
status: accepted
tags: [origin, safety]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# Comandos para origin rodam sem prompt, com tempo limitado e sem force-push

## Context

O planejamento verifica se origin está atrás, e o passo `origin` faz push
para ele (`autopush`). Um prompt de senha ou uma rede lenta travaria a
execução inteira.

## Options

Não encontradas nos registros.

## Decision

Todo comando que fala com origin usa o ambiente de `_facts.origin_env`
(`GIT_TERMINAL_PROMPT=0`, `BatchMode=yes` no ssh, mantendo o `core.sshCommand` do usuário, e
`LC_ALL=C`) e o limite `ORIGIN_TIMEOUT` de 120 s (`src/gitpair/_facts.py:21`,
`:53`). O push só acontece se origin for ancestral do HEAD; se origin
divergiu, o gitpair informa e não faz nada (`README.md:128`).

Motivos (docstring de `origin_env`): acessar origin nunca pode travar num
prompt de senha, e algumas mensagens de erro do git são reconhecidas pelo
texto, por isso em inglês.

## Consequences

- Chaves com passphrase sem agente fazem o acesso a origin falhar em vez de
  perguntar.
- O gitpair nunca reescreve a história de origin.
