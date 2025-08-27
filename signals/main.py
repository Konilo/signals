import os

import typer
from utils.utils import load_and_register_commands

app = typer.Typer()
load_and_register_commands(
    app,
    os.path.join(
        os.path.dirname(__file__),
        "probes",
    ),
)


@app.callback()
def dummy_to_force_subcommand() -> None:
    """
    This function exists because Typer won't let you force a single subcommand.
    Since we know we will add other subcommands in the future and don't want to
    break the interface, we have to use this workaround.

    Delete this when a second subcommand is added.

    https://github.com/fastapi/typer/issues/315#issuecomment-1142593959
    """
    pass


if __name__ == "__main__":
    app()
