---
type: plan
status: active
tags: [gitpair, roadmap, releases]
relatedTo: [gitpair]
---

# Roadmap

Near-term releases. Once a release ships, move its items to the changelog and
delete them here. Unscheduled ideas live in [BACKLOG.md](BACKLOG.md).

## 0.1.0: first public release

- [x] Scan both hosts, build the plan, apply fast-forwards and clones.
- [x] Terminal UI for questions; `plan` and `sync --auto` for scripts.
- [x] Shared config with track/ignore decisions written back.
- [ ] Test against two real machines over ssh (desktop and laptop).
- [ ] Publish to PyPI through the release workflow.

## 0.2.0: less friction

- [ ] Sync every local branch that exists on both hosts, not only the checked
      out one.
- [ ] Offer "stash, fast-forward, pop" for dirty work trees.
- [ ] Fetch repositories in parallel during planning.
