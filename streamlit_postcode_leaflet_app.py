
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

@st.cache_data
def load_data():
    gdf = gpd.read_file("Ely_postcode_clusters.geojson")
    return gdf

gdf = load_data()

st.title("Ely Leaflet Clusters Dashboard")

cluster_ids = sorted(gdf["cluster"].unique())
selected = st.selectbox("Choose a cluster:", cluster_ids)

subset = gdf[gdf["cluster"] == selected]

st.subheader(f"Stats for Cluster {selected}")
st.write(f"Population: {int(subset['cluster_population'].iloc[0]):,}")
st.write(f"Households: {int(subset['cluster_households'].iloc[0]):,}")
st.write(f"Max Distance Across Cluster: {subset['cluster_max_distance_km'].iloc[0]:.2f} km")

m = folium.Map(location=[subset.geometry.centroid.y.mean(), subset.geometry.centroid.x.mean()], zoom_start=14)

folium.GeoJson(
    subset,
    tooltip=folium.GeoJsonTooltip(fields=["Postcode", "Population", "Households"]),
    style_function=lambda x: {"fillColor": "#3186cc", "color": "black", "weight": 1, "fillOpacity": 0.6}
).add_to(m)

st_folium(m, width=700, height=500)
