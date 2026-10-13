import os
import sqlite3
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# Page Setup
# ---------------------------------------------------------
st.set_page_config(
    page_title="IPL Analytics - Teams & Venues",
    page_icon="🏏",
    layout="wide"
)

st.markdown(
    """
    <style>
    :root {
        color-scheme: dark;
        --primary-color: #12CFE0;
        --background-color: #050B0A;
        --secondary-background-color: #081310;
        --text-color: #F5F7F6;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stHeader"] {
        background-color: #050B0A !important;
        color: #F5F7F6 !important;
    }
    [data-testid="stHeader"] { background-color: #050B0A !important; }
    [data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background-color: #081310 !important;
        border-right: 1px solid #1B2A25;
    }
    [data-testid="stAppViewContainer"] h1,
    [data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3,
    [data-testid="stAppViewContainer"] h4,
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] span,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: #F5F7F6;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
        color: #91A19B !important;
    }
    [data-testid="stMetric"] {
        background: #081310;
        border: 1px solid #1B2A25;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.18);
    }
    [data-testid="stMetric"] label,
    [data-testid="stMetric"] [data-testid="stMetricValue"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #F5F7F6 !important;
    }
    [data-testid="stTab"][aria-selected="true"] {
        color: #12CFE0 !important;
        border-bottom: 2px solid #12CFE0 !important;
    }
    [data-testid="stTab"]:not([aria-selected="true"]) {
        color: #91A19B !important;
    }
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background-color: #081310 !important;
        color: #F5F7F6 !important;
        border-color: #1B2A25 !important;
    }
    [data-baseweb="tag"] {
        background-color: #123a3c !important;
        color: #12CFE0 !important;
    }
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"],
    [role="option"] {
        background-color: #081310 !important;
        color: #F5F7F6 !important;
    }
    [role="option"]:hover,
    [aria-selected="true"][role="option"] {
        background-color: #1B2A25 !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
        background-color: #12CFE0 !important;
        border-color: #12CFE0 !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] div[data-testid] {
        background-color: #12CFE0;
    }
    [data-testid="stExpander"] {
        border-color: #1B2A25 !important;
        background-color: #081310 !important;
    }
    [data-testid="stPlotlyChart"] {
        background: #081310;
        border: 1px solid #1B2A25;
        border-radius: 12px;
        padding: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Robust Database Connection Helper
# ---------------------------------------------------------
@st.cache_resource
def find_and_connect_db():
    """
    Locates the populated SQLite database relative to this app.
    """
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "data" / "raw" / "ipl.db",
        project_root / "data" / "ipl.db",
        project_root / "ipl.db",
    ]

    for db_path in candidates:
        if db_path.is_file() and db_path.stat().st_size > 0:
            try:
                with sqlite3.connect(db_path) as conn:
                    objects = {
                        row[0]
                        for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                        )
                    }
                if "v_matches_clean" in objects:
                    return str(db_path)
            except sqlite3.Error:
                continue

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Could not find a populated IPL database containing v_matches_clean. "
        f"Searched: {searched}"
    )

try:
    DB_PATH = find_and_connect_db()
except FileNotFoundError as error:
    st.error(str(error))
    st.stop()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TEMP VIEW matches AS
        SELECT *, match_winner AS winner
        FROM main.v_matches_clean
    """)
    available_objects = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view')"
        )
    }
    if "deliveries" in available_objects:
        conn.execute("""
            CREATE TEMP VIEW deliveries AS
            SELECT *, batter_runs AS batsman_runs, innings AS inning
            FROM main.deliveries
        """)
    return conn

def q(query: str, params: tuple = ()) -> pd.DataFrame:
    """Executes a SQL query and returns the resulting DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


all_seasons = q("""
    SELECT DISTINCT season
    FROM matches
    WHERE season IS NOT NULL
    ORDER BY season
