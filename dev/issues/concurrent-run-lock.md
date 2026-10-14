---
type: issue
status: backlog
tags: [sync, concurrency]
kind: defect
created: 2026-10-14
---

# Lock contra duas execuções ao mesmo tempo nas duas máquinas

Não há lock contra duas execuções ao mesmo tempo nas duas máquinas: o push
forçado para `refs/gitpair/incoming/<branch>` pode colidir.

Origem: `BACKLOG.md`, seção "Limitações conhecidas".
