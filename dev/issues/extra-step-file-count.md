---
type: issue
status: backlog
tags: [tui, ignored-files]
kind: defect
created: 2026-10-14
---

# "copy N files" conta arquivos que não serão copiados

O texto "copy N files" de um passo extra é calculado antes de a política de
arquivos ser escolhida. Por isso, com `skip conflicting files`, ele pode contar
arquivos que não são copiados. Calcule a descrição a partir de
`resolved_files`.

Origem: `BACKLOG.md`, seção "UI".
