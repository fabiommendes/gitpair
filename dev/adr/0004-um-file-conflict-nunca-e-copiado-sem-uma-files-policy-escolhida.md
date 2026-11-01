---
type: adr
status: accepted
tags: [files, safety]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# Um file conflict nunca é copiado sem uma files policy escolhida

## Context

Antes do commit 39eb93e, a cópia de arquivos ignorados era incondicional: o
arquivo mais novo sobrescrevia o outro (`docs/configuration.md:75`, "the
previous, unconditional behavior"). Isso podia apagar uma versão editada nas
duas máquinas.

## Options

- Mais novo vence, sempre (comportamento anterior).
- Perguntar por item: "newer wins" ou "skip conflicts".

## Decision

Um arquivo de `sync_ignored` presente nas duas máquinas com `mtime` diferente
é um file conflict e só é copiado depois que o usuário escolhe a files policy
do item. `--auto` trata a policy não decidida como `skip-conflicts` e ainda
copia os arquivos que existem de um lado só. Mesmo `mtime` com tamanho
diferente gera um aviso e nunca é copiado (`src/gitpair/_decide.py:42`,
`compare_files`).

Motivo: nenhuma ação perde trabalho sem escolha explícita do usuário
(`CONTRIBUTING.md`, "Code style").

## Consequences

- Repositórios com arquivos ignorados editados nas duas máquinas sempre param
  numa pergunta.
- Exclusões não se propagam; isso fica para
  `dev/issues/ignored-files-manifest.md`.
