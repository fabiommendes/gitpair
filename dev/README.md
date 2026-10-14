# Notas de desenvolvimento

Documentos de trabalho para mantenedores e agentes. Não fazem parte da
documentação de usuário. O layout segue o ADR 0003 do tooling-root
(`~/git/tools/tooling-root/dev/adr/0003-modelo-de-repositorio.md`).

- `issues/`: todo o trabalho, de bug a funcionalidade. Um arquivo por issue,
  `<slug>.md`, sem número, no formato de `r2/dev/spec/issues.md`. A spec de uma
  funcionalidade vai no corpo da issue. Ideias sem data e limitações ficam em
  issues com `status: backlog`; o que tem versão planejada ganha `milestone`.
- Issues fechadas (`completed`, `wont_fix`, `deprecated`, com `closed`) ficam no
  repositório e não são editadas.
