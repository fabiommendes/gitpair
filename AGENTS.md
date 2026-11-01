# gitpair

gitpair é uma CLI que mantém sincronizados os repositórios git de duas máquinas, via ssh. Ela analisa as duas máquinas, monta um plan e aplica sozinha os fast-forwards seguros. Para o resto, pergunta ao usuário em uma TUI feita com Textual. O arquivo de configuração é compartilhado pelas duas máquinas; a máquina local é detectada em tempo de execução.

Leia `README.md` para o comportamento visível ao usuário e `docs/how-it-works.md` para os comandos git de cada ação, antes de mudar qualquer coisa em `plan.py` ou `execute.py`.

## Idioma

Nível 2 (aplicativo público), conforme `~/git/tools/tooling-root/dev/adr/0002-idioma-dos-repositorios.md`:

- Em inglês: código, comentários, docstrings, mensagens da CLI e de erro,
  `README.md`, a documentação de usuário em `docs/`, `CHANGELOG.md`,
  `CONTRIBUTING.md`, `GLOSSARY.md` e mensagens de commit.
- Em português (pt-BR): este arquivo, tudo em `dev/`, as ADRs e as issues.

## Comandos

Checagem: `r2 check`, que roda `uv run task ci` (declarado em `r2.toml`). Ela define "pronto": a tarefa não termina enquanto ela falhar. O CI roda o mesmo comando. Até fechar `dev/issues/locale-dependent-test.md`, rode com `LC_ALL=C` numa máquina em outro idioma.

| Comando                 | Ação                                    |
| :---------------------- | :-------------------------------------- |
| `uv sync`               | Instala as dependências.                |
| `uv run task test`      | Roda os testes.                         |
| `uv run task format`    | Formata e corrige automaticamente com ruff. |
| `uv run task lint`      | Verificação de formatação com ruff, lint com ruff e mypy. |
| `uv run task ci`        | Lint e testes, como o CI roda.          |
| `uv run gitpair plan`   | Testa a CLI com a sua própria configuração. |

A suíte de testes não cobre ssh real. Ao mudar `hosts.py` ou as URLs do git, teste contra uma segunda máquina real ou peça ao humano para fazer isso.

## Trabalhando com o humano

- Seja direto e breve. Prefira marcadores a parágrafos. Coloque um identificador (`D1`, `D2`) no início de cada marcador ao listar decisões, para facilitar a resposta.
- Mostre no máximo três decisões em aberto por vez.
- Decida sozinho as coisas pequenas e reversíveis e diga a decisão em uma linha. Pergunte só quando a escolha for difícil de desfazer: mudança no formato da configuração, novas refs gravadas nos repositórios dos usuários, ou qualquer coisa que possa perder commits ou trabalho.
- Não elogie ideias. Aponte problemas.

## Estilo de escrita

O texto voltado ao usuário (README, docs, mensagens da CLI, docstrings) fica em inglês, em linguagem simples. Sem palavras de marketing, sem emojis e sem travessões. Diga o que a ferramenta faz, não o quanto ela é boa.

## Estrutura do projeto

| Caminho                      | Descrição                                                                 |
| :--------------------------- | :------------------------------------------------------------------------ |
| `README.md`                  | Documentação do usuário e início rápido.                                  |
| `docs/`                      | Documentação de usuário mais longa: configuração e funcionamento interno. |
| `examples/config.toml`       | Exemplo completo de configuração. Mantenha-o válido; os testes podem carregá-lo. |
| `CHANGELOG.md`               | Mudanças visíveis ao usuário, no formato Keep a Changelog.                |
| `GLOSSARY.md`                | Vocabulário do projeto. Use esses termos no código e nos docs.            |
| `dev/issues/`                | Todo o trabalho: bugs, funcionalidades (com a spec no corpo), tarefas e o backlog. Veja `dev/README.md`. |
| `src/gitpair/config.py`      | Carrega e atualiza a configuração TOML compartilhada; detecta a máquina local e a remota. |
| `src/gitpair/scanner.py`     | Encontra repositórios e informa o estado de cada um. Roda nas duas máquinas. |
| `src/gitpair/hosts.py`       | `Host` executa comandos localmente; `RemoteHost` os envolve em ssh.       |
| `src/gitpair/plan.py`        | API pública do plan: `build`, `describe`, os enums e as dataclasses.      |
| `src/gitpair/_model.py`      | Privado. `Action`, `Item`, `Plan`, `RepoState`, `Extra`, `Step`.          |
| `src/gitpair/_facts.py`      | Privado. Reúne os fatos do plan: toda a I/O com as máquinas, sem decisões. |
| `src/gitpair/_decide.py`     | Privado. Transforma fatos em `Item`s: puro, sem acesso às máquinas.       |
| `src/gitpair/execute.py`     | Comandos git para cada `Action`.                                          |
| `src/gitpair/session.py`     | Uma execução: conecta, aplica o plan, salva as decisões de track e ignore. |
| `src/gitpair/tui.py`         | App Textual para revisar o plan e responder perguntas.                    |
| `src/gitpair/cli.py`         | Ponto de entrada argparse e saída Rich.                                   |
| `tests/conftest.py`          | Fixture `World`: duas máquinas falsas em um diretório temporário, sem ssh. |

