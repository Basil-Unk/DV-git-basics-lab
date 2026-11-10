# ============================================================
# COMPLETE FINAL APP.PY — Our World in Data Dashboard
# ============================================================

import os
import io
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import requests

st.set_page_config(page_title="OWID Development Dashboard", layout="wide")


@st.cache_data
def load_data():
    # 1) Load the OWID grapher CSV.
    #    OWID rejects the default urllib user-agent with HTTP 403, so fetch it
    #    with a browser user-agent and keep a local cache (data/ is gitignored).
    owid_url = "https://ourworldindata.org/grapher/life-expectancy-vs-gdp-per-capita.csv"
    cache_path = "data/owid_life_exp_vs_gdp.csv"

    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
    else:
        resp = requests.get(
            owid_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OWID-dashboard/1.0)"},
            timeout=60,
        )
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        os.makedirs("data", exist_ok=True)
        df.to_csv(cache_path, index=False)

    # 2) Rename the standard OWID columns
    df = df.rename(columns={"Entity": "country", "Year": "year"})

    # 3) Auto-detect the indicator columns
    #    (OWID renamed these columns in the live CSV, so match on the
    #     normalised header text instead of one hard-coded spelling)
    def find(*needles):
        for c in df.columns:
            key = c.lower().replace(" ", "_")
            if all(n in key for n in needles):
                return c
        raise KeyError(f"No column matching {needles}; have {list(df.columns)}")

    life_col = find("life", "expectancy")
    gdp_col = find("gdp", "per_capita")
    df = df.rename(columns={life_col: "lifeExp", gdp_col: "gdpPercap"})
    df["year"] = df["year"].astype(int)

    # 4) OWID does not always ship continent/population with this CSV,
    #    so merge Gapminder's country metadata to keep the same structure.
    gapminder = px.data.gapminder()

    # Continent mapping
    continent_map = gapminder[["country", "continent"]].drop_duplicates()
    df = df.merge(continent_map, on="country", how="left")

    # Population by country-year (allows bubble sizing).
    # Prefer OWID's own Population column when present, else use Gapminder.
    if "Population" not in df.columns:
        pop_map = gapminder[["country", "year", "pop"]]
        df = df.merge(pop_map, on=["country", "year"], how="left")
    else:
        df = df.rename(columns={"Population": "pop"})

    # 5) Keep only rows that have everything we need for the dashboard
    df = df.dropna(subset=["lifeExp", "gdpPercap", "continent", "pop"])
    return df


df = load_data()

st.title("Country Development Dashboard — OWID Dataset")

# ---- SIDEBAR FILTERS ----
st.sidebar.header("Filters")

years = sorted(df["year"].unique())
selected_year = st.sidebar.select_slider("Year", options=years, value=years[-1])

continents = sorted(df["continent"].unique())
selected_continents = st.sidebar.multiselect("Continent", continents, default=continents)

# Third filter: minimum population
min_pop = int(df["pop"].min())
max_pop = int(df["pop"].max())

selected_min_pop = st.sidebar.slider("Minimum Population", min_pop, max_pop, value=min_pop)

filtered_df = df[
    (df["year"] == selected_year) &
    (df["continent"].isin(selected_continents)) &
    (df["pop"] >= selected_min_pop)
]

# ---- KPI CARDS (Median carried over from Task 4.1) ----
col1, col2, col3 = st.columns(3)
col1.metric("Countries shown", f"{filtered_df['country'].nunique()}")
col2.metric("Median life expectancy", f"{filtered_df['lifeExp'].median():.1f} yrs")
col3.metric("Total population", f"{filtered_df['pop'].sum()/1e9:.2f} B")

# ---- MAIN SCATTER CHART ----
fig = px.scatter(
    filtered_df,
    x="gdpPercap", y="lifeExp", size="pop", color="continent",
    hover_name="country", log_x=True, size_max=60,
    title=f"GDP per Capita vs Life Expectancy - {selected_year} (OWID)"
)
st.plotly_chart(fig, use_container_width=True)

# ---- DRILL-DOWN LINE CHART ----
st.subheader("Drill down into a country")
country_pick = st.selectbox("Choose a country", sorted(filtered_df["country"].unique()))
country_hist = df[df["country"] == country_pick]
fig2 = px.line(
    country_hist, x="year", y="lifeExp", markers=True,
    title=f"Life Expectancy over time - {country_pick}"
)
st.plotly_chart(fig2, use_container_width=True)
