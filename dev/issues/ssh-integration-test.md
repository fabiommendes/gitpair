---
type: issue
status: backlog
tags: [tests, ssh]
kind: task
created: 2026-10-14
---

# Teste de integração opcional contra `ssh localhost`

`RemoteHost` só tem testes unitários. Adicione um teste de integração opcional
que rode contra `ssh localhost` quando `GITPAIR_SSH_TEST=1` estiver definido.

Da revisão de 2026-09-28 (item T4): teste de integração opcional contra `ssh
localhost`, atrás de uma variável de ambiente, para que `run_binary`, as URLs
`host:/path` e a cópia da configuração passem pelo caminho ssh real, em
condições parecidas com as do CI.

Origem: `BACKLOG.md`, seções "Testes" e "Da revisão de 2026-09-28" (os dois
itens pediam o mesmo teste).
