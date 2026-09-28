# Development notes

Working documents for maintainers and coding agents. Not part of the user
documentation.

- `specs/`: one file per non-trivial feature, written and agreed on before
  implementation. Delete the file once the feature ships; the changelog keeps
  the summary.
- `issues/`: bugs that need investigation. Small bugs go to `BACKLOG.md`
  instead. Delete the file once the fix is merged.

Each file starts with MOP frontmatter (`type`, `status`, `tags`, `relatedTo`).
Use `dev/specs/TEMPLATE.md` as a starting point.
