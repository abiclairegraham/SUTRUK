
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import pandas as pd

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

# Choropleth metric
metric_of_interest = 'cluster_population'

# Ensure clean formatting
subset[metric_of_interest] = pd.to_numeric(subset[metric_of_interest], errors='coerce')
subset['Postcode'] = subset['Postcode'].str.replace(" ", "").str.upper()

# Calculate map center from centroids
center = subset.to_crs(4326).geometry.centroid.unary_union.centroid
map_center = [center.y, center.x]

# Create the map
m = folium.Map(location=map_center, zoom_start=14, tiles='cartodbpositron')

# Add choropleth layer
folium.Choropleth(
    geo_data=subset,
    name=f"{metric_of_interest} Heatmap",
    data=subset,
    columns=["Postcode", metric_of_interest],
    key_on="feature.properties.Postcode",
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.3,
    nan_fill_opacity=0,
    legend_name=metric_of_interest.replace('_', ' ').title()
).add_to(m)

# Add boundary outlines with tooltips
folium.GeoJson(
    subset,
    name="Polygons",
    tooltip=folium.GeoJsonTooltip(fields=["Postcode", metric_of_interest])
).add_to(m)

folium.LayerControl().add_to(m)

# Show map
st_folium(m, width=750, height=500)

# --- Per-Cluster Table ---
st.subheader("Streets and Postcodes in This Cluster")

# Clean and sort table
table_df = subset[["Roads", "Postcode"]].drop_duplicates().sort_values(by="Roads")

# Display table
st.dataframe(table_df, use_container_width=True)

# Download button for selected cluster
csv = table_df.to_csv(index=False)
st.download_button("Download this cluster's streets as CSV", csv, file_name=f"cluster_{selected}_streets.csv", mime="text/csv")

# --- NEW: Full Data Table ---
st.subheader("All Clusters Overview")

full_table = gdf[[
    'Roads', 'Postcode', 'Population', 'Households', 'cluster',
    'cluster_population', 'cluster_households', 'cluster_max_distance_km'
]].sort_values(by=['cluster', 'Roads'])

st.dataframe(full_table, use_container_width=True)

# Download full table
full_csv = full_table.to_csv(index=False)
st.download_button("Download all cluster data as CSV", full_csv, file_name="all_clusters_overview.csv", mime="text/csv")