""")["season"].tolist()


st.sidebar.header("Dashboard filters")
st.sidebar.caption("Filters apply only to their named chart.")


def chart_season_filter(key: str, label: str, ground_limit: bool = False) -> list:
    """Show an independent season filter for one chart in the sidebar."""
    with st.sidebar.expander(label):
        selected_seasons = st.multiselect(
            "Seasons",
            options=all_seasons,
            default=all_seasons,
            key=key,
        )
        if ground_limit:
            st.slider(
                "Grounds to display",
                min_value=5,
                max_value=20,
                value=8,
                key=f"{key}_ground_limit",
            )
        return selected_seasons


def season_condition(seasons: list, column: str = "season") -> tuple:
    """Return a parameterized SQL condition for a chart's selected seasons."""
    if not seasons:
        return "1 = 0", ()
    placeholders = ", ".join("?" for _ in seasons)
    return f"{column} IN ({placeholders})", tuple(seasons)


def finish_chart(fig, height: int = 420, x_tickangle: int = 0):
    """Apply a consistent size, spacing, typography, and fully visible axes."""
    fig.update_layout(
        template="plotly_dark",
        height=height,
        autosize=True,
        margin=dict(l=70, r=36, t=54, b=78 if x_tickangle else 58),
        font=dict(family="Arial, sans-serif", size=12, color="#F5F7F6"),
        paper_bgcolor="#081310",
        plot_bgcolor="#081310",
        colorway=["#12CFE0", "#7DE36A", "#A65DB5", "#E58DB7"],
        legend=dict(title_text="", font=dict(color="#F5F7F6")),
        xaxis=dict(
            automargin=True,
            tickangle=x_tickangle,
            title_standoff=12,
            tickfont=dict(color="#91A19B"),
            title_font=dict(color="#F5F7F6"),
            gridcolor="#1B2A25",
            zerolinecolor="#1B2A25",
        ),
        yaxis=dict(
            automargin=True,
            title_standoff=12,
            tickfont=dict(color="#91A19B"),
            title_font=dict(color="#F5F7F6"),
            gridcolor="#1B2A25",
            zerolinecolor="#1B2A25",
        ),
    )
    return fig


def wrap_ground_labels(values) -> list:
    """Wrap long ground names so category labels remain readable in narrow charts."""
    return [
        "<br>".join(textwrap.wrap(str(value), width=22))
        for value in values
    ]


# ---------------------------------------------------------
# Startup Diagnostic Check
# ---------------------------------------------------------
try:
    with get_connection() as conn:
        db_objects = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        tables_in_db = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM main.sqlite_master WHERE type='table'"
            )
        }
except sqlite3.Error:
    db_objects = set()
    tables_in_db = []

if "matches" not in tables_in_db or "v_matches_clean" not in db_objects:
    st.error(
        f"**Database Connection Warning:**\n\n"
        f"Connected to: `{os.path.abspath(DB_PATH)}`\n\n"
        f"Database objects found: `{sorted(db_objects)}`\n\n"
        f"The populated `matches` table and `v_matches_clean` view are required."
    )
    st.stop()

# ---------------------------------------------------------
# Tabs Setup
# ---------------------------------------------------------
tab_overview, tab_venue, tab_team = st.tabs(["Overview", "Venue", "Team"])

