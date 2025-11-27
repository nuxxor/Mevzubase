#!/usr/bin/env bash

# Load the normal bashrc so aliases, PATH, etc. remain.
if [ -f ~/.bashrc ]; then
  source ~/.bashrc
fi

VENV_PATH="${WORKSPACE_FOLDER:-${workspaceFolder:-$(pwd)}}/base"
if [ -f "$VENV_PATH/bin/activate" ]; then
  # Standard activation; preserves prompt change.
  source "$VENV_PATH/bin/activate"
else
  # Fallback: set env and hint in prompt.
  export VIRTUAL_ENV="$VENV_PATH"
  export PATH="$VENV_PATH/bin:$PATH"
  PS1="(base) ${PS1-\\u@\\h:\\w\\$ }"
fi
