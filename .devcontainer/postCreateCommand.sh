#! /bin/bash

# https://stackoverflow.com/a/19622569
trap 'exit' ERR

echo 'Running postCreateCommand.sh'

# Installing the deps (Python and libs) w/ uv
echo 'Running uv sync'
uv sync

# The named volume mounted at ~/.claude is created by Docker as root-owned.
# Fix ownership so the vscode user can write into it before installing Claude Code.
sudo chown -R vscode:vscode /home/vscode/.claude

# Install Claude Code CLI
echo 'Installing Claude Code CLI'
curl -fsSL https://claude.ai/install.sh | bash