# =========================================================
# TAB 1: OVERVIEW — All Teams and Grounds
# =========================================================
with tab_overview:
    st.title("IPL League Overview: Teams & Grounds")
    st.caption("A league-wide strategic breakdown of team wins, ground frequencies, and batting-first advantages.")

    # 1. Metric Cards (Exactly 3)
    df_counts = q("""
        SELECT 
            (SELECT COUNT(DISTINCT team) FROM (
                SELECT team1 AS team FROM matches WHERE team1 IS NOT NULL
                UNION 
                SELECT team2 AS team FROM matches WHERE team2 IS NOT NULL
            )) AS total_teams,
            COUNT(DISTINCT venue_clean) AS total_grounds
        FROM matches
        WHERE venue_clean IS NOT NULL
    """)
    total_teams = int(df_counts['total_teams'].iloc[0])
    total_grounds = int(df_counts['total_grounds'].iloc[0])

    df_total_matches = q("SELECT COUNT(*) AS total_matches FROM matches")
    total_matches = int(df_total_matches['total_matches'].iloc[0])

    df_chase_finding = q("""
        SELECT 
            ROUND(100.0 * SUM(CASE WHEN toss_decision = 'field' AND winner = toss_winner THEN 1 ELSE 0 END) / COUNT(*), 1) AS chase_win_pct
        FROM matches
        WHERE result != 'no result' AND toss_decision IS NOT NULL
    """)
    chase_pct = df_chase_finding['chase_win_pct'].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Teams / cleaned grounds", f"{total_teams} / {total_grounds}")
    col2.metric("Total League Matches", f"{total_matches}")
    col3.metric("Chasing win rate", f"{chase_pct}%", help="Chasing win rate across all completed matches")

    st.markdown("---")

    # 2. Hero Visual: Matches won by each team (Visibly larger)
    st.subheader("Team Dominance: Total Wins vs Matches Played")
    hero_seasons = chart_season_filter(
        "overview_wins_seasons", "Overview · Team wins and matches"
    )
    hero_season_sql, hero_season_params = season_condition(hero_seasons, "season")
    df_team_perf = q("""
        WITH team_matches AS (
            SELECT team1 AS team FROM matches
            WHERE {season_filter}
            UNION ALL
            SELECT team2 AS team FROM matches
            WHERE {season_filter}
        ),
        team_totals AS (
            SELECT team, COUNT(*) AS matches_played
            FROM team_matches
            WHERE team IS NOT NULL
            GROUP BY team
        ),
        team_wins AS (
            SELECT winner AS team, COUNT(*) AS wins
            FROM matches
            WHERE winner IS NOT NULL AND {season_filter}
            GROUP BY winner
        )
        SELECT 
            t.team,
            t.matches_played,
            COALESCE(w.wins, 0) AS wins,
            ROUND(100.0 * COALESCE(w.wins, 0) / t.matches_played, 1) AS win_rate
        FROM team_totals t
        LEFT JOIN team_wins w ON t.team = w.team
        ORDER BY wins DESC
    """.format(season_filter=hero_season_sql), hero_season_params * 3)

    fig_hero_overview = go.Figure()
    fig_hero_overview.add_trace(go.Bar(
        x=df_team_perf['team'],
        y=df_team_perf['matches_played'],
        name='Matches Played',
        marker_color='#A65DB5'
    ))
    fig_hero_overview.add_trace(go.Bar(
        x=df_team_perf['team'],
        y=df_team_perf['wins'],
        name='Wins',
        marker_color='#12CFE0'
    ))
    fig_hero_overview.update_layout(
        barmode='group',
        xaxis_title="Team",
        yaxis_title="Count",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(finish_chart(fig_hero_overview, height=560, x_tickangle=-28), width="stretch")

    # 3. Visual 2 & Visual 3
    col_v2, col_v3 = st.columns(2)

    with col_v2:
        st.subheader("Ground Sample Sizes & Evaluation Cut-off")
        cut_off_threshold = 15
        venue_count_seasons = chart_season_filter(
            "overview_venue_counts_seasons",
            "Overview · Matches by ground",
            ground_limit=True,
        )
        venue_count_sql, venue_count_params = season_condition(venue_count_seasons)
        venue_limit = st.session_state["overview_venue_counts_seasons_ground_limit"]
        df_venue_counts = q("""
            SELECT 
                venue_clean, 
                COUNT(*) as match_count,
                CASE WHEN COUNT(*) >= 15 THEN 'Reliable Sample (>=15)' ELSE 'Low Sample (<15)' END as status
            FROM matches
            WHERE venue_clean IS NOT NULL AND {season_filter}
            GROUP BY venue_clean
            ORDER BY match_count DESC
            LIMIT ?
        """.format(season_filter=venue_count_sql), venue_count_params + (venue_limit,))
        st.caption(f"Showing {len(df_venue_counts)} busiest grounds; the dashed line marks the 15-match sample cutoff.")
        fig_v2 = px.bar(
            df_venue_counts.sort_values("match_count"),
            x='match_count',
            y='venue_clean',
            orientation="h",
            color='status',
            color_discrete_map={'Reliable Sample (>=15)': '#12CFE0', 'Low Sample (<15)': '#A65DB5'},
            labels={'venue_clean': 'Cleaned Venue', 'match_count': 'Matches Held'}
        )
        fig_v2.update_yaxes(
            tickmode="array",
            tickvals=df_venue_counts["venue_clean"],
            ticktext=wrap_ground_labels(df_venue_counts["venue_clean"]),
        )
        fig_v2.add_vline(x=cut_off_threshold, line_dash="dash", line_color="#E58DB7")
        fig_v2.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            )
        )
        fig_v2.update_layout(xaxis_title="Matches held", yaxis_title=None)
        st.plotly_chart(finish_chart(fig_v2, height=440), width="stretch")

    with col_v3:
        st.subheader("Batting-First Win Rate at Eligible Grounds")
        bat_first_seasons = chart_season_filter(
            "overview_bat_first_seasons",
            "Overview · Batting-first win rate",
            ground_limit=True,
        )
        bat_first_sql, bat_first_params = season_condition(bat_first_seasons)
        bat_first_limit = st.session_state["overview_bat_first_seasons_ground_limit"]
        df_league_avg = q("""
            SELECT ROUND(100.0 * SUM(CASE WHEN win_by_runs > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as league_bat_first_pct
            FROM matches
            WHERE result != 'no result' AND (win_by_runs > 0 OR win_by_wickets > 0)
                AND {season_filter}
        """.format(season_filter=bat_first_sql), bat_first_params)
        league_bat_first_pct = df_league_avg['league_bat_first_pct'].iloc[0]

        df_eligible_venues = q("""
            SELECT 
                venue_clean,
                COUNT(*) AS total_matches,
                ROUND(100.0 * SUM(CASE WHEN win_by_runs > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS bat_first_win_pct
            FROM matches
            WHERE venue_clean IS NOT NULL AND (win_by_runs > 0 OR win_by_wickets > 0)
                AND {season_filter}
            GROUP BY venue_clean
            HAVING COUNT(*) >= 15
            ORDER BY bat_first_win_pct DESC
            LIMIT ?
        """.format(season_filter=bat_first_sql), bat_first_params + (bat_first_limit,))
        fig_v3 = px.bar(
            df_eligible_venues.sort_values("bat_first_win_pct"),
            x='bat_first_win_pct',
            y='venue_clean',
            orientation="h",
            labels={'venue_clean': 'Cleaned Venue', 'bat_first_win_pct': 'Batting 1st Win %'},
            hover_data=['total_matches'],
            color_discrete_sequence=['#12CFE0']
        )
        fig_v3.update_yaxes(
            tickmode="array",
            tickvals=df_eligible_venues["venue_clean"],
            ticktext=wrap_ground_labels(df_eligible_venues["venue_clean"]),
        )
        if league_bat_first_pct is not None:
            fig_v3.add_vline(x=league_bat_first_pct, line_dash="dot", line_color="#E58DB7")
        fig_v3.update_layout(xaxis_title="Batting-first win rate (%)", yaxis_title=None, xaxis_range=[0, 100])
        st.caption(
            f"Showing {len(df_eligible_venues)} eligible grounds ranked by batting-first win rate. "
            f"The dashed line is the league average ({league_bat_first_pct}%). Hover for sample size."
        )
        st.plotly_chart(finish_chart(fig_v3, height=440), width="stretch")

    # 4. Extra Visuals (Visuals 4 & 5)
    col_v4, col_v5 = st.columns(2)
    with col_v4:
        st.subheader("Total Sixes Hit by Team")
        has_deliveries = "deliveries" in tables_in_db
        if has_deliveries:
            sixes_seasons = chart_season_filter(
                "overview_sixes_seasons", "Overview · Sixes by team"
            )
            sixes_sql, sixes_params = season_condition(sixes_seasons, "m.season")
            df_sixes = q("""
                SELECT d.batting_team, COUNT(*) as six_count
                FROM deliveries d
                JOIN matches m ON m.match_id = d.match_id
                WHERE d.batsman_runs = 6 AND {season_filter}
                GROUP BY d.batting_team
                ORDER BY six_count DESC
            """.format(season_filter=sixes_sql), sixes_params)
            fig_v4 = px.bar(df_sixes.sort_values("six_count"), x='six_count', y='batting_team',
                            orientation="h", color_discrete_sequence=['#7DE36A'],
                            labels={'batting_team': 'Team', 'six_count': 'Total Sixes'})
            st.plotly_chart(finish_chart(fig_v4, height=440), width="stretch")
        else:
            st.info("Deliveries table not present for boundary breakdown.")

    with col_v5:
        st.subheader("Grounds Deployed Per Season")
        grounds_seasons = chart_season_filter(
            "overview_season_grounds_seasons", "Overview · Grounds by season"
        )
        grounds_sql, grounds_params = season_condition(grounds_seasons)
        df_season_grounds = q("""
            SELECT season, COUNT(DISTINCT venue_clean) as distinct_grounds
            FROM matches
            WHERE {season_filter}
            GROUP BY season
            ORDER BY season ASC
        """.format(season_filter=grounds_sql), grounds_params)
        fig_v5 = px.line(df_season_grounds, x='season', y='distinct_grounds', markers=True,
                         labels={'season': 'Season', 'distinct_grounds': 'Cleaned Grounds Used'})
        fig_v5.update_traces(cliponaxis=False, line=dict(width=3), marker=dict(size=8))
        fig_v5.update_layout(xaxis_title="Season", yaxis_title="Cleaned grounds used")
        st.plotly_chart(finish_chart(fig_v5, height=440, x_tickangle=-30), width="stretch")


