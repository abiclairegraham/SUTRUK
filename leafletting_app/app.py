import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import geopandas as gpd
from io import StringIO
import json

# --- CONFIG ---
st.set_page_config(page_title="Leafletting Tracker", layout="wide")

# --- GOOGLE SHEETS SETUP ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# credentials = ServiceAccountCredentials.from_json_keyfile_name(".streamlit/credentials.json", scope)
# Load credentials from Streamlit secrets
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)

gc = gspread.authorize(credentials)

# Replace this with your actual Google Sheet name and worksheet name
SPREADSHEET_NAME = "LeaflettingMasterSheet"
WORKSHEET_NAME = "Sheet1"
sheet = gc.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)

# --- LOAD MASTER DATA ---
def load_data():
    data = pd.DataFrame(sheet.get_all_records())
    return data

# --- LOAD POLYGON GEOJSON ---
@st.cache_data

def load_polygons():
    gdf = gpd.read_file("data/postcode_polygons.geojson")
    return gdf

# --- FILTER POLYGONS BY LEAFLETTED ---
def filter_leafletted(gdf, data):
    done_postcodes = data[data["Leafletted?"] == "Yes"]["Postcode"].unique()
    return gdf[gdf["postcode"].isin(done_postcodes)]

# --- STREAMLIT UI ---
st.title("📮 Leafletting Tracker")

data = load_data()
gdf = load_polygons()
leafletted_gdf = filter_leafletted(gdf, data)

# Map
with st.expander("🗺️ View Map of Leafletted Areas", expanded=True):
    m = folium.Map(location=[52.2, 0.12], zoom_start=13)

    folium.TileLayer("cartodbpositron").add_to(m)

    for _, row in leafletted_gdf.iterrows():
        folium.GeoJson(
            row["geometry"].__geo_interface__,
            tooltip=row.get("postcode", "Unknown"),
            style_function=lambda x: {"fillColor": "green", "color": "green", "weight": 1, "fillOpacity": 0.5},
        ).add_to(m)

    folium_static(m, width=900, height=600)

# Data Entry Form
st.subheader("✅ Report Leafletted Streets")

with st.form("leafletting_form"):
    col1, col2 = st.columns(2)

    with col1:
        postcode = st.selectbox("Postcode", options=sorted(data["Postcode"].unique()))

    with col2:
        street = st.selectbox("Street", options=sorted(data["Roads"].dropna().unique()))

    comments = st.text_area("Comments (optional)")

    submitted = st.form_submit_button("Submit")

    if submitted:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update the row in Google Sheets
        matching_indices = data[(data["Postcode"] == postcode) & (data["Roads"] == street)].index

        for idx in matching_indices:
            sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "Yes")  # +2 for header + 1-indexing
            if comments:
                sheet.update_cell(idx + 2, data.columns.get_loc("Comments") + 1, comments)

        st.success(f"Marked {street}, {postcode} as leafletted!")