## Regras fáceis de quebrar

- `scanner.py` é enviado para `python3 -` na máquina remota. Use só a biblioteca padrão. Ele deve rodar no Python 3.7 e não importar nada de `gitpair` (ADR 0001).
- Todo comando que chega à máquina remota passa por `Host.run`, que escapa os argumentos com `shlex.join`. Nunca monte uma string de shell com nomes de repositórios, de branches ou caminhos. `Host.shell` só serve para scripts fixos montados a partir de valores da configuração, e esses valores também devem ser escapados.
- A máquina remota nunca se conecta de volta à local. Para levar commits ao remoto, faça push para `refs/gitpair/incoming/<branch>` e depois um fast-forward no remoto (ADR 0002).
- Nenhuma ação pode perder commits ou trabalho não commitado, a menos que o usuário a tenha escolhido na UI. Isso vale também para arquivos ignorados: um arquivo em conflito (presente nas duas máquinas com mtime diferente) nunca é copiado sem uma escolha explícita de `files_policy` (ADR 0004). Do mesmo modo, uma branch divergente nunca é resetada sem uma `Action` explícita. Ações destrutivas salvam o HEAD antigo em `refs/gitpair/backup/`. `--auto` só executa ações que `plan.py` marcou como automáticas e trata uma `files_policy` não decidida como `SKIP_CONFLICTS`.
- Repositórios fora de `repos.track` sempre precisam de uma decisão, mesmo quando a sincronização seria automática (ADR 0005).
- Arquivos ignorados são copiados com `tar` via ssh, nunca com rsync, que não está instalado em todo lugar (ADR 0003). Arquivos vindos da máquina remota são extraídos com o filtro `data` do `tarfile`; não o remova.
- Comandos que falam com `origin` rodam com `origin_env` e `ORIGIN_TIMEOUT` (`_facts.py`, ADR 0008): sem prompts, mensagens em inglês, tempo limitado. Nunca faça force-push para o origin.
- Rich e Textual interpretam `[...]` como markup. Escape todo texto vindo do git ou do sistema de arquivos (`rich.markup.escape`).

## Fluxo de trabalho

1. Todo trabalho parte de uma issue em `dev/issues/`. Ao pegá-la, mude o status para `in_progress` e acrescente uma seção `## Plano` com checkboxes; marque cada item no commit que o fecha. Em funcionalidades não triviais, a spec vai no corpo da issue e é combinada com o humano antes do código.
2. Escreva testes que exercitam repositórios git reais por meio da fixture `World`. Verifique o estado do repositório (HEAD, arquivos, refs), não as chamadas internas. Mocks só são aceitáveis na fronteira do ssh.
3. Implemente.
4. Rode `uv run task format` e depois a checagem, `uv run task ci`.
5. Adicione uma entrada em `CHANGELOG.md`, sob `Unreleased`, para mudanças visíveis ao usuário. Atualize `README.md` ou `docs/` se o comportamento mudou.
6. Feche a issue com `status: completed` e `closed: YYYY-MM-DD`. Não a apague. Cite-a nos commits com o trailer `Refs: dev/issues/<slug>.md`.

Se você encontrar um bug fora da tarefa atual, crie uma issue em `dev/issues/` com `status: backlog`. Não o corrija em silêncio.

## Ordens permanentes

Manutenções que um agente faz sem issue aprovada, desde que a checagem passe:

- Atualizar dependências em `uv.lock` dentro das faixas do `pyproject.toml`.
- Corrigir avisos do ruff e do mypy sem mudar comportamento.
- Consertar um teste instável sem enfraquecer o que ele verifica.
- Corrigir links quebrados e erros de digitação na documentação.
