---
type: adr
status: accepted
tags: [remote, git]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# A máquina remota nunca se conecta de volta à local

## Context

Todos os comandos partem da máquina local (`docs/how-it-works.md`, "One run").
Para levar commits à remota, um push direto para `refs/heads/<branch>` falha
quando a branch está em checkout lá (`receive.denyCurrentBranch`).

## Options

- Push direto para `refs/heads/<branch>`: falha com a branch em checkout.
- A remota faz fetch da local: exige que a remota alcance a local.
- Push para uma ref temporária e fast-forward na remota.

## Decision

A remota nunca abre conexão com a local. Para levar commits, a local faz push
para `refs/gitpair/incoming/<branch>` (incoming ref) e manda a remota fazer
`git merge --ff-only` (ou `reset --hard`, em `take-local`) a partir dela. A ref
é apagada depois, mesmo quando o fast-forward falha (commit 4f88e54).

Motivos (`docs/how-it-works.md`): a máquina local costuma ser um laptop atrás
de NAT, e o push direto esbarra em `receive.denyCurrentBranch`.

## Consequences

- Só a local precisa de acesso ssh à remota.
- `push`, `merge` e `take-local` têm dois passos e deixam a incoming ref para
  trás se o processo morrer entre eles.
- `autopush` a partir da remota fica difícil
  (`dev/issues/autopush-from-remote.md`).
