---
name: gatekeeper-dashboard
description: Start, stop or check the Gatekeeper dashboard (the local web app service) from chat, so the person never manages the process in a terminal. Use when the person says "gatekeeper-dashboard", "/gatekeeper-dashboard", "/gatekeeper-dashboard stop", "start the dashboard", "stop the dashboard", "open the web app" or "is the dashboard running".
---

# gatekeeper-dashboard

Runs the Gatekeeper web app service in the background and stops it again. All the work is in `bin/gk dashboard`; this skill only picks the action and reports it.

## Pick the action

Read the argument after the skill name:

| Said | Run |
|---|---|
| nothing, `start`, "start / open the dashboard" | `"${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard start` |
| `stop`, "stop / shut down the dashboard" | `"${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard stop` |
| `status`, "is it running" | `"${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard status` |
| `open`, "give me a new sign-in link" | `"${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard open` |

If the argument is anything else, say which four are available and stop.

`start` is safe to repeat: if the service is already running it says so and prints a fresh sign-in link. The first start after a web change rebuilds the web app, which can take a minute; run it with a long timeout.

## Start

Run the command, then show the result as an interactive widget, not as plain text. The person must click the sign-in link first, and a text reply buries that.

Load the widget tools once per session: `mcp__visualize__read_me` (module `interactive`), then `mcp__visualize__show_widget`. Do not mention this setup. Build the widget from the script's output:

- Two numbered steps in a single card, step 1 filled and prominent, step 2 muted until step 1 is done.
- Step 1, "Sign in first": one large primary button labelled "Sign in to Gatekeeper before {time}", an `<a href>` to the sign-in link from the script. `{time}` is the script's `Expires:` line, copied as printed (for example "3:42 PM"); never work it out yourself. Under it, one small line: "Works once."
- Step 2, "Then use the dashboard": the plain address `http://127.0.0.1:8787` as a link. A small JS toggle may grey it out until the sign-in button is clicked; it must stay clickable.
- A one-line footer naming the ledger ("Live ledger: decisions you make are real", or "Dev copy of the ledger" for `LEDGER=dev`) and "Stop it with /gatekeeper-dashboard stop".
- If the script said "Already running", say so in the card title; the sign-in link is still fresh.
- Use only CSS variables for colour so it works in dark mode. No emoji.

Clicking a plain link in the widget does nothing for local `http://127.0.0.1` addresses in this app (right-click, "Open link in browser" does work). So keep the `href` on both links, so right-click works, but make the click do this instead: `e.preventDefault(); sendPrompt('Open the Gatekeeper sign-in link in my browser')` for the sign-in button, and `sendPrompt('Open the Gatekeeper dashboard in my browser')` for the address. Do not call `openLink`. Under the button add a small muted line: "Or right-click, then Open link in browser." Also put the sign-in link as a normal markdown link in your text under the widget, as `[Sign in to Gatekeeper before {time}](url)`.

When that prompt comes back, run `open "<url>"` in Bash (macOS opens it in their default browser). For the sign-in button use the link from this card if its `Expires:` time has not passed, otherwise run `"${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard open` for a fresh one and say so in a line. Keep the text around the widget otherwise to one line. Skip the widget and put the same two steps in plain text, sign-in link first and bold, only if the widget tools are not available.

If they are already signed in (the browser stays signed in for 30 days), they only need step 2.

Offer to open the link in the built-in browser only if they ask to see it.

Do not run `service/dev.sh`: it holds the terminal in the foreground.

## Stop

Run the command and say what it printed. Stopping the dashboard does not touch the ledger or the Claude connector; the Gatekeeper connector is a separate process and keeps working.

## If it fails

Show the script's message in one line and the last lines of `.gatekeeper/dashboard.log` if it points there. Common causes:

- `Could not build the Python environment`: show the message; it needs Python 3.10 or newer, or `uv` (`brew install uv`).
- Port in use by something else: the script leaves other programs alone. Offer `PORT=<other> "${CLAUDE_PLUGIN_ROOT}/bin/gk" dashboard start`.
- Web build failed: show the build error from the output; do not edit the web app to fix it unless asked.

Do not edit anything in `data/` or `context/`.
