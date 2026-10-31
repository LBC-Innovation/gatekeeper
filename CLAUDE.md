# Gatekeeper

An innovation pipeline: scouts find signals, a panel deliberates, you decide.

- The ledger lives behind the `gatekeeper` MCP connector (`server/`). Never edit `data/` or `context/` by hand.
- Skills: `gatekeeper-setup` (the interview), `gatekeeper-run` (one pipeline pass), `gatekeeper-review` (board, decisions, settings in chat), `gatekeeper-digest` (weekly reply-to-decide email for the digest test, `docs/web-app-review/04-digest-test-plan.md`).
- Agents: `.claude/agents/gatekeeper-*.md`, one job each. The source copies live in `claude-config/`; `scripts/install.sh` installs them.
- If the connector's tools are missing, run `scripts/install.sh` and restart.
- Decisions belong to the person. Never record one they did not make.
