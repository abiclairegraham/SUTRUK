
 
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd
from io import BytesIO

st.set_page_config(layout="wide")

# --- Load full dataset ---
@st.cache_data
def load_data():
    #gdf = gpd.read_file("All_Fenland_wards_all_postcodes.geojson")
    gdf = gpd.read_file("CB_PE_selected_wards_all_postcodes.geojson")
    gdf["Population"] = pd.to_numeric(gdf["Population"], errors="coerce")
    gdf["Postcode"] = gdf["Postcode"].str.replace(" ", "").str.upper()
    return gdf

gdf_full = load_data()
gdf = gdf_full.copy()

# --- UI elements ---
st.title("📍 Build Your Own Cluster - Interactive Map")
st.markdown("Use the population shading to target high-population areas. Click postcode polygons to select them.")

# --- Dropdown to select division ---
if "County Electoral Division" in gdf.columns:
    divisions = sorted(gdf["County Electoral Division"].dropna().unique())
    selected_division = st.selectbox("Choose County Electoral Division:", divisions)
    gdf = gdf[gdf["County Electoral Division"] == selected_division].copy()

# --- Simplification slider ---
tolerance_m = st.slider("Simplification tolerance (meters):", 1, 100, 10, step=1)

# --- Simplify in metric CRS ---
gdf = gdf.to_crs(epsg=27700)
gdf["geometry"] = gdf["geometry"].simplify(tolerance=tolerance_m, preserve_topology=True)
gdf = gdf[
    gdf["geometry"].is_valid
    & gdf["geometry"].notnull()
    & ~gdf["geometry"].is_empty
    & gdf["geometry"].geom_type.isin(["Polygon", "MultiPolygon"])
].reset_index(drop=True)
gdf = gdf.to_crs(epsg=4326)

# --- Choropleth toggle ---
show_choropleth = st.checkbox("Show Population Choropleth", value=True)

# --- Selection state ---
if "selected_postcodes" not in st.session_state:
    st.session_state.selected_postcodes = set()

# --- Map setup ---
m = folium.Map(
    location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()],
    zoom_start=14,
    tiles="cartodbpositron"
)

# --- Choropleth layer ---
if show_choropleth:
    folium.Choropleth(
        geo_data=gdf,
        name="Population Heatmap",
        data=gdf,
        columns=["Postcode", "Population"],
        key_on="feature.properties.Postcode",
        fill_color="YlOrRd",
        fill_opacity=0.35,
        line_opacity=0.3,
        nan_fill_opacity=0,
        legend_name="Population"
    ).add_to(m)

# --- Polygon styling ---
def style_function(feature):
    postcode = feature['properties']['Postcode']
    if postcode in st.session_state.selected_postcodes:
        return {"fillColor": "#1f78b4", "color": "#0d47a1", "weight": 3, "fillOpacity": 0.4}
    else:
        return {"fillColor": "transparent", "color": "black", "weight": 1, "fillOpacity": 0.0}

folium.GeoJson(
    gdf,
    name="Postcodes",
    tooltip=folium.GeoJsonTooltip(fields=["Postcode", "Population", "Households"]),
    style_function=style_function,
    highlight_function=lambda x: {"weight": 3, "color": "blue"}
).add_to(m)

# --- Render map ---
st_data = st_folium(m, width=900, height=600)

# --- Download map as HTML ---
map_html = m.get_root().render()
map_bytes = BytesIO()
map_bytes.write(map_html.encode('utf-8'))
map_bytes.seek(0)
st.download_button("Download Map as HTML", data=map_bytes, file_name="custom_cluster_map.html", mime="text/html")

# --- Handle click ---
clicked = st_data.get("last_clicked", {})
if clicked:
    point = gpd.GeoSeries([gpd.points_from_xy([clicked["lng"]], [clicked["lat"]])[0]], crs="EPSG:4326")
    matches = gdf[gdf.geometry.contains(point[0])]
    if not matches.empty:
        clicked_pc = matches.iloc[0]["Postcode"]
        if clicked_pc in st.session_state.selected_postcodes:
            st.session_state.selected_postcodes.remove(clicked_pc)
        else:
            st.session_state.selected_postcodes.add(clicked_pc)
        st.rerun()

# --- Show selected postcodes + stats ---
st.subheader("Your Selected Postcodes")
selected_df = gdf[gdf["Postcode"].isin(st.session_state.selected_postcodes)]

if selected_df.empty:
    st.info("No postcodes selected yet. Click on polygons to start building your cluster.")
else:
    st.dataframe(selected_df[["Roads", "Postcode", "Population", "Households"]].sort_values("Roads"), use_container_width=True)
    st.markdown(f"**Total Population:** {int(selected_df['Population'].sum()):,}")
    st.markdown(f"**Total Households:** {int(selected_df['Households'].sum()):,}")
    csv = selected_df[["Roads", "Postcode", "Population", "Households"]].to_csv(index=False)
    st.download_button("Download Selected Area as CSV", csv, file_name="custom_cluster.csv", mime="text/csv")

# --- Clear selection ---
if st.button("Clear Selection"):
    st.session_state.selected_postcodes.clear()
    st.rerun()


