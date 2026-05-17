# NEXUS Executive Demo Script — 30 Minutes

**Audience:** Executive Board, CTO, CDTO, Chief Architect  
**Goal:** Show that NEXUS gives instant, accurate, AI-powered answers about the enterprise architecture — and that GiGi can access it too.

---

## Pre-Demo Setup (10 min before)

```bash
# 1. Start API
cd /Users/drs58706/david/EA_David/EA_David
python -m uvicorn nexus.api.main:app --reload --port 8000

# 2. Start UI
python -m streamlit run nexus/ui/app.py --server.port 8501

# 3. Validate graph data
python demo/validate_demo_data.py

# 4. Open browser: http://localhost:8501
# 5. Connect to StarDog (credentials in .env)
# 6. Toggle DEMO MODE ON in the sidebar
# 7. Select persona: "Executive Board"
# 8. Zoom browser to 110% for visibility
```

**Checklist:**
- [ ] StarDog connected (green status indicator)
- [ ] Demo Mode toggle is ON
- [ ] Browser zoomed to 110%
- [ ] Second screen ready if presenting via projector
- [ ] validate_demo_data.py returned all OK

---

## Slide (0–2 min) — Context Setting

**Say:**
> "NEXUS is our enterprise knowledge graph — every application, business capability, data asset, and AI agent in the organisation, connected and queryable in real time. What you'll see today is not a dashboard with pre-baked slides. Every answer comes live from the graph."

**Transition:** "Let me show you what that means in practice."

---

## Section 1 — Knowledge Graph Chat (2–10 min)

**Persona: Executive Board**  
Switch Demo Mode persona to "Executive Board". The example questions update.

### Question 1 (2–4 min)

**Type:** `What percentage of our application portfolio is at risk?`

**Wait for answer, then say:**
> "That's a live number — pulled from the portfolio scoring model that runs against our actual application registry. No spreadsheet, no manual survey."

**If answer is thin:** Navigate to the Portfolio tab (Tab 5) — show the TIME quadrant chart. The visual makes it land better.

---

### Question 2 (4–7 min)

**Type:** `Which business capabilities have no technology support?`

**Wait for answer, then say:**
> "These are the blind spots — capabilities the business depends on where we have no supporting application. That gap is now visible without a six-week assessment."

**If no results:** Ask instead: `List capabilities with no supporting application in Finance.` (Scoped query usually returns results.)

---

### Question 3 (7–10 min)

**Type:** `What is our AI governance posture across all agents?`

**Wait for answer, then say:**
> "Every AI agent we operate is tracked here — its risk tier, its last review date, and whether it's overdue. The nightly background agent flags any that fall out of compliance automatically."

**Pivot:** "Let me show you the portfolio view."

---

## Section 2 — Portfolio TIME Analysis (10–15 min)

**Tab:** Portfolio (Tab 5)  
**Persona switch:** CTO

**Say:**
> "This is the Gartner TIME model — Tolerate, Invest, Migrate, Eliminate. Every application in our estate is scored on business value, technical fitness, and risk. The scoring runs automatically against the graph."

**Walk through:**
- Point to the ELIMINATE quadrant: "These are decommission candidates."
- Point to the INVEST quadrant: "These are our strategic platforms — we double down here."
- Click into one ELIMINATE-class app to show the detail view.

**CTO talking point:**
> "The nightly background agent checks for newly ELIMINATE-class apps and creates a finding automatically. No one has to run the analysis — it runs itself."

---

## Section 3 — Change Impact Analysis (15–20 min)

**Tab:** Change Impact (Tab 8)  
**Persona switch:** CDTO

**Say:**
> "Before we retire any application, we need to know the blast radius. Watch this."

**Action:**
1. Type an application name in the search box (e.g., "SAP ERP" or the most interconnected ELIMINATE-class app from the portfolio view)
2. Click "Analyse Impact"
3. Wait for the 6-ring dependency diagram

**Say:**
> "Each ring shows a hop of dependency. Ring 1 is direct dependents. Ring 6 is everything downstream. Every one of those systems needs a migration plan before we can decommission."

