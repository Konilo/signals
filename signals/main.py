import os

import dotenv
import typer
from utils.cli_utils import load_and_register_commands

app = typer.Typer()
load_and_register_commands(
    app,
    os.path.join(
        os.path.dirname(__file__),
        "probes",
    ),
)


# Note: previously a dummy @app.callback() was needed to force Typer to treat
# the app as multi-command when only one subcommand existed.
# It was removed once a second subcommand was added.
# https://github.com/fastapi/typer/issues/315#issuecomment-1142593959


if __name__ == "__main__":
    # Only useful in dev
    dotenv.load_dotenv()

    app()
