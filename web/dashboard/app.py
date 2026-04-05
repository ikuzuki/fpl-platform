"""FPL Analytics Dashboard — multi-page Streamlit app.

Reads from S3 data lake layers (clean, enriched, reports).
Handles gracefully when data doesn't exist yet.

Usage:
    streamlit run web/dashboard/app.py
"""

import io
import json
import logging
from datetime import UTC, datetime

import boto3
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

logger = logging.getLogger(__name__)

BUCKET = "fpl-data-lake-dev"
COST_BUCKET = "fpl-cost-reports-dev"

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
FORM_COLOURS = {"improving": "#28a745", "stable": "#ffc107", "declining": "#dc3545"}


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------


@st.cache_resource
def _s3_client() -> boto3.client:
    return boto3.client("s3", region_name="eu-west-2")


def _read_parquet(key: str, bucket: str = BUCKET) -> pd.DataFrame | None:
    """Read a Parquet file from S3, returning None if it doesn't exist."""
    try:
        resp = _s3_client().get_object(Bucket=bucket, Key=key)
        buf = io.BytesIO(resp["Body"].read())
        return pq.read_table(buf).to_pandas()
    except _s3_client().exceptions.NoSuchKey:
        return None
    except Exception:
        logger.exception("Failed to read s3://%s/%s", bucket, key)
        return None


def _read_json(key: str, bucket: str = BUCKET) -> dict | None:
    """Read a JSON file from S3, returning None if it doesn't exist."""
    try:
        resp = _s3_client().get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except _s3_client().exceptions.NoSuchKey:
        return None
    except Exception:
        logger.exception("Failed to read s3://%s/%s", bucket, key)
        return None


def _find_latest_gameweek(season: str, prefix: str) -> int | None:
    """Find the highest gameweek number available under a prefix."""
    paginator = _s3_client().get_paginator("list_objects_v2")
    gws: set[int] = set()
    full_prefix = f"{prefix}/season={season}/"
    try:
        for page in paginator.paginate(Bucket=BUCKET, Prefix=full_prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                part = cp["Prefix"].rstrip("/").split("/")[-1]
                if part.startswith("gameweek="):
                    gws.add(int(part.split("=")[1]))
    except Exception:
        return None
    return max(gws) if gws else None


# ---------------------------------------------------------------------------
# Page: Player Overview
# ---------------------------------------------------------------------------


def page_player_overview() -> None:
    st.header("Player Overview")

    season = st.sidebar.text_input("Season", value="2025-26")
    gw = _find_latest_gameweek(season, "clean/players")

    if gw is None:
        st.info("No data available yet. Run the pipeline to collect data.")
        return

    st.sidebar.write(f"Latest gameweek: **{gw}**")

    # Load clean player data
    df = _read_parquet(f"clean/players/season={season}/gameweek={gw:02d}/players.parquet")
    if df is None:
        st.warning("No player data found for this gameweek.")
        return

    # Load enrichment data if available
    enriched = _read_parquet(
        f"enriched/player_summaries/season={season}/gameweek={gw:02d}/summaries.parquet"
    )
    if enriched is not None and "id" in enriched.columns:
        df = df.merge(enriched, on="id", how="left", suffixes=("", "_enriched"))

    # Map position
    df["position"] = df["element_type"].map(POSITION_MAP)

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("Search player", "")
    with col2:
        position_filter = st.multiselect("Position", ["GKP", "DEF", "MID", "FWD"])

    if search:
        df = df[df["web_name"].str.contains(search, case=False, na=False)]
    if position_filter:
        df = df[df["position"].isin(position_filter)]

    # Display columns
    display_cols = ["web_name", "position", "team", "total_points", "minutes", "form"]
    if "form_trend" in df.columns:
        display_cols.append("form_trend")
    if "summary" in df.columns:
        display_cols.append("summary")

    df_display = (
        df[display_cols].sort_values("total_points", ascending=False).reset_index(drop=True)
    )
    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]

    st.dataframe(
        df_display,
        use_container_width=True,
        height=600,
    )

    st.caption(f"Showing {len(df_display)} players for GW{gw}")


