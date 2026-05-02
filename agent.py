import sys
from agent.tui import BbagentApp


def main() -> None:
    app = BbagentApp()
    if len(sys.argv) > 1:
        app.initial_task = " ".join(sys.argv[1:])
    app.run()


if __name__ == "__main__":
    main()
