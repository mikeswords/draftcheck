#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v uv >/dev/null; then
  printf '%s\n' 'Draftcheck needs uv. Install it, then open this launcher again.'
  exit 1
fi

if curl --silent --fail --max-time 1 http://127.0.0.1:8765/api/status | grep -q '"model_ready"'; then
  exec open http://127.0.0.1:8765/
fi

uv run --locked --python 3.12 python -m draftcheck setup
exec uv run --locked python -m draftcheck serve --open
