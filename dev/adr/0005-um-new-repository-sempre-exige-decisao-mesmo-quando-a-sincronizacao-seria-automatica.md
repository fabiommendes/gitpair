---
type: adr
status: accepted
tags: [plan, safety]
created: 2026-11-01
decided: 2026-09-28
decided: 2026-11-01
creator: claude
---

# Um new repository sempre exige decisão, mesmo quando a sincronização seria automática

## Context

Um repositório encontrado numa máquina que não está em `repos.track` nem em
`repos.ignore` é um new repository (`src/gitpair/_decide.py:192`). O README
lista "Repository not in the config" como caso que pergunta, com as opções
"sync and track, ignore forever, skip".

## Options

Não encontradas nos registros.

## Decision

O item de um new repository nunca é automático, mesmo que a ação seria um
fast-forward ou um clone. `--auto` só roda ações que o plan marcou como
automáticas, então pula esses itens. A resposta (track ou ignore) é gravada na
configuração compartilhada.

Motivo não registrado.

## Consequences

- A primeira execução numa máquina com muitos repositórios faz muitas
  perguntas.
- Um diretório `.git` acidental não é sincronizado sozinho (caso real no
  commit 7cf35a4).
