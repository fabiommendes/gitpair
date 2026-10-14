---
type: issue
status: backlog
tags: [layout]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, tooling-root/dev/docs/repository-layout.md]
kind: task
created: 2026-10-14
---

# Migrar para o layout do ADR 0003

O ADR 0003 do tooling-root unifica o layout dos repositórios. O gitpair diverge
assim:

## Plano

- `dev/specs/`: tirar. A spec vai no corpo da issue. Apagar `TEMPLATE.md`.
- `BACKLOG.md`: cada item vira uma issue em `dev/issues/` com `status: backlog`.
  As limitações conhecidas que o usuário precisa saber vão para `docs/`.
- `ROADMAP.md`: cada item vira uma issue com `milestone`. O arquivo volta a
  existir quando o `r2 roadmap` gerar o roadmap.
- Issues fechadas ficam no repositório com status fechado, em vez de serem
  apagadas. Atualizar `dev/README.md`.
- `AGENTS.md`: acrescentar o comando de checagem e as ordens permanentes,
  conforme o esqueleto de `repository-layout.md`.
