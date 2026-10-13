import math
from pathlib import Path
 
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import reports.figures.app as st
 
st.set_page_config(page_title="IPL Toss & Venue Dashboard", layout="wide")
 
READER = "For the team analyst, deciding whether to bat or field after winning the toss at each venue"
HERO_H, SMALL_H = 460, 320
NAVY, BLUE, ORANGE, GREY = "#16304f", "#2b7bba", "#e8833a", "#9aa5b1"
 
# ----------------------------------------------------------------------------
# 1. LOAD + CLEAN
# ----------------------------------------------------------------------------
def find(name):
    for d in [Path("data"), Path("."), Path(__file__).parent, Path(__file__).parent.parent / "data",
              Path(__file__).parent.parent]:
        if (d / name).exists():
            return d / name
    st.error(f"Cannot find {name}. Put it in a 'data' folder next to the app.")
    st.stop()
 
 
def pick(df, options):
    for o in options:
        if o in df.columns:
            return o
    return None
 
 
TEAM_ALIASES = {
    "delhi daredevils": "Delhi Capitals", "kings xi punjab": "Punjab Kings",
    "royal challengers bengaluru": "Royal Challengers Bangalore",
    "rising pune supergiants": "Rising Pune Supergiant",
    "rising pune supergiant": "Rising Pune Supergiant", "pune warriors india": "Pune Warriors",
    "gujarat lions": "Gujarat Lions",
}
VENUE_ALIASES = {
    "feroz shah kotla": "arun jaitley stadium",
    "sardar patel stadium": "narendra modi stadium",
    "punjab cricket association is bindra stadium": "is bindra stadium",
    "punjab cricket association stadium": "is bindra stadium",
    "maharaja yadavindra singh international cricket stadium": "mullanpur stadium",
    "zayed cricket stadium": "sheikh zayed stadium",
    "subrata roy sahara stadium": "maharashtra cricket association stadium",
}
 
 
def venue_key(name):
    if pd.isna(name):
        return None
    s = str(name).lower().split(",")[0].replace(".", " ")
    s = " ".join(s.split())
    return VENUE_ALIASES.get(s, s)
 
 
@st.cache_data
def load():
    teams = pd.read_csv(find("teams.csv"))
    venues = pd.read_csv(find("venues.csv"))
    m = pd.read_csv(find("matches.csv"))
 
    # --- team lookup: id -> clean name (3604 'Supergiants' merged into 4)
    teams["clean"] = teams.team_name.str.lower().map(TEAM_ALIASES).fillna(teams.team_name)
    id2team = dict(zip(teams.team_id, teams.clean))
 
    def to_team(s):
        if pd.api.types.is_numeric_dtype(s):
            return s.map(id2team)
        low = s.astype(str).str.strip().str.lower()
        return low.map(TEAM_ALIASES).fillna(s)
 
    # --- venue lookup: collapse 63 rows to the real grounds
    venues["key"] = venues.venue.map(venue_key)
    first = venues.sort_values("venue_id").groupby("key").first()
    disp = first.venue.str.split(",").str[0].to_dict()
    city = (venues.dropna(subset=["city"]).sort_values("venue_id").groupby("key").city.first()
            .replace({"Bangalore": "Bengaluru"}).to_dict())
    id2key = dict(zip(venues.venue_id, venues.key))
 
    c = {k: pick(m, v) for k, v in {
        "season": ["season", "Season", "year"], "date": ["date", "match_date"],
        "t1": ["team1_id", "team1", "team_1"], "t2": ["team2_id", "team2", "team_2"],
        "tw": ["toss_winner_id", "toss_winner"], "td": ["toss_decision", "toss_choice"],
        "win": ["winner_id", "winner", "match_winner"], "ven": ["venue_id", "venue", "ground"],
    }.items()}
    need = ["t1", "t2", "tw", "td", "win", "ven"]
    miss = [k for k in need if c[k] is None]
    if miss:
        st.error(f"matches.csv is missing columns for: {miss}. Columns found: {list(m.columns)}")
        st.stop()
 
    d = pd.DataFrame({
        "team1": to_team(m[c["t1"]]), "team2": to_team(m[c["t2"]]),
        "toss_winner": to_team(m[c["tw"]]), "winner": to_team(m[c["win"]]),
        "toss_decision": m[c["td"]].astype(str).str.lower().str.strip(),
    })
    d["date"] = pd.to_datetime(m[c["date"]], errors="coerce") if c["date"] else pd.NaT
    d["season"] = (m[c["season"]].astype(str) if c["season"] else d.date.dt.year.astype("Int64").astype(str))
    vk = m[c["ven"]].map(id2key) if pd.api.types.is_numeric_dtype(m[c["ven"]]) else m[c["ven"]].map(venue_key)
    d["venue"] = vk.map(lambda k: disp.get(k, k.title() if isinstance(k, str) else None))
    d["city"] = vk.map(city)
 
    d["toss_decision"] = d.toss_decision.replace({"bat": "bat", "field": "field", "bowl": "field"})
    d = d[d.toss_decision.isin(["bat", "field"])].copy()
    d["total_matches_raw"] = 1
    d["decided"] = d.winner.notna() & d.winner.isin(set(d.team1) | set(d.team2))
    d["bat_first"] = np.where(d.toss_decision == "bat", d.toss_winner,
                              np.where(d.toss_winner == d.team1, d.team2, d.team1))
    d["chase_win"] = np.where(d.decided, (d.winner != d.bat_first).astype(float), np.nan)
    d["toss_win_match"] = np.where(d.decided, (d.winner == d.toss_winner).astype(float), np.nan)
    return d.reset_index(drop=True)
 
 
