---
type: issue
status: backlog
tags: [tests, locale]
kind: defect
created: 2026-10-14
---

# Teste de `_decide` falha com git em outro idioma

`tests/test_decide.py::test_head_deleted_after_creation_is_a_git_error_not_an_empty_repo`
compara a mensagem do git com o texto em inglês `not a git repository`. Com
`LANG=pt_BR.UTF-8`, o git responde `não é um repositório git` e o teste falha.
Com `LC_ALL=C`, a suíte passa (176 testes).

O código só repassa a mensagem do git ao usuário, então o defeito é do teste.
Opções: rodar a fixture `World` com `LC_ALL=C` ou deixar de comparar o texto
do git.

Encontrado ao migrar o layout (`dev/issues/adr-0003-layout.md`).
