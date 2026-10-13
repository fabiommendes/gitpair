---
type: plan
status: active
tags: [gitpair, backlog, known-limitations]
relatedTo: [gitpair]
---

# Backlog

Trabalho sem data e limitações conhecidas. Os itens são agrupados por assunto, não por prioridade. Mova os itens para [ROADMAP.md](ROADMAP.md) quando receberem uma versão.

## Limitações conhecidas

* [ ] Só o branch atual é comparado. Os demais branches são ignorados, a menos que o repositório seja clonado.
* [ ] Branches diferentes em cada máquina são informados e pulados. Poderia oferecer o checkout do mesmo branch em um dos lados.
* [ ] Quando a configuração remota é diferente da local, o gitpair se recusa a sobrescrevê-la e pede ao usuário que a copie à mão. Um merge de três vias das listas `repos` eliminaria a maioria desses casos.
* [ ] Mais de duas máquinas são suportadas apenas em pares (`--remote`). Não existe modo "sincronizar todas as máquinas".
* [ ] `clone-there` precisa de git 2.28+ na máquina remota (`git init --initial-branch`).

* [ ] Arquivos ignorados: exclusões não são propagadas, e conflitos são decididos só pelo mtime. Um registro por máquina do último manifesto sincronizado permitiria exclusões reais e detecção de conflitos.
* [ ] Os arquivos ignorados de um repositório só são copiados a partir da segunda execução, depois que ele é clonado em uma máquina.
* [ ] `autopush` faz push só a partir da máquina local. Se só a máquina remota tiver credenciais para o origin, ele falha.
* [ ] Não há lock contra duas execuções ao mesmo tempo nas duas máquinas: o push forçado para `refs/gitpair/incoming/<branch>` pode colidir.

## Testes

* [ ] `RemoteHost` só tem testes unitários. Adicione um teste de integração opcional que rode contra `ssh localhost` quando `GITPAIR_SSH_TEST=1` estiver definido.

## UI

* [ ] Mostre a lista de commits (`git log --oneline`) dos commits recebidos no diálogo de pergunta.
* [ ] Mostre os repositórios sincronizados atrás de um alternador.
* [ ] O texto "copy N files" de um passo extra é calculado antes de a política de arquivos ser escolhida. Por isso, com `skip conflicting files`, ele pode contar arquivos que não são copiados. Calcule a descrição a partir de `resolved_files`.

## Da revisão de 2026-09-28

* [ ] Teste de integração opcional contra `ssh localhost`, atrás de uma variável de ambiente, para que `run_binary`, as URLs `host:/path` e a cópia da configuração passem pelo caminho ssh real, em condições parecidas com as do CI (item T4 da revisão).
* [ ] Decida se o projeto precisa de uma tarefa `docs` (doc-zero) ou se o README mais `docs/` bastam (item P5 da revisão).