def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    den = 1 + z**2 / n
    mid = (p + z**2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return p, mid - half, mid + half
 
 
def rate(series):
    s = series.dropna()
    return wilson(s.sum(), len(s))
 
 
def pct(x):
    return "n/a" if pd.isna(x) else f"{x*100:.0f}%"
 
 
df_all = load()
TOTAL = len(df_all)
 
# ----------------------------------------------------------------------------
# 2. FILTERS  (sidebar, so they are visible and apply on every tab)
# ----------------------------------------------------------------------------
st.sidebar.header("Filters")
seasons = sorted(df_all.season.unique())
sel_seasons = st.sidebar.multiselect("Season", seasons, default=seasons)
sel_toss = st.sidebar.radio("Toss winner chose to", ["Both", "bat", "field"], horizontal=True)
min_n = st.sidebar.slider("Minimum matches for a ranked list", 3, 30, 10)
 
df = df_all[df_all.season.isin(sel_seasons)]
if sel_toss != "Both":
    df = df[df.toss_decision == sel_toss]
dec = df[df.decided]
 
# ----------------------------------------------------------------------------
# 3. PAGE HEADER
# ----------------------------------------------------------------------------
st.title("Does the toss decide the match?")
st.caption(f"**{READER}.**")
if dec.empty:
    st.warning("No decided matches for this filter combination.")
    st.stop()
 
tab_over, tab_venue = st.tabs(["Overview", "Venue detail"])
 
# ============================ OVERVIEW =======================================
with tab_over:
    p_tw, lo, hi = rate(dec.toss_win_match)
    p_ch, _, _ = rate(dec.chase_win)
 
    c1, c2, c3 = st.columns(3)
    c1.metric("Matches in the data (all seasons, before any filter)", f"{TOTAL:,}",
              help=f"{len(dec):,} decided matches in the current filter")
    c2.metric("Toss winner also won the match", pct(p_tw),
              f"95% CI {pct(lo)}–{pct(hi)}, n={len(dec)}", delta_color="off")
    c3.metric("Chasing side won", pct(p_ch), f"n={len(dec)} decided matches", delta_color="off")
 
    # --- data for hero: chase win % by season
    s = (dec.groupby("season").chase_win.agg(["sum", "count"]).reset_index())
    s["rate"] = s["sum"] / s["count"] * 100
    hi_s, lo_s = s.loc[s.rate.idxmax()], s.loc[s.rate.idxmin()]
    hero = go.Figure(go.Scatter(x=s.season, y=s.rate, mode="lines+markers+text",
                                text=[f"n={n}" for n in s["count"]], textposition="top center",
                                line=dict(color=BLUE, width=3)))
    hero.add_hline(y=50, line_dash="dash", line_color=ORANGE, annotation_text="50% = no advantage")
    hero.update_layout(height=HERO_H, yaxis_title="Chasing side win %", xaxis_title=None,
                       yaxis_range=[0, 100], margin=dict(t=30))
    st.subheader(f"Chasing won most in {hi_s.season} ({hi_s.rate:.0f}%) and least in {lo_s.season} ({lo_s.rate:.0f}%)")
    st.caption(f"Share of decided matches won by the chasing side, per season. Labels show matches per season (n); {len(dec)} matches in total.")
    st.plotly_chart(hero, use_container_width=True)
 
    left, right = st.columns(2)
 
    # --- venue ranking (bar + table share data)
    v = dec.groupby(["venue"]).chase_win.agg(["sum", "count"]).reset_index()
    v = v[v["count"] >= min_n].copy()
    v["rate"] = v["sum"] / v["count"] * 100
    v = v.sort_values("rate", ascending=False)
    with left:
        if v.empty:
            st.info(f"No venue has {min_n}+ matches in this filter.")
        else:
            top, bot = v.iloc[0], v.iloc[-1]
            st.subheader(f"Chasing wins {top.rate:.0f}% at {top.venue} but only {bot.rate:.0f}% at {bot.venue}")
            st.caption(f"Venues with at least {min_n} decided matches. Number in brackets = matches.")
            vp = v.sort_values("rate")
            f = px.bar(vp, x="rate", y="venue", orientation="h",
                       text=[f"{r:.0f}%  (n={int(n)})" for r, n in zip(vp.rate, vp["count"])],
                       color_discrete_sequence=[BLUE])
            f.add_vline(x=50, line_dash="dash", line_color=ORANGE)
            f.update_layout(height=SMALL_H + 20 * max(0, len(vp) - 8), xaxis_title="Chasing win %",
                            yaxis_title=None, xaxis_range=[0, 100], margin=dict(t=10))
            st.plotly_chart(f, use_container_width=True)
 
    # --- team: win % when chasing vs defending
    long = pd.concat([
        dec.assign(team=dec.team1), dec.assign(team=dec.team2)])
    long["won"] = (long.winner == long.team).astype(int)
    long["role"] = np.where(long.bat_first == long.team, "Defending", "Chasing")
    t = long.groupby(["team", "role"]).won.agg(["sum", "count"]).reset_index()
    t = t[t["count"] >= min_n]
    t["rate"] = t["sum"] / t["count"] * 100
    with right:
        both = t.groupby("team").role.nunique()
        keep = both[both == 2].index
        t = t[t.team.isin(keep)]
        if t.empty:
            st.info(f"No team has {min_n}+ matches in both roles in this filter.")
        else:
            pv = t.pivot(index="team", columns="role", values="rate")
            pv["gap"] = pv.Chasing - pv.Defending
            b = pv.gap.idxmax()
            st.subheader(f"{b} win {pv.loc[b,'gap']:+.0f} points more often chasing than defending")
            st.caption(f"Teams with at least {min_n} matches in each role. Labels show win % (n).")
            f = px.bar(t, x="team", y="rate", color="role", barmode="group",
                       text=[f"{r:.0f}% (n={int(n)})" for r, n in zip(t.rate, t["count"])],
                       color_discrete_map={"Chasing": BLUE, "Defending": GREY})
            f.add_hline(y=50, line_dash="dash", line_color=ORANGE)
            f.update_layout(height=SMALL_H, yaxis_title="Win %", xaxis_title=None,
                            yaxis_range=[0, 100], margin=dict(t=10), legend_title=None)
            f.update_traces(textposition="outside", textfont_size=9)
            st.plotly_chart(f, use_container_width=True)
 
    # --- ranked table
    st.subheader("Venue ranking: where chasing is the safer call")
    st.caption(f"Ranked by chasing win %. Minimum {min_n} decided matches per venue.")
    if not v.empty:
        tbl = v.merge(dec[["venue", "city"]].drop_duplicates("venue"), on="venue", how="left")
        tbl = tbl.assign(Rank=range(1, len(tbl) + 1))[["Rank", "venue", "city", "count", "rate"]]
        tbl.columns = ["Rank", "Venue", "City", "Matches", "Chasing win %"]
        st.dataframe(tbl.style.format({"Chasing win %": "{:.0f}"}), hide_index=True, use_container_width=True)
 
# ============================ VENUE DETAIL ===================================
with tab_venue:
    counts = dec.venue.value_counts()
    if counts.empty:
        st.info("No venues available for this filter.")
        st.stop()
    venue = st.selectbox("Choose a venue", counts.index.tolist(),
                         format_func=lambda x: f"{x}  ({counts[x]} matches)")
    d = dec[dec.venue == venue]
    city_name = d.city.dropna().iloc[0] if d.city.notna().any() else ""
    st.caption(f"{venue} {('· ' + city_name) if city_name else ''}")
 
    p_c, clo, chi = rate(d.chase_win)
    p_t, tlo, thi = rate(d.toss_win_match)
    k1, k2, k3 = st.columns(3)
    k1.metric("Decided matches at this venue", len(d))
    k2.metric("Chasing side won", pct(p_c), f"95% CI {pct(clo)}–{pct(chi)}", delta_color="off")
    k3.metric("Toss winner also won", pct(p_t), f"95% CI {pct(tlo)}–{pct(thi)}", delta_color="off")
 
    # hero: team record at venue
    long = pd.concat([d.assign(team=d.team1), d.assign(team=d.team2)])
    long["won"] = (long.winner == long.team).astype(int)
    tv = long.groupby("team").won.agg(["sum", "count"]).reset_index()
    min_t = 3
    tv = tv[tv["count"] >= min_t].copy()
    tv["rate"] = tv["sum"] / tv["count"] * 100
    tv = tv.sort_values("rate")
    if tv.empty:
        st.info(f"No team has {min_t}+ matches here under this filter.")
    else:
        bt = tv.iloc[-1]
        st.subheader(f"{bt.team} are the strongest side here, winning {bt.rate:.0f}% of {int(bt['count'])} matches")
        st.caption(f"Win % by team at {venue}. Teams with at least {min_t} matches. Labels show win % (n).")
        f = px.bar(tv, x="rate", y="team", orientation="h",
                   text=[f"{r:.0f}% (n={int(n)})" for r, n in zip(tv.rate, tv["count"])],
                   color_discrete_sequence=[BLUE])
        f.add_vline(x=50, line_dash="dash", line_color=ORANGE)
        f.update_layout(height=HERO_H, xaxis_title="Win %", yaxis_title=None,
                        xaxis_range=[0, 100], margin=dict(t=10))
        st.plotly_chart(f, use_container_width=True)
 
    a, b2 = st.columns(2)
    with a:
        ss = d.groupby("season").chase_win.agg(["sum", "count"]).reset_index()
        ss["Chasing won"] = ss["sum"]
        ss["Defending won"] = ss["count"] - ss["sum"]
        lead = "chasing" if d.chase_win.mean() >= 0.5 else "defending"
        st.subheader(f"The {lead} side has won more often here across {len(ss)} seasons")
        st.caption(f"Matches won by chasing vs defending side, per season ({len(d)} matches).")
        f = px.bar(ss, x="season", y=["Chasing won", "Defending won"], barmode="stack",
                   color_discrete_sequence=[BLUE, GREY], text_auto=True)
        f.update_layout(height=SMALL_H, yaxis_title="Matches", xaxis_title=None,
                        legend_title=None, margin=dict(t=10))
        st.plotly_chart(f, use_container_width=True)
    with b2:
        td = d.groupby("toss_decision").toss_win_match.agg(["sum", "count"]).reset_index()
        td["rate"] = td["sum"] / td["count"] * 100
        td["label"] = td.toss_decision.map({"bat": "Chose to bat", "field": "Chose to field"})
        if len(td):
            w = td.loc[td.rate.idxmax()]
            st.subheader(f"Toss winners who {w.label.lower().replace('chose to ','chose to ')} won {w.rate:.0f}% here")
            st.caption("Match win % of the toss winner, by decision. Labels show win % (n).")
            f = px.bar(td, x="label", y="rate",
                       text=[f"{r:.0f}% (n={int(n)})" for r, n in zip(td.rate, td["count"])],
                       color_discrete_sequence=[BLUE])
            f.add_hline(y=50, line_dash="dash", line_color=ORANGE)
            f.update_layout(height=SMALL_H, yaxis_title="Toss winner win %", xaxis_title=None,
                            yaxis_range=[0, 100], margin=dict(t=10))
            st.plotly_chart(f, use_container_width=True)
 
    st.subheader(f"The {min(10, len(d))} most recent matches at {venue}")
    st.caption("Latest decided matches under the current filters.")
    rec = d.sort_values("date", ascending=False).head(10)
    rec = rec.assign(Date=rec.date.dt.date, Match=rec.team1 + " vs " + rec.team2,
                     **{"Toss": rec.toss_winner + " (" + rec.toss_decision + ")"})
    st.dataframe(rec[["Date", "season", "Match", "Toss", "winner"]]
                 .rename(columns={"season": "Season", "winner": "Winner"}),
                 hide_index=True, use_container_width=True)
 


