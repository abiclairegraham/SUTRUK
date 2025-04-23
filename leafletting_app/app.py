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

# --- COUNTY SELECTION ---
st.title("📮 Leafletting Tracker")
county = st.selectbox("Choose your county:", ["Cambridgeshire", "Hertfordshire"])

# --- CONFIG LOOKUP ---
SHEET_CONFIG = {
    "Cambridgeshire": {
        "sheet_id": "1NoyMBvPgRx8_m4fJ7Mw6JrPo7R8pZMmOzbJ0fv3DFiU",
        "sheet_name": "cambs_wards_street_CEDs_pc_simplified",
        "geojson_path": "ting_app/data/cambs_pc_polygons.geojson",
        "map_center": [52.2, 0.12]
    },
    "Hertfordshire": {
        "sheet_id": "1uIBFgGBVBozTM0mI4OriSlWdX3-r0HXbfqDwaUXMj9Q",
        "sheet_name": "herts_wards_street_CEDs_pc_simplified",
        "geojson_path": "leafletting_app/data/herts_pc_polygons.geojson",
        "map_center": [51.8, -0.2]
    }
}

# --- GOOGLE SHEETS SETUP ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(credentials)

sheet_info = SHEET_CONFIG[county]
sheet = gc.open_by_key(sheet_info["sheet_id"]).worksheet(sheet_info["sheet_name"])

# --- LOAD MASTER DATA ---
def load_data():
    data = pd.DataFrame(sheet.get_all_records())
    return data

# --- LOAD POLYGON GEOJSON ---
@st.cache_data(show_spinner=False)
def load_polygons():
    gdf = gpd.read_file(sheet_info["geojson_path"])
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
        m = folium.Map(location=sheet_info["map_center"], zoom_start=12)
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

# --- MAIN FLOW ---
data = load_data()
render_map(data)

# Data Entry Form
st.subheader("✅ Report Leafletted Streets")

with st.form("leafletting_form"):
    col1, col2 = st.columns(2)

    built_up_area = col1.selectbox("Built Up Area", options=sorted(data["Built Up Area"].dropna().unique()))
    street = col2.selectbox("Street", options=sorted(data["Roads"].dropna().unique()))
    comments = st.text_area("Comments (optional)")

    submitted = st.form_submit_button("Submit")

    if submitted:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update the row in Google Sheets
        matching_indices = data[(data["Built Up Area"] == built_up_area) & (data["Roads"] == street)].index

        for idx in matching_indices:
            sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
            if comments:
                sheet.update_cell(idx + 2, data.columns.get_loc("Comments") + 1, comments)

        st.success(f"Marked {street}, {built_up_area} as leafletted!")

        # 🔄 Refresh map
        data = load_data()
        render_map(data)
