import streamlit as st
import pandas as pd
import os
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
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)

SPREADSHEET_ID = "1_YxODw-hduZCLXE-vyaLBu5P0yKZjxQnWU6RCsvCvD0"
WORKSHEET_NAME = "CB_PE_wards_street_CEDs_pc_simplified"
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

# --- LOAD MASTER DATA ---
def load_data():
    data = pd.DataFrame(sheet.get_all_records())
    return data

# --- LOAD POLYGON GEOJSON ---
@st.cache_data(show_spinner=False)
def load_polygons():
    gdf = gpd.read_file("leafletting_app/data/CB_PE_postcodes_geometry_only.geojson")
    gdf = gdf[~gdf["geometry"].isnull()]
    return gdf

# --- FILTER POLYGONS BY LEAFLETTED ---
def filter_leafletted(gdf, data):
    marked_postcodes = data[data["Leafletted?"].isin(["✅", "❓"])] ["Postcode"].unique()
    return gdf[gdf["Postcode"].isin(marked_postcodes)]

# --- RENDER MAP ---
def render_map(data):
    gdf = load_polygons()
    leafletted_gdf = filter_leafletted(gdf, data)

    with st.expander("🗺️ View Map of Leafletted Areas", expanded=True):
        m = folium.Map(location=[52.2, 0.12], zoom_start=13)
        folium.TileLayer("cartodbpositron").add_to(m)

        for _, row in leafletted_gdf.iterrows():
            postcode = row["Postcode"]
            status = data[data["Postcode"] == postcode]["Leafletted?"].values[0]
            fill_color = "green" if status == "✅" else "orange"

            folium.GeoJson(
                row["geometry"].__geo_interface__,
                tooltip=f"{postcode} ({status})",
                style_function=lambda x, color=fill_color: {
                    "fillColor": color,
                    "color": color,
                    "weight": 1,
                    "fillOpacity": 0.5,
                },
            ).add_to(m)

        # Add a custom legend
        legend_html = '''
         <div style="position: fixed; 
                     bottom: 50px; left: 50px; width: 180px; height: 90px; 
                     border:2px solid grey; z-index:9999; font-size:14px;
                     background-color:white; padding: 10px;">
         <b>Legend</b><br>
         <i style="background:green; width:10px; height:10px; display:inline-block;"></i> ✅ Definitely leafletted<br>
         <i style="background:orange; width:10px; height:10px; display:inline-block;"></i> ❓ Possibly leafletted<br>
         </div> 
        '''
        m.get_root().html.add_child(folium.Element(legend_html))

        folium_static(m, width=900, height=600)

# --- STREAMLIT UI ---
st.title("📮 Leafletting Tracker")

data = load_data()
render_map(data)

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
            sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
            if comments:
                sheet.update_cell(idx + 2, data.columns.get_loc("Comments") + 1, comments)

        st.success(f"Marked {street}, {postcode} as leafletted!")

        # 🔄 Refresh map
        data = load_data()
        render_map(data)
