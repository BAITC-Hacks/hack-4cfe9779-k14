"""EKT consultant; importing this package does not read secrets or call APIs."""


def main() -> None:
    from .cli import main as run

    run()
