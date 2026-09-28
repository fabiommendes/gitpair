# Security policy

gitpair runs git and shell commands on your machines over ssh, so bugs can have
security impact. Examples: a repository path or branch name that escapes shell
quoting, a config value that runs unintended commands on the remote, or an
action that discards commits without asking.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's private vulnerability reporting:
**Security > Report a vulnerability** on the repository page.

Include the gitpair version, what an attacker controls (a repository name, the
config file, the remote host) and the steps to reproduce. You should get a
reply within a week.

## Supported versions

Only the latest release receives fixes.

## Trust model

gitpair assumes that both hosts and the shared config file are trusted: anyone
who can edit the config can already choose which host you ssh into. Repository
contents, directory names and branch names are not trusted and must never be
interpreted as commands.
