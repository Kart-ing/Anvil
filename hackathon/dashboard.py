#!/usr/bin/env python3
"""Anvil Enterprise - Dashboard.

Real-time monitoring dashboard for AI agent tools.
Shows tool health, repair history, and audit logs.

Run with: streamlit run dashboard.py
"""

import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="Anvil Enterprise",
    page_icon="🔧",
    layout="wide",
)

MANIFEST_FILE = Path("anvil_manifest.json")
LOG_FILE = Path("repair_log.json")


def load_manifest() -> dict | None:
    """Load the manifest file."""
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text())
    return None


def load_logs() -> list:
    """Load repair logs."""
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []


def status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "healthy": "green",
        "broken": "red",
        "repairing": "orange",
        "pending": "gray",
    }
    return colors.get(status, "gray")


def status_emoji(status: str) -> str:
    """Get emoji for status."""
    emojis = {
        "healthy": "🟢",
        "broken": "🔴",
        "repairing": "🟡",
        "pending": "⚪",
    }
    return emojis.get(status, "⚪")


def main():
    # Header
    st.title("🔧 Anvil Enterprise")
    st.caption("CI/CD Pipeline for AI Agents")

    # Load data
    manifest = load_manifest()
    logs = load_logs()

    if manifest is None:
        st.warning("No manifest found. Run `python ingest.py` first.")
        st.code("cd hackathon && python ingest.py", language="bash")
        return

    # Sidebar - Agent Info
    with st.sidebar:
        st.header("Agent Info")
        st.write(f"**Name:** {manifest['agent']['name']}")
        st.write(f"**Tools:** {manifest['stats']['total']}")

        st.divider()

        st.header("Quick Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Healthy", manifest["stats"].get("healthy", 0), delta=None)
            st.metric("Broken", manifest["stats"].get("broken", 0), delta=None)
        with col2:
            st.metric("Repairing", manifest["stats"].get("repairing", 0), delta=None)
            st.metric("Pending", manifest["stats"].get("pending", 0), delta=None)

        st.divider()

        st.header("Actions")
        if st.button("🔄 Run Pipeline", use_container_width=True):
            st.info("Run `python pipeline.py` in terminal")

        if st.button("📥 Re-ingest Tools", use_container_width=True):
            st.info("Run `python ingest.py` in terminal")

        # Auto-refresh
        st.divider()
        auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)
        if auto_refresh:
            time.sleep(5)
            st.rerun()

    # Main content - Tool Status
    st.header("Tool Health Monitor")

    # Tool cards
    cols = st.columns(3)
    for i, tool in enumerate(manifest["tools"]):
        with cols[i % 3]:
            status = tool.get("status", "pending")
            emoji = status_emoji(status)

            with st.container(border=True):
                st.subheader(f"{emoji} {tool['name']}")
                st.caption(tool.get("description", "No description"))

                st.write(f"**Status:** {status.upper()}")

                if tool.get("last_check"):
                    last_check = datetime.fromisoformat(tool["last_check"])
                    st.write(f"**Last Check:** {last_check.strftime('%H:%M:%S')}")

                if tool.get("error"):
                    with st.expander("View Error"):
                        st.code(tool["error"], language="text")

    # Pipeline visualization
    st.header("Repair Pipeline")

    pipeline_cols = st.columns(4)
    stages = [
        ("🔍", "Detect", "Error caught"),
        ("🔧", "Anvil", "Generate fix"),
        ("🏖️", "Daytona", "Sandbox verify"),
        ("🐰", "CodeRabbit", "Security audit"),
    ]

    for col, (icon, name, desc) in zip(pipeline_cols, stages):
        with col:
            with st.container(border=True):
                st.markdown(f"### {icon} {name}")
                st.caption(desc)

    # Recent activity
    st.header("Repair Log")

    if logs:
        for log in reversed(logs[-10:]):  # Last 10 entries
            timestamp = log.get("timestamp", "Unknown")
            event_type = log.get("type", "unknown")
            tool = log.get("tool", "unknown")

            if event_type == "repair_complete":
                success = log.get("success", False)
                icon = "✅" if success else "⚠️"
                st.write(f"{icon} **{timestamp}** - `{tool}` repair {'completed' if success else 'needs review'}")

                # Show stage details
                with st.expander("Pipeline Details"):
                    stages = log.get("stages", {})
                    for stage_name, stage_data in stages.items():
                        success = stage_data.get("success", stage_data.get("approved", False))
                        st.write(f"- **{stage_name.upper()}:** {'✓ Passed' if success else '⚠ Warning'}")
                        if "review" in stage_data:
                            st.text(stage_data["review"][:200])
            else:
                st.write(f"📝 **{timestamp}** - {event_type}: `{tool}`")
    else:
        st.info("No repair activity yet. Run the pipeline to see logs.")

    # Footer
    st.divider()
    st.caption("Anvil Enterprise - CI/CD for AI Agents | Powered by Daytona & CodeRabbit")


if __name__ == "__main__":
    main()
