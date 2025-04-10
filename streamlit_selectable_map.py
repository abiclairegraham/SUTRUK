
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from io import BytesIO

st.set_page_config(layout="wide")

@st.cache_data

def load_data():
    gdf = gpd.read_file("Ely_postcode_clusters.geojson")
    return gdf

gdf = load_data()

st.title("📍 Build Your Own Cluster - Interactive Map")
st.markdown("Click postcode areas on the map to select them. Your custom cluster will appear below.")

# Convert to WGS84 for Folium
gdf = gdf.to_crs(epsg=4326)
st.write(gdf.head())
st.write(gdf.crs)

# --- Initialize session state for selected postcodes ---
if "selected_postcodes" not in st.session_state:
    st.session_state.selected_postcodes = set()

# --- Map Setup ---
m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=14, tiles="cartodbpositron")

# Add GeoJson layer with clickable polygons
def style_function(feature):
    postcode = feature['properties']['Postcode']
    if postcode in st.session_state.selected_postcodes:
        return {"fillColor": "#ff6e40", "color": "#ff3d00", "weight": 2, "fillOpacity": 0.7}
    else:
        return {"fillColor": "#2288bb", "color": "black", "weight": 1, "fillOpacity": 0.3}

# JavaScript to handle click events
click_js = """
function(feature, layer) {
    layer.on('click', function (e) {
        let selected = window.selected_postcodes || [];
        const pc = feature.properties.Postcode;
        const index = selected.indexOf(pc);
        if (index === -1) {
            selected.push(pc);
        } else {
            selected.splice(index, 1);
        }
        window.selected_postcodes = selected;
        layer.setStyle({fillColor: '#ff6e40', color: '#ff3d00', weight: 2, fillOpacity: 0.7});
    });
}
"""

folium.GeoJson(
    gdf,
    name="Postcodes",
    tooltip=folium.GeoJsonTooltip(fields=["Postcode", "Population", "Households"]),
    style_function=style_function,
    highlight_function=lambda x: {"weight": 3, "color": "red"},
    on_each_feature=click_js
).add_to(m)

st_data = st_folium(m, width=900, height=600)

# --- Collect clicked postcodes ---
clicked = st_data.get("last_active_drawing", {})

if clicked and "properties" in clicked:
    clicked_pc = clicked["properties"].get("Postcode")
    if clicked_pc:
        if clicked_pc in st.session_state.selected_postcodes:
            st.session_state.selected_postcodes.remove(clicked_pc)
        else:
            st.session_state.selected_postcodes.add(clicked_pc)

# --- Show selected postcodes + stats ---
st.subheader("Your Selected Postcodes")
selected_df = gdf[gdf["Postcode"].isin(st.session_state.selected_postcodes)]

if selected_df.empty:
    st.info("No postcodes selected yet. Click on polygons to start building your cluster.")
else:
    st.dataframe(selected_df[["Roads", "Postcode", "Population", "Households"]].sort_values("Roads"), use_container_width=True)

    st.markdown(f"**Total Population:** {int(selected_df['Population'].sum()):,}")
    st.markdown(f"**Total Households:** {int(selected_df['Households'].sum()):,}")

    # --- Download button ---
    csv = selected_df[["Roads", "Postcode", "Population", "Households"]].to_csv(index=False)
    st.download_button("Download Selected Area as CSV", csv, file_name="custom_cluster.csv", mime="text/csv")

# --- Clear selection ---
if st.button("Clear Selection"):
    st.session_state.selected_postcodes.clear()
    st.experimental_rerun()

