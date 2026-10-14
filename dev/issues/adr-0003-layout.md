---
type: issue
status: completed
tags: [layout]
relatedTo: [tooling-root/dev/adr/0003-modelo-de-repositorio.md, tooling-root/dev/docs/repository-layout.md]
kind: task
created: 2026-10-14
closed: 2026-10-14
---

# Migrar para o layout do ADR 0003

O ADR 0003 do tooling-root unifica o layout dos repositórios. O gitpair diverge
assim:

- `dev/specs/`: tirar. A spec vai no corpo da issue. Apagar `TEMPLATE.md`.
- `BACKLOG.md`: cada item vira uma issue em `dev/issues/` com `status: completed`.
  As limitações conhecidas que o usuário precisa saber vão para `docs/`.
- `ROADMAP.md`: cada item vira uma issue com `milestone`. O arquivo volta a
  existir quando o `r2 roadmap` gerar o roadmap.
- Issues fechadas ficam no repositório com status fechado, em vez de serem
  apagadas. Atualizar `dev/README.md`.
- `AGENTS.md`: acrescentar o comando de checagem e as ordens permanentes,
  conforme o esqueleto de `repository-layout.md`.

## Plano

- [x] Converter cada item de `BACKLOG.md` em uma issue `backlog` com o `kind` certo.
- [x] Converter os itens abertos de `ROADMAP.md` em issues com `milestone: 0.2.0`.
- [x] Mover as limitações conhecidas que o usuário precisa saber para `docs/how-it-works.md`.
- [x] Apagar `BACKLOG.md`, `ROADMAP.md` e `dev/specs/`.
- [x] Atualizar `dev/README.md`: issues fechadas ficam, spec no corpo da issue.
- [x] Atualizar `AGENTS.md`: comando de checagem, mapa, ordens permanentes e fluxo.
- [x] Corrigir os links restantes para `BACKLOG.md`, `ROADMAP.md` e `dev/specs/`.
- [x] Rodar `uv run task ci`.

---
by: claude

Decisões tomadas na migração:

- O item do backlog "só a branch atual é comparada" e o item do roadmap
  "sync every local branch" eram o mesmo trabalho e viraram uma issue só,
  `sync-all-branches`, com `milestone: 0.2.0`.
- Os dois itens de teste via `ssh localhost` (seção "Testes" e item T4 da
  revisão) viraram uma issue só, `ssh-integration-test`, com os dois textos.
- Os itens do roadmap estavam em inglês; o corpo das issues traz a tradução e
  a frase original.
- As limitações conhecidas foram para uma seção `Known limitations` em
  `docs/how-it-works.md`, em inglês. As issues continuam abertas para cada uma.
- `kind`: `defect` para o miscount do "copy N files", a cópia de arquivos
  ignorados só na segunda execução e a falta de lock; `task` para o teste via
  ssh e a decisão sobre a tarefa `docs`; `enhancement` para o resto.
- Reescrevi `dev/README.md` em português, conforme o nível de idioma.
- A checagem falha com `LANG=pt_BR.UTF-8` num teste que compara texto do git
  em inglês. Não é desta migração; abri `locale-dependent-test`. Com
  `LC_ALL=C`, `uv run task ci` passa.
- Não criei o link `CLAUDE.md` -> `AGENTS.md` do layout; fica fora do escopo
  desta issue.
