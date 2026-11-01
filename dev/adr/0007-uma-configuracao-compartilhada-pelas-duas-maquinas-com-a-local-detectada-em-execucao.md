---
type: adr
status: accepted
tags: [config]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# Uma configuração compartilhada pelas duas máquinas, com a local detectada em execução

## Context

O gitpair roda em qualquer uma das duas máquinas. Cada uma precisa saber qual
é ela e qual é a outra (`src/gitpair/config.py:136`, `Config.local_host`).

## Options

Não encontradas nos registros.

## Decision

Um único arquivo TOML descreve as duas máquinas em `[hosts.<name>]`. A local é
a que tem `hostname` igual ao da máquina (ou a escolhida com `--as`); a outra
é a remota. Com `push_config = true`, mudanças na configuração (track e
ignore) são copiadas para a outra máquina (`src/gitpair/session.py:85`).

Motivo não registrado.

## Consequences

- O mesmo arquivo serve nas duas máquinas, sem versões divergentes por padrão.
- Edições feitas nas duas ao mesmo tempo colidem; o merge das listas `repos`
  fica para `dev/issues/merge-remote-config.md`.
- Hostnames iguais ou trocados exigem `hostname` explícito ou `--as`.
