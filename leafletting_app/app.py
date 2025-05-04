import streamlit as st
import pandas as pd
import os
import folium
from streamlit_folium import st_folium
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import geopandas as gpd
from io import StringIO
import json

# --- CONFIG ---
st.set_page_config(page_title="SUTRUK Leafletting Tracker", layout="wide")

# --- COUNTY SELECTION ---
st.title("📮 SUTRUK Leafletting Tracker")
county = st.selectbox("Choose your county:", ["Cambridgeshire", "Hertfordshire"])

# --- CONFIG LOOKUP ---
SHEET_CONFIG = {
    "Cambridgeshire": {
        "sheet_id": "1NoyMBvPgRx8_m4fJ7Mw6JrPo7R8pZMmOzbJ0fv3DFiU",
        "sheet_name": "cambs_wards_street_CEDs_pc_simplified",
        "geojson_path": "leafletting_app/data/cambs_pc_polygons.geojson"
    },
    "Hertfordshire": {
        "sheet_id": "1uIBFgGBVBozTM0mI4OriSlWdX3-r0HXbfqDwaUXMj9Q",
        "sheet_name": "herts_wards_street_CEDs_pc_simplified",
        "geojson_path": "leafletting_app/data/herts_pc_polygons.geojson"
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
def load_polygons(geojson_path):
    gdf = gpd.read_file(geojson_path)
    gdf = gdf.to_crs(epsg=27700)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=8, preserve_topology=True)
    gdf = gdf[
        gdf["geometry"].is_valid &
        gdf["geometry"].notnull() &
        ~gdf["geometry"].is_empty &
        gdf["geometry"].geom_type.isin(["Polygon", "MultiPolygon"])
    ].reset_index(drop=True)
    gdf = gdf.to_crs(epsg=4326)
    return gdf

# --- INITIALIZE SESSION STATE ---
if "batch" not in st.session_state:
    st.session_state.batch = []
if "selected_postcodes" not in st.session_state:
    st.session_state.selected_postcodes = set()
if "render_map" not in st.session_state:
    st.session_state.render_map = False

# --- LOAD DATA ---
data = load_data()
data["Built Up Area"] = data["Built Up Area"].astype(str).str.strip()
data["Roads"] = data["Roads"].astype(str).str.strip()
data["Postcode"] = data["Postcode"].astype(str).str.replace(" ", "").str.upper()

# --- USER SELECTS BUILT UP AREA ---
st.header("✅ Report Leafletted Streets")
st.subheader("1️⃣ Select Built Up Area")
built_up_area = st.selectbox("Built Up Area", options=sorted(data["Built Up Area"].dropna().unique()))
data_filtered = data[data["Built Up Area"] == built_up_area]

# --- SHOW MAP ONLY ON BUTTON CLICK ---
if st.button("🗺️ Show/Refresh Map"):
    st.session_state.render_map = True

if st.session_state.render_map:
    gdf = load_polygons(sheet_info["geojson_path"])
    gdf["Postcode"] = gdf["Postcode"].astype(str).str.replace(" ", "").str.upper()
    postcodes = data_filtered["Postcode"].unique()
    gdf_filtered = gdf[gdf["Postcode"].isin(postcodes)]
    del gdf  # cleanup

    st.subheader("🗺️ Interactive Map of Leafletted Areas")
    if not gdf_filtered.empty:
        m = folium.Map(location=[
            gdf_filtered.geometry.centroid.y.mean(),
            gdf_filtered.geometry.centroid.x.mean()
        ], zoom_start=13)
        folium.TileLayer("cartodbpositron").add_to(m)

        for _, row in gdf_filtered.iterrows():
            postcode = row["Postcode"]
            status = data_filtered[data_filtered["Postcode"] == postcode]["Leafletted?"].values
            status = status[0] if len(status) > 0 else ""
            fill_color = ("blue" if postcode in st.session_state.selected_postcodes
                          else "green" if status == "✅"
                          else "orange" if status == "❓" else "gray")

            folium.GeoJson(
                row["geometry"].__geo_interface__,
                tooltip=f"{postcode} ({status})",
                style_function=lambda x, color=fill_color: {
                    "fillColor": color,
                    "color": color,
                    "weight": 1,
                    "fillOpacity": 0.05,
                },
                name="Postcodes",
                highlight_function=lambda x: {"weight": 3, "color": "blue"},
            ).add_to(m)

        legend_html = '''
         <div style="position: fixed; 
                     bottom: 50px; left: 50px; width: 200px; height: 120px; 
                     border:2px solid grey; z-index:9999; font-size:14px;
                     background-color:white; padding: 10px;">
         <b>Legend</b><br>
         <i style="background:green; width:10px; height:10px; display:inline-block;"></i> ✅ Definitely leafletted<br>
         <i style="background:orange; width:10px; height:10px; display:inline-block;"></i> ❓ Possibly leafletted<br>
         <i style="background:blue; width:10px; height:10px; display:inline-block;"></i> Selected<br>
         </div> 
        '''
        m.get_root().html.add_child(folium.Element(legend_html))

        st_data = st_folium(m, width=900, height=600)

        clicked = st_data.get("last_clicked", {})
        if clicked:
            point = gpd.GeoSeries([gpd.points_from_xy([clicked["lng"]], [clicked["lat"]])[0]], crs="EPSG:4326")
            matches = gdf_filtered[gdf_filtered.geometry.contains(point[0])]
            if not matches.empty:
                clicked_pc = matches.iloc[0]["Postcode"]
                if clicked_pc in st.session_state.selected_postcodes:
                    st.session_state.selected_postcodes.remove(clicked_pc)
                else:
                    st.session_state.selected_postcodes.add(clicked_pc)
                st.rerun()
    else:
        st.warning("Please select a Built Up Area above to view the map.")

# --- STREET ENTRY FORM ---
st.subheader("2️⃣ Select Streets, Add Comment and Add to Batch")
filtered_streets = data_filtered["Roads"].dropna().unique()

with st.form("leafletting_form"):
    col1, col2 = st.columns(2)
    street = col1.selectbox("Street", options=sorted(filtered_streets) if len(filtered_streets) > 0 else ["No streets available"])
    comments = col2.text_area("Comments (optional)")
    add_to_batch = st.form_submit_button("➕ Add to Batch")
    if add_to_batch:
        st.session_state.batch.append({"Built Up Area": built_up_area, "Street": street, "Comments": comments})
        st.success(f"Added {street}, {built_up_area} to batch!")

if st.session_state.batch:
    st.subheader("📝 Streets Ready to Submit:")
    batch_df = pd.DataFrame(st.session_state.batch)
    st.dataframe(batch_df, use_container_width=True)

    if st.button("📤 Submit All Streets"):
        for entry in st.session_state.batch:
            bua = entry["Built Up Area"]
            street = entry["Street"]
            comments = entry["Comments"]
            matching_indices = data[(data["Built Up Area"] == bua) & (data["Roads"] == street)].index
            for idx in matching_indices:
                sheet.update_cell(idx + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
                if comments:
                    sheet.update_cell(idx + 2, data.columns.get_loc("Comments") + 1, comments)
        st.success("✅ All streets submitted!")
        st.session_state.batch = []
        st.session_state.render_map = False
        st.rerun()

selected_df = data_filtered[data_filtered["Postcode"].isin(st.session_state.selected_postcodes)]
if not selected_df.empty:
    st.subheader("📍 Postcodes Selected from Map")
    st.dataframe(selected_df[["Roads", "Postcode", "Built Up Area", "Households"]])

    if st.button("📤 Submit Selected Postcodes"):
        for _, row in selected_df.iterrows():
            idx = data[(data["Postcode"] == row["Postcode"])].index
            for i in idx:
                sheet.update_cell(i + 2, data.columns.get_loc("Leafletted?") + 1, "✅")
        st.success("✅ Postcodes submitted!")
        st.session_state.selected_postcodes.clear()
        st.session_state.render_map = False
        st.rerun()

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