# ---------------------------------------------------------------------------
# Page: Player Deep Dive
# ---------------------------------------------------------------------------


def page_player_deep_dive() -> None:
    st.header("Player Deep Dive")

    season = st.sidebar.text_input("Season", value="2025-26", key="dd_season")
    gw = _find_latest_gameweek(season, "clean/players")

    if gw is None:
        st.info("No data available yet.")
        return

    df = _read_parquet(f"clean/players/season={season}/gameweek={gw:02d}/players.parquet")
    if df is None:
        st.warning("No player data found.")
        return

    # Player selector
    player_names = sorted(df["web_name"].dropna().unique())
    selected = st.selectbox("Select player", player_names)
    player = df[df["web_name"] == selected].iloc[0]

    # Stats card
    st.subheader(f"{player['web_name']} — {POSITION_MAP.get(player['element_type'], '?')}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Points", int(player["total_points"]))
    col2.metric("Minutes", int(player["minutes"]))
    col3.metric("Goals", int(player.get("goals_scored", 0)))
    col4.metric("Assists", int(player.get("assists", 0)))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("xG", f"{player.get('expected_goals', 0):.1f}")
    col6.metric("xA", f"{player.get('expected_assists', 0):.1f}")
    col7.metric("Form", f"{player.get('form', 0):.1f}")
    col8.metric("ICT Index", f"{player.get('ict_index', 0):.1f}")

    # Points per gameweek chart (from gameweek live data if available)
    st.subheader("Points by Gameweek")
    gw_points = []
    for g in range(1, gw + 1):
        gw_data = _read_parquet(f"clean/players/season={season}/gameweek={g:02d}/players.parquet")
        if gw_data is not None:
            p = gw_data[gw_data["web_name"] == selected]
            if not p.empty:
                gw_points.append({"Gameweek": g, "Points": int(p.iloc[0]["total_points"])})

    if gw_points:
        gw_df = pd.DataFrame(gw_points)
        # Show per-GW delta (not cumulative)
        gw_df["GW Points"] = gw_df["Points"].diff().fillna(gw_df["Points"])
        st.bar_chart(gw_df.set_index("Gameweek")["GW Points"])
    else:
        st.info("No per-gameweek data available.")

    # LLM summary
    enriched = _read_parquet(
        f"enriched/player_summaries/season={season}/gameweek={gw:02d}/summaries.parquet"
    )
    if enriched is not None:
        player_enriched = (
            enriched[enriched["id"] == player["id"]] if "id" in enriched.columns else pd.DataFrame()
        )
        if not player_enriched.empty:
            row = player_enriched.iloc[0]
            st.subheader("LLM Analysis")
            if "summary" in row and pd.notna(row["summary"]):
                st.write(row["summary"])
            if "form_trend" in row and pd.notna(row["form_trend"]):
                colour = FORM_COLOURS.get(row["form_trend"], "#666")
                st.markdown(f"**Form trend:** :{colour}[{row['form_trend']}]")
            if "recommendation" in row and pd.notna(row["recommendation"]):
                st.info(f"**Fixture outlook:** {row['recommendation']}")
        else:
            st.info("No LLM analysis available for this player.")
    else:
        st.info("No enrichment data available yet.")


# ---------------------------------------------------------------------------
# Page: Injury Watch
# ---------------------------------------------------------------------------


