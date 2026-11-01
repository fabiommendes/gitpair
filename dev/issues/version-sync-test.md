---
type: issue
status: backlog
tags: [tests, release]
kind: task
created: 2026-11-01
creator: claude
---

# Teste que garante a mesma versão em `pyproject.toml` e `__init__.py`

O `CONTRIBUTING.md` manda subir a versão em dois lugares a cada release:
`version` no `pyproject.toml` e `__version__` em `src/gitpair/__init__.py`.
Nada verifica que os dois batem.

Opções:

- um teste que lê o `pyproject.toml` com `tomllib` e compara com `__version__`;
- ou tirar a duplicação: `__version__ = importlib.metadata.version("gitpair")`.

A segunda elimina o passo manual; a primeira não muda o pacote.

Origem: fase de `AGENTS.md` do bootstrap do r2.
