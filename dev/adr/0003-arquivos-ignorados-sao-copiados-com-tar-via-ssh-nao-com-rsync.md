---
type: adr
status: accepted
tags: [files, remote]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# Arquivos ignorados são copiados com tar via ssh, não com rsync

## Context

A opção `sync_ignored` copia entre as máquinas arquivos que o git ignora
(`.env`, dados locais). É preciso uma ferramenta de cópia disponível nas duas
máquinas.

## Options

- rsync.
- tar via ssh, com o `tarfile` do Python do lado local.

## Decision

Os passos "files there" e "files here" usam tar via ssh
(`docs/how-it-works.md`, "Extra steps"). Do lado local, o tar é montado e
extraído com `tarfile`; a extração de arquivos vindos da remota usa
`filter="data"` (`src/gitpair/execute.py:107`).

Motivos: rsync não está instalado em todo lugar (`AGENTS.md`, "Regras fáceis
de quebrar"). O filtro `data` bloqueia caminhos absolutos, links para fora do
repositório e arquivos especiais, porque o conteúdo do repositório não é
confiável (`SECURITY.md`, "Trust model").

## Consequences

- Não há cópia incremental por bloco: cada arquivo mais novo vai inteiro.
- A comparação dos arquivos é feita pelo próprio gitpair, por `[size, mtime]`.
