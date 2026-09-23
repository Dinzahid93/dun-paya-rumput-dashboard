import json
from datetime import datetime
from urllib.parse import quote_plus

import folium
import pandas as pd
import requests
import streamlit as st
from fpdf import FPDF
from streamlit_folium import st_folium


st.set_page_config(
    page_title="DUN N13 Paya Rumput",
    page_icon="📍",
    layout="wide"
)

BOUNDARY_URL = (
    "https://lake.electiondata.my/maps/delimitations/"
    "peninsular_2018_dun.geojson"
)

# Fixed locations. No automatic internet geocoding.
# "Semak" means approximate / needs one visual confirmation on Google Maps.
POLLING_CENTRES = [
    {
        "pdm": "136/13/01 Hujong Padang",
        "name": "SK Paya Rumput",
        "lat": 2.294033,
        "lon": 102.216130,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/01 Hujong Padang",
        "name": "SMK Paya Rumput",
        "lat": 2.294138,
        "lon": 102.213694,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/02 Krubong",
        "name": "SK Krubong",
        "lat": 2.299470,
        "lon": 102.254610,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/02 Krubong",
        "name": "SMK Krubong",
        "lat": 2.319217,
        "lon": 102.245009,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/02 Krubong",
        "name": "Dewan Komuniti PPR Krubong",
        "lat": 2.283209,
        "lon": 102.234791,
        "status": "Semak di Google Maps",
    },
    {
        "pdm": "136/13/03 Pantai Cheng",
        "name": "SK Cheng",
        "lat": 2.260514,
        "lon": 102.224581,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/04 Cheng Perdana",
        "name": "SK Tanjung Minyak",
        "lat": 2.266660,
        "lon": 102.215000,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/05 Cheng",
        "name": "SMK Tun Haji Abdul Malek",
        "lat": 2.266380,
        "lon": 102.213000,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/06 Tanjung Minyak",
        "name": "SK Tanjung Minyak 2",
        "lat": 2.268481,
        "lon": 102.194046,
        "status": "Disahkan",
    },
    {
        "pdm": "136/13/06 Tanjung Minyak",
        "name": "SRA JAIM Tanjung Minyak 2",
        "lat": 2.269100,
        "lon": 102.195000,
        "status": "Semak di Google Maps",
    },
]


@st.cache_data(ttl=86400)
def get_n13_boundary():
    response = requests.get(BOUNDARY_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    for feature in data["features"]:
        props = feature.get("properties", {})
        if (
            props.get("state") == "Melaka"
            and props.get("code_dun") == "N.13"
            and props.get("dun") == "N.13 Paya Rumput"
        ):
            return feature

    return None


def geojson_bounds(geometry):
    points = []

    def collect(item):
        if isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[0], (int, float)):
                points.append(item)
            else:
                for child in item:
                    collect(child)

    collect(geometry["coordinates"])

    lats = [point[1] for point in points]
    lons = [point[0] for point in points]

    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def make_pdf(centres):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DUN N13 Paya Rumput - Senarai Lokasi", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        7,
        f"Dicetak: {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(45, 8, "PDM", border=1)
    pdf.cell(90, 8, "Pusat Mengundi", border=1)
    pdf.cell(45, 8, "Status Koordinat", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    for centre in centres:
        pdf.cell(45, 8, centre["pdm"][:27], border=1)
        pdf.cell(90, 8, centre["name"][:52], border=1)
        pdf.cell(45, 8, centre["status"], border=1, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


st.title("📍 DUN N13 Paya Rumput")
st.caption("Peta pusat mengundi, sempadan DUN dan senarai lokasi untuk kerja lapangan.")

df = pd.DataFrame(POLLING_CENTRES)

col1, col2, col3 = st.columns(3)
col1.metric("PDM", "6")
col2.metric("Pusat mengundi", len(df))
col3.metric("Lokasi disahkan", int((df["status"] == "Disahkan").sum()))

with st.sidebar:
    st.header("Tetapan peta")
    basemap = st.radio("Pilih paparan", ["Peta jalan", "Satelit"])
    show_boundary = st.checkbox("Papar sempadan DUN N13", value=True)
    show_check_locations = st.checkbox(
        "Papar lokasi perlu semak", value=True
    )
    selected_pdms = st.multiselect(
        "Tapis PDM",
        options=sorted(df["pdm"].unique()),
        default=sorted(df["pdm"].unique()),
    )

filtered = df[df["pdm"].isin(selected_pdms)].copy()

if not show_check_locations:
    filtered = filtered[filtered["status"] == "Disahkan"]

try:
    boundary = get_n13_boundary()
except Exception:
    boundary = None

peta = folium.Map(
    location=[2.285, 102.225],
    zoom_start=13,
    tiles=None,
    control_scale=True,
)

if basemap == "Peta jalan":
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Peta jalan",
        control=False,
    ).add_to(peta)
else:
    folium.TileLayer(
        tiles="https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Satelit",
        subdomains=["mt0", "mt1", "mt2", "mt3"],
        control=False,
    ).add_to(peta)

if show_boundary and boundary:
    folium.GeoJson(
        boundary,
        name="Sempadan DUN N13",
        style_function=lambda _: {
            "fillColor": "#2563eb",
            "color": "#1d4ed8",
            "weight": 3,
            "fillOpacity": 0.08,
        },
        tooltip="Sempadan DUN N13 Paya Rumput",
    ).add_to(peta)

    # This is what the old code was missing:
    # force map to zoom to the N13 boundary.
    peta.fit_bounds(geojson_bounds(boundary["geometry"]))

for _, centre in filtered.iterrows():
    is_verified = centre["status"] == "Disahkan"
    colour = "blue" if is_verified else "orange"
    icon_name = "flag" if is_verified else "question-sign"

    google_link = (
        "https://www.google.com/maps/search/?api=1&query="
        + quote_plus(centre["name"] + ", Melaka")
    )

    popup_html = f"""
    <b>{centre["name"]}</b><br>
    <b>PDM:</b> {centre["pdm"]}<br>
    <b>Status:</b> {centre["status"]}<br><br>
    <a href="{google_link}" target="_blank">
        Buka / sahkan dalam Google Maps
    </a>
    """

    folium.Marker(
        location=[centre["lat"], centre["lon"]],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=centre["name"],
        icon=folium.Icon(color=colour, icon=icon_name, prefix="glyphicon"),
    ).add_to(peta)

st.subheader("Peta N13")
st.info(
    "Biru = koordinat disahkan. Oren = lokasi anggaran; klik pin dan "
    "buka Google Maps untuk sahkan sebelum gunakan."
)
st_folium(peta, height=620, use_container_width=True)

st.subheader("10 pusat mengundi")
show_df = filtered[["pdm", "name", "status", "lat", "lon"]].rename(
    columns={
        "pdm": "PDM",
        "name": "Pusat mengundi",
        "status": "Status",
        "lat": "Latitude",
        "lon": "Longitude",
    }
)
st.dataframe(show_df, use_container_width=True, hide_index=True)

csv = show_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Muat turun senarai CSV",
    data=csv,
    file_name="pusat_mengundi_n13_paya_rumput.csv",
    mime="text/csv",
)

st.download_button(
    "Muat turun senarai PDF",
    data=make_pdf(filtered.to_dict("records")),
    file_name="pusat_mengundi_n13_paya_rumput.pdf",
    mime="application/pdf",
)
