#!/usr/bin/env bash
# Make a clean copy of Gatekeeper in another folder and install it there.
#
#   scripts/new-instance.sh DEST                      copy and install (empty ledger)
#   scripts/new-instance.sh DEST --desktop            ... and point Claude Desktop chats at the copy
#
# Copies the code, agents and skills. Never copies the ledger, briefs, context,
# inbox files, .venv or .claude: the copy starts with nothing of this instance's state.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ $# -lt 1 ] || [[ "$1" == -* ]]; then
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi
DEST="$1"; shift

INSTALL_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --desktop) INSTALL_ARGS+=("--desktop") ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "$DEST exists and is not empty. Choose a new folder." >&2
  exit 1
fi
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
case "$DEST/" in "$SRC/"*) echo "DEST cannot be inside this folder." >&2; exit 1 ;; esac

echo "Copying $SRC -> $DEST"
rsync -a \
  --exclude '.git/' --exclude '.venv/' --exclude '.claude/' --exclude '.mcp.json' \
  --exclude '/data/' --exclude '/briefs/*.md' --exclude '/context/*' \
  --include '/inbox/README.md' --exclude '/inbox/*' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  "$SRC/" "$DEST/"
mkdir -p "$DEST/briefs" "$DEST/inbox"

bash "$DEST/scripts/install.sh" ${INSTALL_ARGS[@]+"${INSTALL_ARGS[@]}"}


echo
echo "New instance ready: $DEST"
echo "Open a Code tab session on that folder."
