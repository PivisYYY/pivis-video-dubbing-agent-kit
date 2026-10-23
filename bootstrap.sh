#!/usr/bin/env bash
# Bootstrap an isolated Python 3.11 environment for video-dubbing-agent-kit.
#
# Scope (intentionally narrow):
#   - Apple Silicon macOS (arm64) only; every other platform exits non-zero.
#   - Creates ./.venv with a uv-managed Python 3.11 (uv may fetch CPython
#     3.11 itself if no 3.11 interpreter is present).
#   - Installs this project editable with the 'speech' extra from PyPI.
#
# This script NEVER: installs Homebrew, edits global/agent configuration,
# pipes install scripts from the web (curl|sh), reads credentials, or
# downloads speech models. Model weights are fetched later, only with the
# explicit --accept-download authorization flag (see README.md).
set -euo pipefail

if [[ "${1-}" != "--accept-install" ]]; then
  printf '%s\n' 'This script downloads Python dependencies into .venv.' 'After authorization run: bash bootstrap.sh --accept-install' >&2
  exit 2
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  printf '%s\n' 'FFmpeg/ffprobe are required. Install with your approved package manager; no global changes are made here.' >&2
  exit 2
fi

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "ERROR: unsupported platform: $(uname -s)/$(uname -m)." >&2
  echo "The first release of this kit targets Apple Silicon macOS (arm64) only." >&2
  echo "Do not install MLX on other platforms; see docs/SUPPORT.md." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 'uv' is required but was not found on PATH." >&2
  echo "Install uv by following the official documentation (do not guess or pipe commands):" >&2
  echo "  https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Creating isolated .venv with uv-managed Python 3.11"
echo "    (note: uv may download CPython 3.11 itself if no 3.11 interpreter is available)"
if [[ ! -x .venv/bin/python ]]; then
  uv venv --python 3.11 .venv
fi

echo "==> Installing this project in editable mode with the 'speech' extra"
uv pip install --python .venv/bin/python --constraint requirements-macos-arm64.lock.txt -e '.[speech]'

echo "==> Smoke check (imports only, no model downloads)"
.venv/bin/python - <<'PY'
import dubkit
from dubkit import models

registry = models.load_registry()
print(f"dubkit {dubkit.__version__} | pinned models: {', '.join(sorted(registry))}")
PY

cat <<'EOF'

Bootstrap complete. Nothing was downloaded beyond the Python toolchain and
PyPI packages. Next steps, each gated on your explicit authorization:

  .venv/bin/python -m dubkit doctor            # read-only environment report
  .venv/bin/python -m dubkit models list       # read-only cache status
  .venv/bin/python -m dubkit models fetch --accept-download   # model downloads

See README.md for the full workflow and AGENTS.md for agent operating rules.
EOF
