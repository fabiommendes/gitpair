"""Keep git repositories in sync between two machines over ssh."""

__version__ = "0.1.0"


def main() -> None:
    import sys

    from gitpair.cli import main as run

    sys.exit(run())
