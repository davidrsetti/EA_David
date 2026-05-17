# NEXUS Demo Setup Guide

One-page setup guide for running the executive demo. Complete these steps at least 2 hours before the session.

---

## 1. Start the Services

```bash
cd /Users/drs58706/david/EA_David/EA_David

# Terminal 1 — API
python -m uvicorn nexus.api.main:app --reload --port 8000

# Terminal 2 — UI
python -m streamlit run nexus/ui/app.py --server.port 8501
```

Open `http://localhost:8501` in a browser.

---

## 2. Validate Graph Data

Run the pre-flight check to confirm the graph has sufficient data for all 4 personas:

```bash
python demo/validate_demo_data.py
```

All checks must show `OK`. If any show `FAIL`, load more data into StarDog before the demo.

---

## 3. Connect in the UI

In the sidebar:
1. Enter your StarDog endpoint, token, and database name (from `.env`)
2. Enter your OpenAI API key
3. Click **Connect** — the status indicator should turn green

---

## 4. Enable Demo Mode

In the sidebar, scroll to the **Demo** section:
1. Toggle **Demo Mode** ON
2. Select the starting persona: **Executive Board**

This hides the SPARQL panel, results table, and query plan — and loads persona-specific example questions into the chat tab.

---

## 5. Switch Personas During Demo

Change the **Persona** dropdown in the sidebar to switch the example questions:

| Persona | When to use |
|---------|-------------|
| Executive Board | Opening 3 questions (risk, governance) |
| CTO | Portfolio TIME section |
| CDTO | Change Impact, capability gaps |
| Chief Architect | SA Advisor, ADRs, diagram generation |

---

## 6. (Optional) Register GiGi MCP

To demo GiGi integration, add the NEXUS MCP server to Glean's MCP registry:

```json
{
  "mcpServers": {
    "nexus-kg": {
      "command": "python",
      "args": ["-m", "nexus.mcp_server"],
      "env": {
        "NEXUS_API_URL": "http://localhost:8000",
        "NEXUS_TOKEN": ""
      }
    }
  }
}
```

Test the MCP server locally first:
```bash
python -m nexus.mcp_server
```

Expected output: 9 tools registered (`nexus_query`, `nexus_impact_analyze`, ...).

---

## 7. Demo Flow Reference

See `demo/exec_demo_script.md` for the full 30-minute narrative.

See `demo/questions_by_persona.json` for per-persona questions, expected themes, and fallbacks.

---

## 8. Troubleshooting

| Issue | Fix |
|-------|-----|
| StarDog connection refused | Check `STARDOG_ENDPOINT` in `.env`; confirm StarDog is running |
| OpenAI API error | Check `OPENAI_API_KEY` in `.env`; confirm quota |
| Slow queries | Pre-run the Change Impact analysis before the demo; results cache in the session |
| Empty answers | Run `validate_demo_data.py` — graph may not have enough data |
| Anthropic API not working | Check `ANTHROPIC_API_KEY` in `.env`; demo falls back to OpenAI automatically |
