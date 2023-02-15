import altair as alt
import numpy
import pandas as pd
import pickle
import streamlit as st

# SET PAGE CONFIG TO WIDE MODE. ADD A TITLE AND FAVICON.
st.set_page_config(layout="wide", page_title="NHL SOS App", page_icon="🏒")

# LOAD DATA ONCE.
@st.experimental_singleton
def load_data():
    # Main SOS data.
    data = pd.read_csv("./data/sos.csv")

    # Season -> SOS data column lookup.
    with open("./data/seasons_lookup.pickle", mode="rb") as infile:
        col_from_season = pickle.load(infile)
        infile.close()

    # Team id -> Team name lookup.
    with open("./data/name_from_id.pickle", mode="rb") as f:
        name_from_id = pickle.load(f)
        f.close()

    # List of all seasons.
    seasons = list(col_from_season)

    return data, col_from_season, name_from_id, seasons

# FILTER DATA FOR A SPECIFIC SEASON.
@st.experimental_memo
def filterdata(df, selected_season):
    # Select a single season.
    season = df.iloc[:, col_from_season[selected_season]]
    # Keep only non-zero entries.
    season = season[season != 0]
    season = season.sort_values()
    # Convert numeric index to team names.
    season.name = "SOS"
    team_names = [name_from_id[id+1] for id in season.index.to_list()]
    team_names = pd.Series(team_names, index=season.index, name="Team")
    data = pd.concat([team_names, season], axis=1)
    return data

# BUILD HISTOGRAM.
@st.experimental_memo
def histdata():
    sos_data = numpy.genfromtxt("data/sos.csv", delimiter=',')
    non_zero_idxs = numpy.nonzero(sos_data)
    sos_array = numpy.array([])
    for idx in range(numpy.shape(non_zero_idxs)[1]):
        sos_array = numpy.append(sos_array, sos_data[non_zero_idxs[0][idx]][non_zero_idxs[1][idx]])
    hist = numpy.histogram(sos_array, bins=300)

    return pd.DataFrame({"SOS": hist[1][:-1], "Frequency": hist[0]})

# GET THE DATA.
data, col_from_season, name_from_id, seasons = load_data()

# CALCULATE DATA FOR THE HISTOGRAM.
chart_data = histdata()

# LAY OUT THE SECTIONS OF THE APP.
row1_1, row1_2 = st.columns((2, 3))
row2_1, row2_2 = st.columns((1, 4))

# WHEN THE SELECTBOX CHANGES UPDATE THE STATE.
def update_state():
    season_selected = st.session_state["sos_season"]

# DEFINE THE SECTIONS OF THE APP.
with row1_1:
    st.title("NHL Strength of Schedule Dashboard")
    season_selected = st.selectbox(
        "Select a season", seasons, key="sos_season", on_change=update_state
    )

with row1_2:
    st.write(
        f"""**Examine strength of schedule statistics across all {len(seasons)} NHL seasons and see how a given team's SOS compares to the historical average.**"""
    )
    st.write(
        f"""**A team's SOS indicates how easy or hard their given schedule was relative to the rest of the league. Higher values indicate harder schedules while 0.5 indicates averge difficulty. Read more about SOS [here](https://en.wikipedia.org/wiki/Strength_of_schedule).**"""
    )

with row2_1:
    df = filterdata(data, season_selected)
    st.write(df)

with row2_2:
    st.write(
        f"""**Distribution of SOS statistic across all seasons.**"""
    )

    st.altair_chart(
        alt.Chart(chart_data)
        .mark_area(
            interpolate="step-after",
        )
        .encode(
            x=alt.X("SOS:Q", scale=alt.Scale(nice=False)),
            y=alt.Y("Frequency:Q"),
            tooltip=["SOS", "Frequency"],
        )
        .configure_mark(opacity=0.2, color="red"),
        use_container_width=True,
    )