def page_injury_watch() -> None:
    st.header("Injury Watch")

    season = st.sidebar.text_input("Season", value="2025-26", key="iw_season")
    gw = _find_latest_gameweek(season, "enriched/player_summaries")

    if gw is None:
        st.info("No enrichment data available yet. Run the enrichment pipeline first.")
        return

    enriched = _read_parquet(
        f"enriched/player_summaries/season={season}/gameweek={gw:02d}/summaries.parquet"
    )
    if enriched is None:
        st.warning("No enrichment data found.")
        return

    if "risk_score" not in enriched.columns:
        st.info("No injury signal data in this enrichment run.")
        return

    # Filter high-risk players
    injured = enriched[enriched["risk_score"] >= 6].sort_values("risk_score", ascending=False)

    if injured.empty:
        st.success("No high-risk injury signals detected.")
        return

    st.warning(f"**{len(injured)}** players with injury risk score >= 6")

    display_cols = ["web_name", "team", "risk_score", "reasoning"]
    available = [c for c in display_cols if c in injured.columns]

    # Load clean data for team/name if not in enriched
    if "web_name" not in injured.columns:
        clean = _read_parquet(f"clean/players/season={season}/gameweek={gw:02d}/players.parquet")
        if clean is not None and "id" in injured.columns:
            injured = injured.merge(clean[["id", "web_name", "team"]], on="id", how="left")
            available = [c for c in display_cols if c in injured.columns]

    df_display = injured[available].reset_index(drop=True)
    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]
    st.dataframe(df_display, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Pipeline Health
# ---------------------------------------------------------------------------


def page_pipeline_health() -> None:
    st.header("Pipeline Health")

    season = st.sidebar.text_input("Season", value="2025-26", key="ph_season")

    # Find latest gameweek across layers
    latest_raw = _find_latest_gameweek(season, "raw/fpl-api")
    latest_clean = _find_latest_gameweek(season, "clean/players")
    latest_enriched = _find_latest_gameweek(season, "enriched/player_summaries")

    col1, col2, col3 = st.columns(3)
    col1.metric("Latest Raw GW", latest_raw or "N/A")
    col2.metric("Latest Clean GW", latest_clean or "N/A")
    col3.metric("Latest Enriched GW", latest_enriched or "N/A")

    # Record counts
    if latest_clean:
        clean = _read_parquet(
            f"clean/players/season={season}/gameweek={latest_clean:02d}/players.parquet"
        )
        if clean is not None:
            st.metric("Clean Player Records", len(clean))

    # Cost report
    if latest_enriched:
        cost = _read_json(
            f"reports/costs/season={season}/gameweek={latest_enriched:02d}/cost_report.json"
        )
        if cost:
            st.subheader("LLM Cost Report")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Calls", cost.get("total_calls", "N/A"))
            col2.metric("Input Tokens", f"{cost.get('total_input_tokens', 0):,}")
            col3.metric("Output Tokens", f"{cost.get('total_output_tokens', 0):,}")
            st.metric("Estimated Cost", f"${cost.get('estimated_cost_usd', 0):.4f}")

            if "model_breakdown" in cost:
                st.write("**By model:**")
                st.json(cost["model_breakdown"])
        else:
            st.info("No cost report available.")

    # Data freshness check
    if latest_raw:
        raw_prefix = f"raw/fpl-api/season={season}/gameweek={latest_raw:02d}/"
        try:
            resp = _s3_client().list_objects_v2(Bucket=BUCKET, Prefix=raw_prefix, MaxKeys=1)
            if resp.get("Contents"):
                last_modified = resp["Contents"][0]["LastModified"]
                days_ago = (datetime.now(UTC) - last_modified).days
                if days_ago > 8:
                    st.error(
                        f"Data is **{days_ago} days old** — pipeline may not be running. "
                        "Check Step Functions execution history."
                    )
                else:
                    st.success(f"Data last updated {days_ago} day(s) ago.")
        except Exception:
            st.warning("Could not check data freshness.")
    else:
        st.info("No raw data found. Run the collection pipeline first.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="FPL Analytics",
        page_icon="",
        layout="wide",
    )

    st.title("FPL Analytics Dashboard")

    page = st.sidebar.radio(
        "Navigation",
        ["Player Overview", "Player Deep Dive", "Injury Watch", "Pipeline Health"],
    )

    if page == "Player Overview":
        page_player_overview()
    elif page == "Player Deep Dive":
        page_player_deep_dive()
    elif page == "Injury Watch":
        page_injury_watch()
    elif page == "Pipeline Health":
        page_pipeline_health()


if __name__ == "__main__":
    main()