**CDTO talking point:**
> "This is what replaces the 3-month impact assessment. We get this in 30 seconds."

**If StarDog query is slow:** Pre-run the analysis and screenshot it. Show the screenshot and say "this is a cached view — we ran it this morning."

---

## Section 4 — Architecture Diagram Generation (20–24 min)

**Tab:** Architecture Diagram (Tab 7)  
**Persona switch:** Chief Architect

**Say:**
> "The SA Advisor generates solution architecture recommendations grounded in the live graph — not generic templates."

**Action:**
1. Type: `Generate a solution architecture for a new customer portal with SSO, API gateway, and mobile app`
2. Click Generate

**Say:**
> "The diagram is ArchiMate-aligned — Business layer, Application layer, Technology layer. And it's grounded in what we actually have — it references existing platforms in the portfolio."

**Chief Architect talking point:**
> "ADRs are queryable too — if we go to the chat and ask for ADRs in the Finance domain, we get the decision history instantly."

---

## Section 5 — AI Governance (24–27 min)

**Tab:** AI Governance (Tab 9)  
**Persona switch:** CDTO / CTO

**Say:**
> "As we scale AI agents across the enterprise, governance is non-negotiable. This tab shows every agent, its risk classification, and whether its review is current."

**Walk through:**
- Unrated agents panel: "These need a risk tier assigned — the background agent flags them every morning."
- Overdue reviews panel: "These have passed their governance review date. The system finds them automatically."

**EU AI Act talking point:**
> "The AI Act requires a risk classification for every system that uses AI in a consequential decision. We have the infrastructure to track this at enterprise scale."

---

## Section 6 — GiGi / MCP Integration (27–30 min)

**If GiGi MCP is live:**

**Say:**
> "The final piece. NEXUS exposes a Model Context Protocol server — which means GiGi, our enterprise ChatBot, can now call NEXUS as a tool. Any employee can ask GiGi an EA question and get a graph-grounded answer."

**Demo:** Open GiGi, ask: `"Which applications support Order-to-Cash?"` — show GiGi calling the nexus_query tool and returning the answer.

**If GiGi MCP is not live:**

**Say:**
> "We've built the MCP server — NEXUS exposes 9 tools that any MCP-compatible system can call. Once we register it with Glean, GiGi gains EA knowledge graph access for every user in the organisation. That's the next milestone."

---

## Q&A Cheat Sheet

| Question | Answer |
|----------|--------|
| "How current is the data?" | "It's pulled live from StarDog. For the portfolio model, scores refresh on each query. Findings are generated nightly." |
| "What if StarDog is down?" | "The UI degrades gracefully — the chat shows an error, but the API and background agents queue their work." |
| "Can it connect to ServiceNow/Jira?" | "That's Phase 4 on the roadmap — ITSM integration via MCP tools. The architecture is in place." |
| "Who maintains the ontology?" | "The EA team. We have 40+ namespaces covering applications, capabilities, data, AI agents, and governance. New classes are added through the KG Population tab." |
| "Is this replacing [existing tool]?" | "NEXUS complements existing tools — it's the connective tissue. It doesn't replace EA tools, it makes them queryable and AI-accessible." |
| "How long to get to production?" | "The core platform is production-ready now. Full GiGi integration is 4–6 weeks." |
| "What's the EU AI Act coverage?" | "Every AI agent has a risk tier, review date, and audit trail. The daily governance check flags any that fall out of compliance." |

---

## Fallback Plan

If StarDog is unavailable during the demo:

1. Open the pre-recorded screen capture (record it the day before).
2. Walk through the recording: "Let me show you a session we recorded against the live graph this morning."
3. Use the Portfolio tab screenshots and the Change Impact diagram screenshot as backup.
4. Run validate_demo_data.py live to show the graph is populated — just can't query during the outage.

---

## Closing (30 min)

**Say:**
> "What you've seen today is a production-grade knowledge graph platform with agentic AI built in. Natural language queries. Proactive findings. Change impact analysis. AI governance tracking. And GiGi integration on the roadmap. The EA team is now operating at a completely different speed."

**Hand over to stakeholder questions.**
