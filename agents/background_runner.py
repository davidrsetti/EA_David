"""
agents/background_runner.py — Autonomous scheduled agents for NEXUS.

Uses APScheduler to run background tasks on a schedule.
Wired into FastAPI lifespan so it starts/stops with the server.

Scheduled jobs:
  nightly_portfolio_health_scan   @ 02:00 UTC daily
  weekly_capability_gap_report    @ 06:00 UTC Monday
  weekly_change_impact_watchlist  @ 06:30 UTC Monday
  daily_ai_governance_check       @ 03:00 UTC daily
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _write_finding(label: str, severity: str, asset_uri: str, description: str) -> None:
    """Write a finding to the graph, swallowing errors (background task)."""
    try:
        from nexus.agents.findings import Finding, assert_finding
        finding = Finding(
            agent_id    = "background-runner",
            label       = label,
            severity    = severity,
            asset_uri   = asset_uri,
            description = description,
        )
        uri = assert_finding(finding)
        logger.info("Background finding asserted: %s", uri)
    except Exception as exc:
        logger.warning("Background finding write failed: %s", exc)


# ── Scheduled jobs ──────────────────────────────────────────────────────

def nightly_portfolio_health_scan() -> None:
    """Identify newly Eliminate-class apps and create findings."""
    logger.info("Background: nightly_portfolio_health_scan starting")
    try:
        from nexus.core.apm_agent import run_apm_agent
        from nexus.core.stardog_client import get_stardog

        result = run_apm_agent(focus_domain="", user_role="admin")
        eliminate = [s for s in result.app_scores if s.time_class.value == "ELIMINATE"]

        for app in eliminate[:10]:
            if app.portfolio_score < 20:
                _write_finding(
                    label       = f"Eliminate candidate: {app.app_label}",
                    severity    = "High",
                    asset_uri   = f"https://ontology.ea.example.org/app#{app.app_label.replace(' ', '_')}",
                    description = (
                        f"{app.app_label} scored {app.portfolio_score:.0f}/100 in the portfolio. "
                        f"Business value: {app.business_value:.1f}, Technical fit: {app.technical_fit:.1f}, "
                        f"Risk: {app.risk_score:.1f}. Recommend formal decommission review."
                    ),
                )
        logger.info("nightly_portfolio_health_scan: %d Eliminate apps checked", len(eliminate))
    except Exception as exc:
        logger.error("nightly_portfolio_health_scan failed: %s", exc)


def weekly_capability_gap_report() -> None:
    """Detect capabilities with no supporting application and create findings."""
    logger.info("Background: weekly_capability_gap_report starting")
    try:
        from nexus.core.stardog_client import get_stardog
        db   = get_stardog()
        q    = """
        SELECT ?cap ?capLabel WHERE {
            ?cap a ea:BusinessCapabilityL3 .
            OPTIONAL { ?cap rdfs:label ?capLabel }
            FILTER NOT EXISTS { ?app ea:enablesBusinessCapability ?cap }
        } LIMIT 20
        """
        _, rows = db.to_rows(db.query(q, inject_prefixes=True))
        for row in rows:
            uri   = row.get("cap", "")
            label = row.get("capLabel", uri)
            if not uri:
                continue
            _write_finding(
                label       = f"Capability gap: {label}",
                severity    = "Medium",
                asset_uri   = uri,
                description = (
                    f"Business capability '{label}' has no supporting application in the portfolio. "
                    f"This represents a functional gap that may impact business operations. "
                    f"Review whether this capability should be supported by an existing or new application."
                ),
            )
        logger.info("weekly_capability_gap_report: %d gaps found", len(rows))
    except Exception as exc:
        logger.error("weekly_capability_gap_report failed: %s", exc)


def weekly_change_impact_watchlist() -> None:
    """Flag sunset/legacy apps with active dependencies."""
    logger.info("Background: weekly_change_impact_watchlist starting")
    try:
        from nexus.core.stardog_client import get_stardog
        db = get_stardog()
        q  = """
        SELECT ?app ?appLabel ?lifecycle WHERE {
            ?app a app:Application ;
                 app:lifecycle ?lifecycle .
            FILTER(?lifecycle IN ("sunset","legacy","eol","retire"))
            FILTER EXISTS { ?other app:dependsOn ?app }
            OPTIONAL { ?app rdfs:label ?appLabel }
        } LIMIT 15
        """
        _, rows = db.to_rows(db.query(q, inject_prefixes=True))
        for row in rows:
            uri   = row.get("app", "")
            label = row.get("appLabel", uri)
            lc    = row.get("lifecycle", "?")
            if not uri:
                continue
            _write_finding(
                label       = f"Risky dependency: {label} is {lc}",
                severity    = "High",
                asset_uri   = uri,
                description = (
                    f"Application '{label}' has lifecycle status '{lc}' but still has active dependencies. "
                    f"This creates delivery risk. Recommend proactive migration planning for dependent systems."
                ),
            )
        logger.info("weekly_change_impact_watchlist: %d at-risk apps found", len(rows))
    except Exception as exc:
        logger.error("weekly_change_impact_watchlist failed: %s", exc)


def daily_ai_governance_check() -> None:
    """Flag AI agents without riskTier or past their review date."""
    logger.info("Background: daily_ai_governance_check starting")
    try:
        from nexus.core.stardog_client import get_stardog
        db  = get_stardog()
        now = datetime.now(timezone.utc).isoformat()

        unrated_q = """
        SELECT ?agent ?agentLabel WHERE {
            ?agent a ai:Agent .
            OPTIONAL { ?agent rdfs:label ?agentLabel }
            FILTER NOT EXISTS { ?agent ai:riskTier ?t }
        } LIMIT 10
        """
        _, unrated = db.to_rows(db.query(unrated_q, inject_prefixes=True))
        for row in unrated:
            uri   = row.get("agent", "")
            label = row.get("agentLabel", uri)
            if not uri:
                continue
            _write_finding(
                label       = f"Unrated AI agent: {label}",
                severity    = "Medium",
                asset_uri   = uri,
                description = (
                    f"AI agent '{label}' has no risk tier assigned. "
                    f"All agents must have a risk classification (Low/Medium/High/Critical) "
                    f"per the AI Governance Policy."
                ),
            )

        overdue_q = f"""
        SELECT ?agent ?agentLabel ?reviewDue WHERE {{
            ?agent a ai:Agent ;
                   ai:reviewDue ?reviewDue .
            OPTIONAL {{ ?agent rdfs:label ?agentLabel }}
            FILTER(STR(?reviewDue) < "{now[:10]}")
        }} LIMIT 10
        """
        _, overdue = db.to_rows(db.query(overdue_q, inject_prefixes=True))
        for row in overdue:
            uri   = row.get("agent", "")
            label = row.get("agentLabel", uri)
            due   = row.get("reviewDue", "?")
            if not uri:
                continue
            _write_finding(
                label       = f"Overdue AI review: {label}",
                severity    = "High",
                asset_uri   = uri,
                description = (
                    f"AI agent '{label}' had a governance review due on {due} and has not been reviewed. "
                    f"Schedule an immediate review per the AI Governance Policy."
                ),
            )

        logger.info(
            "daily_ai_governance_check: %d unrated, %d overdue",
            len(unrated), len(overdue),
        )
    except Exception as exc:
        logger.error("daily_ai_governance_check failed: %s", exc)


# ── Scheduler setup ─────────────────────────────────────────────────────

def start_scheduler():
    """Start the APScheduler. Called from FastAPI lifespan."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(nightly_portfolio_health_scan,  "cron", hour=2,  minute=0,  id="portfolio_scan")
        scheduler.add_job(weekly_capability_gap_report,   "cron", day_of_week="mon", hour=6,  minute=0,  id="cap_gap")
        scheduler.add_job(weekly_change_impact_watchlist, "cron", day_of_week="mon", hour=6,  minute=30, id="watchlist")
        scheduler.add_job(daily_ai_governance_check,      "cron", hour=3,  minute=0,  id="ai_gov")
        scheduler.start()
        logger.info("NEXUS background scheduler started (4 jobs)")
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed — background jobs disabled. pip install apscheduler")
        return None
    except Exception as exc:
        logger.error("Scheduler start failed: %s", exc)
        return None
