# WORKING - to do: implement polygon drawing on map to define area

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import geopandas as gpd
import json
from shapely.geometry import Polygon, Point
import numpy as np

# --- CONFIG ---
st.set_page_config(page_title="SUTRUK Leafletting Tracker", layout="wide")
if "batch" not in st.session_state:
    st.session_state.batch = []

# --- COUNTY SELECTION ---
st.title("📮 SUTRUK Leafletting Tracker")
county = st.selectbox("1️⃣ Choose your county:", ["Cambridgeshire", "Hertfordshire"])

# --- CONFIG LOOKUP ---
SHEET_CONFIG = {
    "Cambridgeshire": {
        "sheet_id": "1NoyMBvPgRx8_m4fJ7Mw6JrPo7R8pZMmOzbJ0fv3DFiU",
        "sheet_name": "cambs_wards_street_CEDs_pc_simplified",
        "geojson_path": "leafletting_app/data/cambs_pc_polygons.geojson",
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

# --- LOAD DATA ---
def load_data():
    return pd.DataFrame(sheet.get_all_records())

@st.cache_data(show_spinner=False)
def load_polygons(geojson_path):
    gdf = gpd.read_file(geojson_path)
    return gdf[~gdf["geometry"].isnull()]

# --- GET BUILT UP AREAS ---
data = load_data()
data["Built Up Area"] = data["Built Up Area"].astype(str).str.strip()
data["Postcode"] = data["Postcode"].astype(str).str.strip().str.upper()
built_up_areas = sorted(data["Built Up Area"].dropna().unique())

# --- BUILT UP AREA SELECTION ---
built_up_area = st.selectbox("2️⃣ Now select your Built Up Area:", built_up_areas)
area_data = data[data["Built Up Area"] == built_up_area].copy()

# --- LOAD POLYGONS AND MERGE ---
gdf = load_polygons(sheet_info["geojson_path"])
gdf["Postcode"] = gdf["Postcode"].astype(str).str.strip().str.upper()
merged = gdf.merge(area_data, on="Postcode", how="inner").drop_duplicates(subset=["Postcode"])

# --- SHOW MAP OF LEAFLETTED AREAS IN THIS BUILT-UP AREA ---
with st.expander("🗺️ Leafletted Areas in This Built Up Area", expanded=True):
    m = folium.Map(location=sheet_info["map_center"], zoom_start=12)
    folium.TileLayer("cartodbpositron").add_to(m)

    leafletted = merged[merged["Leafletted?"].isin(["✅", "❓"])]

    for _, row in leafletted.iterrows():
        fill_color = "green" if row["Leafletted?"] == "✅" else "orange"
        folium.GeoJson(
            row["geometry"].__geo_interface__,
            tooltip=f"{row['Postcode']} ({row['Leafletted?']})",
            style_function=lambda x, color=fill_color: {
                "fillColor": color,
                "color": color,
                "weight": 1,
                "fillOpacity": 0.5,
            },
        ).add_to(m)

    legend_html = '''
        <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; height: 90px;
                    border:2px solid grey; z-index:9999; font-size:14px;
                    background-color:white; padding: 10px;">
        <b>Legend</b><br>
        <i style="background:green; width:10px; height:10px; display:inline-block;"></i> ✅ Leafletted<br>
        <i style="background:orange; width:10px; height:10px; display:inline-block;"></i> ❓ Possibly leafletted<br>
        </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    folium_static(m, width=900, height=600)


# --- ZONE SELECTION BY POSTCODES ---
st.header("📍 Select an Area by 4 Postcodes in this Built Up Area")

postcodes_in_area = sorted(merged["Postcode"].unique())

with st.form("corner_selection_form"):
    col1, col2, col3, col4 = st.columns(4)
    corner1 = col1.selectbox("Corner 1", options=postcodes_in_area, key="corner1_form")
    corner2 = col2.selectbox("Corner 2", options=postcodes_in_area, key="corner2_form")
    corner3 = col3.selectbox("Corner 3", options=postcodes_in_area, key="corner3_form")
    corner4 = col4.selectbox("Corner 4", options=postcodes_in_area, key="corner4_form")
    submit_corners = st.form_submit_button("📦 Find Postcodes Inside Area")

selected_corners = [corner1, corner2, corner3, corner4]

if submit_corners:
    selected_geoms = merged[merged["Postcode"].isin(selected_corners)].geometry.centroid

    if len(selected_geoms) == 4:
        corner_coords = [(pt.x, pt.y) for pt in selected_geoms]
        center_x = np.mean([pt[0] for pt in corner_coords])
        center_y = np.mean([pt[1] for pt in corner_coords])
        center = Point(center_x, center_y)

        def angle_from_center(pt):
            return np.arctan2(pt[1] - center_y, pt[0] - center_x)

        corner_coords_sorted = sorted(corner_coords, key=angle_from_center)
        poly = Polygon(corner_coords_sorted)

        selected_in_poly = merged[merged.geometry.centroid.within(poly)]
        st.session_state.selected_in_poly = selected_in_poly  # ✅ Persist for later

        st.success(f"Found {len(selected_in_poly)} postcode areas inside selected region!")

        with st.expander("📌 View Selected Area on Map", expanded=True):
            m = folium.Map(location=sheet_info["map_center"], zoom_start=12)
            folium.TileLayer("cartodbpositron").add_to(m)

            folium.Polygon(
                locations=[(y, x) for x, y in corner_coords_sorted] + [(corner_coords_sorted[0][1], corner_coords_sorted[0][0])],
                color="blue", fill=True, fill_opacity=0.1, weight=2
            ).add_to(m)

            for _, row in selected_in_poly.iterrows():
                folium.GeoJson(
                    row["geometry"].__geo_interface__,
                    tooltip=row["Postcode"],
                    style_function=lambda x: {
                        "fillColor": "blue",
                        "color": "blue",
                        "weight": 1,
                        "fillOpacity": 0.4,
                    },
                ).add_to(m)

            folium_static(m, width=900, height=600)
    else:
        st.error(f"Please select 4 unique postcodes, {len(selected_geoms)} found")

# --- Show matching street preview and update button ---
if "selected_in_poly" in st.session_state:
    st.subheader("📝 Streets Inside Selected Polygon")
    street_matches = area_data[
        area_data["Postcode"].isin(st.session_state.selected_in_poly["Postcode"])
    ][["Postcode", "Roads"]].dropna()

    if not street_matches.empty:
        st.dataframe(street_matches.head(10), use_container_width=True)
    else:
        st.info("No matching streets found for selected postcodes.")

    if st.button("✅ Mark All These Postcodes as Leafletted"):
        updated_rows = 0
        for postcode in st.session_state.selected_in_poly["Postcode"].unique():
            matches = area_data[area_data["Postcode"] == postcode].index
            for idx in matches:
                try:
                    sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
                    updated_rows += 1
                except Exception as e:
                    st.error(f"Error updating {postcode}: {e}")
        if updated_rows > 0:
            st.success(f"✅ Updated {updated_rows} rows in the Google Sheet!")
            del st.session_state.selected_in_poly  # Reset to avoid duplicates
        else:
            st.warning("No matching postcodes found in sheet to update.")

# --- Data Entry Form ---
st.header("✅ Report Leafletted Streets")
st.subheader("3️⃣ Now select Streets, add Comment and Add to Batch")

filtered_streets = data[data["Built Up Area"] == built_up_area]["Roads"].dropna().unique()

with st.form("leafletting_form"):
    col1, col2 = st.columns(2)
    street = col1.selectbox("Street", options=sorted(filtered_streets) if len(filtered_streets) > 0 else ["No streets available"])
    comments = col2.text_area("Comments (optional)")
    add_to_batch = st.form_submit_button("➕ Add to Batch")

    if add_to_batch:
        st.session_state.batch.append({"Built Up Area": built_up_area, "Street": street, "Comments": comments})
        st.success(f"Added {street}, {built_up_area} to batch!")

# --- Show Batch Table ---
if st.session_state.batch:
    st.subheader("📝 Streets Ready to Submit:")
    batch_df = pd.DataFrame(st.session_state.batch)
    st.dataframe(batch_df, use_container_width=True)

    if st.button("📤 Submit All"):
        for entry in st.session_state.batch:
            built_up_area = entry["Built Up Area"]
            street = entry["Street"]
            comments = entry["Comments"]

            matching_indices = data[(data["Built Up Area"] == built_up_area) & (data["Roads"] == street)].index

            for idx in matching_indices:
                sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
                if comments:
                    sheet.update_cell(idx + 2, data.columns.get_loc("Comments") + 1, comments)

        st.success("✅ All streets submitted!")
        st.session_state.batch = []

        data = load_data()
        data["Built Up Area"] = data["Built Up Area"].astype(str).str.strip()
        data["Roads"] = data["Roads"].astype(str).str.strip()
        data["Postcode"] = data["Postcode"].astype(str).str.strip().str.upper()

# --- STATS SECTION ---
st.subheader("📊 Leafletting Summary")
leafletted_rows = data[data["Leafletted?"].isin(["✅", "❓"])]

if not leafletted_rows.empty:
    summary = leafletted_rows.groupby(["Built Up Area", "Roads"], dropna=True)["Households"].sum().reset_index()
    summary = summary.sort_values(by=["Built Up Area", "Roads"])
    total_households = summary["Households"].sum()

    st.markdown(f"**Total households leafletted:** {int(total_households):,}")
    st.dataframe(summary, use_container_width=True)
else:
    st.info("No streets have been marked as leafletted yet.")
