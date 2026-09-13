---
name: setup
description: One-time setup for the AIHawk browser server - downloads the patched Firefox it drives. Use when a browser tool reports that the engine is missing, or right after installing the plugin.
---

The server runs with `uvx aihawk` and needs its browser engine on this machine once. Run the block for the user's system, then the browser tools work.

Windows, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
uvx invisible-playwright fetch
```

Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uvx invisible-playwright fetch
```

Nothing else to configure: no account, no key. Over MCP the model is the client's own.
