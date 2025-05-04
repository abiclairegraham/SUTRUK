import streamlit as st
import pandas as pd
import os
import folium
from streamlit\_folium import folium\_static
from datetime import datetime
import gspread
from oauth2client.service\_account import ServiceAccountCredentials
import geopandas as gpd
from io import StringIO
import json

# --- CONFIG ---

st.set\_page\_config(page\_title="SUTRUK Leafletting Tracker", layout="wide")

# --- COUNTY SELECTION ---

st.title("📮 SUTRUK Leafletting Tracker")
county = st.selectbox("Choose your county:", \["Cambridgeshire", "Hertfordshire"])

# --- CONFIG LOOKUP ---

SHEET\_CONFIG = {
"Cambridgeshire": {
"sheet\_id": "1NoyMBvPgRx8\_m4fJ7Mw6JrPo7R8pZMmOzbJ0fv3DFiU",
"sheet\_name": "cambs\_wards\_street\_CEDs\_pc\_simplified",
"geojson\_path": "leafletting\_app/data/cambs\_pc\_polygons.geojson",
"map\_center": \[52.2, 0.12]
},
"Hertfordshire": {
"sheet\_id": "1uIBFgGBVBozTM0mI4OriSlWdX3-r0HXbfqDwaUXMj9Q",
"sheet\_name": "herts\_wards\_street\_CEDs\_pc\_simplified",
"geojson\_path": "leafletting\_app/data/herts\_pc\_polygons.geojson",
"map\_center": \[51.8, -0.2]
}
}

# --- GOOGLE SHEETS SETUP ---

scope = \["[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)", "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"]
creds\_dict = json.loads(st.secrets\["GOOGLE\_SHEETS\_CREDENTIALS"])
credentials = ServiceAccountCredentials.from\_json\_keyfile\_dict(creds\_dict, scope)
gc = gspread.authorize(credentials)

sheet\_info = SHEET\_CONFIG\[county]
sheet = gc.open\_by\_key(sheet\_info\["sheet\_id"]).worksheet(sheet\_info\["sheet\_name"])

# --- LOAD MASTER DATA ---

def load\_data():
data = pd.DataFrame(sheet.get\_all\_records())
return data

# --- LOAD POLYGON GEOJSON ---

@st.cache\_data(show\_spinner=False)
def load\_polygons(geojson\_path):
gdf = gpd.read\_file(geojson\_path)
gdf = gdf\[\~gdf\["geometry"].isnull()]
return gdf

# --- FILTER POLYGONS BY LEAFLETTED ---

def filter\_leafletted(gdf, data):
marked\_postcodes = data\[data\["Leafletted?"].isin(\["✅", "❓"])] \["Postcode"].unique()
return gdf\[gdf\["Postcode"].isin(marked\_postcodes)]

# --- RENDER MAP ---

 def render_map(data):
    gdf = load_polygons(sheet_info["geojson_path"])
    leafletted_gdf = filter_leafletted(gdf, data)

    with st.expander("🗺️ View Map of Leafletted Areas", expanded=True):
        m = folium.Map(location=sheet_info["map_center"], zoom_start=12)
        folium.TileLayer("cartodbpositron").add_to(m)

        for _, row in leafletted_gdf.iterrows():
            postcode = row["Postcode"]
            status_values = data[data["Postcode"] == postcode]["Leafletted?"].values
            status = status_values[0] if len(status_values) > 0 else ""
            fill_color = "green" if status == "✅" else "orange"

            folium.GeoJson(
                row["geometry"].__geo_interface__,
                tooltip=folium.GeoJsonTooltip(
                    fields=[],
                    aliases=[],
                    labels=False,
                    sticky=False,
                    style=("background-color: white; color: black; font-weight: bold;"),
                    text=f"{postcode} ({status})"
                ),
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

if "batch" not in st.session\_state:
st.session\_state.batch = \[]

data = load\_data()
data\["Built Up Area"] = data\["Built Up Area"].astype(str).str.strip()
data\["Roads"] = data\["Roads"].astype(str).str.strip()
render\_map(data)

# --- Data Entry Form ---

st.header("✅ Report Leafletted Streets")
st.subheader("1️⃣ Select Built Up Area first")

built\_up\_area = st.selectbox("Built Up Area", options=sorted(data\["Built Up Area"].dropna().unique()))

st.subheader("2️⃣ Now select Streets, add Comment and Add to Batch")

filtered\_streets = data\[data\["Built Up Area"] == built\_up\_area]\["Roads"].dropna().unique()

with st.form("leafletting\_form"):
col1, col2 = st.columns(2)

```
street = col1.selectbox("Street", options=sorted(filtered_streets) if len(filtered_streets) > 0 else ["No streets available"])
comments = col2.text_area("Comments (optional)")

add_to_batch = st.form_submit_button("➕ Add to Batch")

if add_to_batch:
    st.session_state.batch.append({"Built Up Area": built_up_area, "Street": street, "Comments": comments})
    st.success(f"Added {street}, {built_up_area} to batch!")
```

# --- Show Batch Table ---

if st.session\_state.batch:
st.subheader("📝 Streets Ready to Submit:")
batch\_df = pd.DataFrame(st.session\_state.batch)
st.dataframe(batch\_df, use\_container\_width=True)

```
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

    # Refresh map
    data = load_data()
    data["Built Up Area"] = data["Built Up Area"].astype(str).str.strip()
    data["Roads"] = data["Roads"].astype(str).str.strip()
    render_map(data)
```

# --- STATS SECTION ---

st.subheader("📊 Leafletting Summary")
leafletted\_rows = data\[data\["Leafletted?"].isin(\["✅", "❓"])]

if not leafletted\_rows.empty:
summary = leafletted\_rows.groupby(\["Built Up Area", "Roads"], dropna=True)\["Households"].sum().reset\_index()
summary = summary.sort\_values(by=\["Built Up Area", "Roads"])
total\_households = summary\["Households"].sum()

```
st.markdown(f"**Total households leafletted:** {int(total_households):,}")
st.dataframe(summary, use_container_width=True)
```

else:
st.info("No streets have been marked as leafletted yet.")