# =========================================================
# TAB 2: VENUE — One Ground at a Time
# =========================================================
with tab_venue:
    st.title("Venue Tactical Profile")
    st.caption("Investigate ground scoring tendencies and chase-versus-defend viability before the toss.")

    df_venues_list = q("""
        SELECT venue_clean, COUNT(*) as match_count
        FROM matches
        WHERE venue_clean IS NOT NULL
        GROUP BY venue_clean
        ORDER BY match_count DESC
    """)
    venue_options = df_venues_list['venue_clean'].tolist()
    venue_display_map = {row['venue_clean']: f"{row['venue_clean']} ({row['match_count']} matches)" for _, row in df_venues_list.iterrows()}

    with st.sidebar.expander("Venue · Selected ground"):
        selected_venue = st.selectbox(
            "Ground (sorted by matches held)",
            options=venue_options,
            format_func=lambda x: venue_display_map.get(x, x),
            key="venue_selected_ground",
        )

    df_sel_venue_matches = q("""
        SELECT COUNT(*) as count 
        FROM matches 
        WHERE venue_clean = ?
    """, (selected_venue,))
    venue_matches_count = int(df_sel_venue_matches['count'].iloc[0])

    col_vm, _ = st.columns([1, 3])
    col_vm.metric("Matches Hosted at Venue", venue_matches_count)
    if venue_matches_count < 15:
        st.warning(f"⚠️ Small sample size alert: Only {venue_matches_count} matches recorded at this ground. Tactical conclusions should be interpreted cautiously.")

    st.markdown("---")

    # Visual 1 — Hero: 1st Innings Par Score vs League Average
    st.subheader(f"1st Innings Par Score vs League Average: {selected_venue}")
    has_deliveries = "deliveries" in tables_in_db

    if has_deliveries:
        innings_seasons = chart_season_filter(
            "venue_first_innings_seasons", "Venue · First-innings score"
        )
        innings_sql, innings_params = season_condition(innings_seasons, "m.season")
        df_venue_innings = q("""
            WITH match_innings_totals AS (
                SELECT 
                    m.match_id,
                    m.venue_clean,
                    m.season,
                    SUM(d.total_runs) as first_innings_score
                FROM matches m
                JOIN deliveries d ON m.match_id = d.match_id
                WHERE d.inning = 1 AND {season_filter}
                GROUP BY m.match_id, m.venue_clean, m.season
            ),
            league_par AS (
                SELECT ROUND(AVG(first_innings_score), 1) as league_avg
                FROM match_innings_totals
            ),
            ground_par AS (
                SELECT ROUND(AVG(first_innings_score), 1) as venue_avg, COUNT(*) as sample_count
                FROM match_innings_totals
                WHERE venue_clean = ?
            )
            SELECT 
                (SELECT venue_avg FROM ground_par) as ground_avg,
                (SELECT league_avg FROM league_par) as league_avg,
                (SELECT sample_count FROM ground_par) as venue_innings
        """.format(season_filter=innings_sql), innings_params + (selected_venue,))

        v_avg = df_venue_innings['ground_avg'].iloc[0]
        l_avg = df_venue_innings['league_avg'].iloc[0]
        venue_innings_count = int(df_venue_innings['venue_innings'].iloc[0])
    else:
        innings_seasons = []
        v_avg = l_avg = None
        venue_innings_count = 0

    if not has_deliveries:
        st.info("First-innings score chart requires the deliveries table.")
    elif not innings_seasons:
        st.info("Select at least one season for this chart.")
    elif v_avg is None or l_avg is None:
        st.info("No first-innings score data is available for this ground and season selection.")
    else:
        fig_hero_venue = go.Figure()
        fig_hero_venue.add_trace(go.Bar(
            x=[selected_venue],
            y=[v_avg],
            name="Venue 1st Innings Avg",
            marker_color="#12CFE0",
            text=[f"{v_avg} runs (n={venue_innings_count})"],
            textposition="auto"
        ))
        fig_hero_venue.add_hline(y=l_avg, line_dash="dash", line_color="#E58DB7",
                                 annotation_text=f"League Average ({l_avg} runs)", annotation_position="top left")
        fig_hero_venue.update_layout(
            yaxis_title="Average 1st Innings Runs",
            yaxis_range=[0, max(240, v_avg + 30)]
        )
        st.plotly_chart(finish_chart(fig_hero_venue, height=540), width="stretch")

    col_vsub1, col_vsub2 = st.columns(2)
    with col_vsub1:
        st.subheader("Outcome: Batting First vs Chasing")
        outcome_seasons = chart_season_filter(
            "venue_outcome_seasons", "Venue · Batting-first or chase results"
        )
        outcome_sql, outcome_params = season_condition(outcome_seasons)
        df_venue_outcome = q("""
            SELECT 
                CASE 
                    WHEN win_by_runs > 0 THEN 'Batting First Won'
                    WHEN win_by_wickets > 0 THEN 'Chasing Won'
                    ELSE 'Tie/No Result'
                END as result_type,
                COUNT(*) as matches_count
            FROM matches
                WHERE venue_clean = ? AND {season_filter}
            GROUP BY result_type
        """.format(season_filter=outcome_sql), (selected_venue,) + outcome_params)

        if not outcome_seasons:
                st.info("Select at least one season for this chart.")
        elif df_venue_outcome.empty:
                st.info("No match outcomes are available for this ground and season selection.")
        else:
                fig_venue_outcome = px.pie(
                    df_venue_outcome,
                    names='result_type',
                    values='matches_count',
                    color='result_type',
                    color_discrete_map={'Batting First Won': '#12CFE0', 'Chasing Won': '#7DE36A', 'Tie/No Result': '#A65DB5'},
                    hole=0.4
                )
                fig_venue_outcome.update_traces(
                    textinfo="label+value",
                    hovertemplate="%{label}: %{value} matches<extra></extra>"
                )
                st.plotly_chart(finish_chart(fig_venue_outcome, height=440), width="stretch")

    with col_vsub2:
        st.subheader(f"Most Active Teams at {selected_venue}")
        active_seasons = chart_season_filter(
            "venue_active_teams_seasons", "Venue · Team appearances"
        )
        active_sql, active_params = season_condition(active_seasons)
        df_venue_teams = q("""
                WITH venue_matches AS (
                    SELECT team1 as team FROM matches WHERE venue_clean = ? AND {season_filter}
                    UNION ALL
                    SELECT team2 as team FROM matches WHERE venue_clean = ? AND {season_filter}
                )
            SELECT team, COUNT(*) as appearances
            FROM venue_matches
            WHERE team IS NOT NULL
            GROUP BY team
            ORDER BY appearances DESC
            LIMIT 8
        """.format(season_filter=active_sql),
            (selected_venue,) + active_params + (selected_venue,) + active_params)

        if not active_seasons:
            st.info("Select at least one season for this chart.")
        elif df_venue_teams.empty:
            st.info("No team appearances are available for this ground and season selection.")
        else:
            fig_venue_teams = px.bar(
                df_venue_teams,
                x='appearances',
                y='team',
                orientation='h',
                text='appearances',
                labels={'appearances': 'Appearances', 'team': 'Team'},
                color_discrete_sequence=['#A65DB5']
            )
            fig_venue_teams.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(finish_chart(fig_venue_teams, height=440), width="stretch")


