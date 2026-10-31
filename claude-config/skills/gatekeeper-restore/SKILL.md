---
name: gatekeeper-restore
description: List the Gatekeeper ledger backups in data/backups/ and restore one, for example to undo a reset or return to an earlier state. Use when the person says "gatekeeper-restore", "/gatekeeper-restore", "restore a backup", "go back to the earlier ledger", "undo the demo reset" or "list my backups".
---

# gatekeeper-restore

Replaces the current ledger with one of the backups in `data/backups/`. Backups are made before any reset and by hand. The restore saves the current ledger first, so it can be undone with this same skill.

## 1. List

```
"${CLAUDE_PLUGIN_ROOT}/bin/gk" run restore_backup.py --list
```

Show the list as a short table, newest first: number, saved time, what it holds (company, ideas, runs, decisions), and its label if it has one. Say in one line which one the ledger most likely matches today. Use only what the script prints. A backup with few ideas and runs is usually a demo or a fresh setup; one with many is a working ledger.

If the command says it could not build the Python environment, show the person that message: it needs Python 3.10 or newer, or `uv` (`brew install uv`). Then retry once.

## 2. Choose

Ask which one to restore, by number. Do not choose for them. If they named a time or label ("the one before the reset"), match it to the list and confirm the match in one line before going on.

## 3. Confirm

Before restoring, say in two lines what changes: the current ledger (its ideas, runs and decisions, from `get_pipeline_status`) is replaced by the chosen one, and the current one is saved first as `…-before-restore.db`. Ask for a clear yes. Never restore without it.

## 4. Restore

```
"${CLAUDE_PLUGIN_ROOT}/bin/gk" run restore_backup.py --restore <file name> --yes
```

Add `--yes` only after the yes in chat. The script refuses while a run is in progress, and refuses a backup that fails the integrity check or is not in `data/backups/`. If it refuses, say why in one line and stop.

## 5. Show the result

Use the connector: `get_pipeline_status` (counts) and `get_setup_status`. One line each. Then say:

- The web app and the connector pick up the restored ledger without a restart. Reload the page.
- The file saved before the restore, by name, so they can come back.

Do not start a run or the interview yourself.
