---
type: issue
status: in_progress
tags: [layout, r2]
kind: task
created: 2026-11-01
creator: claude
---

# Preparar o repositório para o r2

Rodar o `bootstrap` do r2: layout, `AGENTS.md` e `r2 check`, glossário,
descrições de módulos, ADRs das decisões já no código, user stories com os
testes e2e e os marcadores no código.

## Plano

- [x] `r2 init` e `r2.toml` com `[commands.check]`.
- [x] `AGENTS.md`: `r2 check`, regras citando os ADRs; issues para regras verificáveis por ferramenta.
- [x] Glossário: frontmatter, termos novos, "Conflict" -> "File conflict".
- [x] Descrição de `src/gitpair/__main__.py`.
- [x] ADRs 0001 a 0008.
- [x] User stories do papel `user`, citadas pelos testes.
- [x] Marcadores `r2: adr/NNNN` no código.
- [ ] Mover os testes das stories para `tests/stories/`.