# =========================================================
# TAB 3: TEAM — One Team at a Time
# =========================================================
with tab_team:
    st.title("Team Tactical Analysis")
    st.caption("Season-by-season stability and direct head-to-head match-up records.")

    df_teams_list = q("""
        SELECT DISTINCT team FROM (
            SELECT team1 AS team FROM matches WHERE team1 IS NOT NULL
            UNION
            SELECT team2 AS team FROM matches WHERE team2 IS NOT NULL
        ) ORDER BY team ASC
    """)
    team_options = df_teams_list['team'].tolist()
    with st.sidebar.expander("Team · Selected team"):
        selected_team = st.selectbox(
            "Team",
            options=team_options,
            key="team_selected_team",
        )

    df_team_metrics = q("""
        WITH team_all AS (
            SELECT 
                COUNT(*) as matches_played,
                SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as matches_won
            FROM matches
            WHERE team1 = ? OR team2 = ?
        )
        SELECT 
            matches_played,
            matches_won,
            ROUND(100.0 * matches_won / CASE WHEN matches_played = 0 THEN 1 ELSE matches_played END, 1) as win_rate
        FROM team_all
    """, (selected_team, selected_team, selected_team))

    t_played = int(df_team_metrics['matches_played'].iloc[0])
    t_won = int(df_team_metrics['matches_won'].iloc[0])
    t_rate = float(df_team_metrics['win_rate'].iloc[0])

    c_tm1, c_tm2, c_tm3 = st.columns(3)
    c_tm1.metric("Matches Played", t_played)
    c_tm2.metric("Matches Won", t_won)
    c_tm3.metric("Overall Win Rate", f"{t_rate}%")

    st.markdown("---")

    # Visual 1 — Hero: Season Win Rate with 50% line
    st.subheader(f"Season-by-Season Win Rate: {selected_team}")
    team_season_filter = chart_season_filter(
        "team_season_win_rate_seasons", "Team · Seasonal win rate"
    )
    team_season_sql, team_season_params = season_condition(team_season_filter)
    df_season_rate = q("""
        SELECT 
            season,
            COUNT(*) as season_played,
            SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as season_won,
            ROUND(100.0 * SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) / COUNT(*), 1) as season_win_rate
        FROM matches
        WHERE (team1 = ? OR team2 = ?) AND {season_filter}
        GROUP BY season
        ORDER BY season ASC
    """.format(season_filter=team_season_sql),
        (selected_team, selected_team, selected_team, selected_team) + team_season_params)

    if not team_season_filter:
        st.info("Select at least one season for this chart.")
    elif df_season_rate.empty:
        st.info("No seasonal match data is available for this team and season selection.")
    else:
        fig_hero_team = px.line(
            df_season_rate,
            x='season',
            y='season_win_rate',
            markers=True,
            labels={'season': 'Season', 'season_win_rate': 'Win Rate (%)'},
            hover_data=['season_played', 'season_won']
        )
        fig_hero_team.add_hline(y=50.0, line_dash="dash", line_color="#E58DB7", annotation_text="50% Par Benchmark")
        fig_hero_team.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(finish_chart(fig_hero_team, height=540, x_tickangle=-30), width="stretch")

    col_t2, col_t3 = st.columns(2)

    with col_t2:
        st.subheader("Head-to-Head Opponent Records")
        h2h_seasons = chart_season_filter(
            "team_opponent_record_seasons", "Team · Opponent record"
        )
        h2h_season_sql, h2h_season_params = season_condition(h2h_seasons)
        df_h2h = q("""
            WITH opponents AS (
                SELECT 
                    CASE WHEN team1 = ? THEN team2 ELSE team1 END as opponent,
                    CASE WHEN winner = ? THEN 1 ELSE 0 END as won
                FROM matches
                WHERE (team1 = ? OR team2 = ?) AND {season_filter}
            )
            SELECT 
                opponent,
                COUNT(*) as matches_played,
                SUM(won) as wins,
                COUNT(*) - SUM(won) as losses
            FROM opponents
            GROUP BY opponent
            ORDER BY matches_played DESC
        """.format(season_filter=h2h_season_sql),
            (selected_team, selected_team, selected_team, selected_team) + h2h_season_params)

        if not h2h_seasons:
            st.info("Select at least one season for this chart.")
        elif df_h2h.empty:
            st.info("No opponent records are available for this team and season selection.")
        else:
            fig_h2h = go.Figure()
            fig_h2h.add_trace(go.Bar(
                y=df_h2h['opponent'],
                x=df_h2h['wins'],
                name='Wins',
                orientation='h',
                marker_color='#7DE36A'
            ))
            fig_h2h.add_trace(go.Bar(
                y=df_h2h['opponent'],
                x=df_h2h['losses'],
                name='Losses',
                orientation='h',
                marker_color='#E58DB7'
            ))
            fig_h2h.update_layout(
                barmode='stack',
                xaxis_title="Matches",
                yaxis=dict(autorange="reversed"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(finish_chart(fig_h2h, height=440), width="stretch")

    with col_t3:
        st.subheader("Toss Decisions and Match Outcomes")
        toss_seasons = chart_season_filter(
            "team_toss_decision_seasons", "Team · Toss decisions"
        )
        toss_season_sql, toss_season_params = season_condition(toss_seasons)
        df_toss_decision = q("""
            SELECT 
                toss_decision,
                COUNT(*) as total_times,
                SUM(CASE WHEN winner = ? THEN 1 ELSE 0 END) as match_wins
            FROM matches
            WHERE toss_winner = ? AND {season_filter}
            GROUP BY toss_decision
        """.format(season_filter=toss_season_sql), (selected_team, selected_team) + toss_season_params)

        if not toss_seasons:
            st.info("Select at least one season for this chart.")
        elif df_toss_decision.empty:
            st.info("No toss data is available for this team and season selection.")
        else:
            fig_toss = px.bar(
                df_toss_decision,
                x='toss_decision',
                y=['match_wins', 'total_times'],
                barmode='group',
                labels={'value': 'Count', 'toss_decision': 'Toss Decision'},
                color_discrete_map={'match_wins': '#12CFE0', 'total_times': '#A65DB5'}
            )
            st.plotly_chart(finish_chart(fig_toss, height=440), width="stretch")