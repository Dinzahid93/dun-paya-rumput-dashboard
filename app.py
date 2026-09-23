import time

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium


# --------------------------------------------------
# APP SETTINGS
# --------------------------------------------------

st.set_page_config(
    page_title="DUN N13 Paya Rumput",
    page_icon="🗺️",
    layout="wide"
)

BOUNDARY_URL = (
    "https://lake.electiondata.my/maps/delimitations/"
    "peninsular_2018_dun.geojson"
)

MAP_CENTER = [2.287, 102.223]


# --------------------------------------------------
# LOAD DUN BOUNDARY
# --------------------------------------------------

@st.cache_data(ttl=86400)
def load_paya_rumput_boundary():
    response = requests.get(BOUNDARY_URL, timeout=60)
    response.raise_for_status()

    geojson = response.json()

    for feature in geojson["features"]:
        dun_name = str(feature["properties"].get("dun", ""))
        code_dun = str(feature["properties"].get("code_dun", ""))

        if "Paya Rumput" in dun_name or code_dun == "N.13":
            return feature

    return None


# --------------------------------------------------
# AUTO-FIND POLLING CENTRES
# --------------------------------------------------

@st.cache_data(ttl=86400)
def load_polling_centres():
    centres = [
        {"name": "SK Paya Rumput", "district": "Hujong Padang"},
        {"name": "SMK Paya Rumput", "district": "Hujong Padang"},
        {"name": "SK Krubong", "district": "Krubong"},
        {"name": "SMK Krubong", "district": "Krubong"},
        {
            "name": "Dewan Komuniti PPR Krubong",
            "district": "Krubong"
        },
        {"name": "SK Cheng", "district": "Pantai Cheng"},
        {
            "name": "SK Tanjung Minyak",
            "district": "Cheng Perdana"
        },
        {
            "name": "SMK Tun Haji Abdul Malek",
            "district": "Cheng"
        },
        {
            "name": "SK Tanjung Minyak 2",
            "district": "Tanjung Minyak"
        },
        {
            "name": "SRA JAIM Tanjung Minyak 2",
            "district": "Tanjung Minyak"
        },
    ]

    results = []

    for centre in centres:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": centre["name"] + ", Melaka, Malaysia",
                    "format": "jsonv2",
                    "limit": 1,
                },
                headers={
                    "User-Agent": "PayaRumputDashboard/1.0"
                },
                timeout=30,
            )

            data = response.json()

            if data:
                results.append(
                    {
                        "name": centre["name"],
                        "district": centre["district"],
                        "lat": float(data[0]["lat"]),
                        "lon": float(data[0]["lon"]),
                    }
                )

            # Respect free OpenStreetMap search service
            time.sleep(1)

        except Exception:
            pass

    return pd.DataFrame(results)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

boundary = load_paya_rumput_boundary()
polling_centres = load_polling_centres()


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

st.title("DUN N13 Paya Rumput")
st.caption(
    "Peta sempadan DUN, pusat mengundi dan ringkasan kawasan."
)


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.header("Kawalan peta")

    basemap = st.radio(
        "Pilih peta",
        ["Jalan", "Satelit"],
        horizontal=True
    )

    time_slot = st.selectbox(
        "Pilih masa",
        [
            "06:00-09:00",
            "09:00-12:00",
            "12:00-15:00",
            "15:00-18:00",
            "18:00-21:00",
            "21:00-00:00",
        ]
    )

    show_centres = st.checkbox(
        "Tunjuk pusat mengundi",
        value=True
    )

    st.divider()

    st.markdown(
        "[Buka Google Maps Traffic](https://www.google.com/maps/@2.287,102.223,13z/data=!5m1!1e1)"
    )

    st.caption(
        "Trafik Google dibuka dalam tab berasingan."
    )


# --------------------------------------------------
# SUMMARY METRICS
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Pemilih berdaftar", "26,455")
col2.metric("Daerah mengundi", "6")
col3.metric("Pusat mengundi", "10")
col4.metric("Keluar mengundi 2021", "66.2%")


# --------------------------------------------------
# TABS
# --------------------------------------------------

tab1, tab2, tab3 = st.tabs(
    ["Peta DUN", "Profil Pengundi", "Trafik"]
)


# --------------------------------------------------
# MAP TAB
# --------------------------------------------------

with tab1:
    st.subheader(f"Peta Paya Rumput: {time_slot}")

    peta = folium.Map(
        location=MAP_CENTER,
        zoom_start=13,
        tiles=None,
        control_scale=True
    )

    if basemap == "Jalan":
        folium.TileLayer(
            "OpenStreetMap",
            name="Jalan"
        ).add_to(peta)

    else:
        folium.TileLayer(
            tiles=(
                "https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            attr="Esri Satellite",
            name="Satelit"
        ).add_to(peta)

    # DUN boundary
    if boundary:
        folium.GeoJson(
            boundary,
            name="Sempadan DUN N13",
            style_function=lambda _: {
                "color": "#1565C0",
                "weight": 3,
                "fillColor": "#2196F3",
                "fillOpacity": 0.08,
            }
        ).add_to(peta)

    # Polling-centre pins
    if show_centres and not polling_centres.empty:
        for _, centre in polling_centres.iterrows():

            google_link = (
                f"https://www.google.com/maps?q="
                f"{centre['lat']},{centre['lon']}"
            )

            popup = f"""
            <b>{centre['name']}</b><br>
            Daerah mengundi: {centre['district']}<br><br>
            <a href="{google_link}" target="_blank">
            Open Google Maps
            </a>
            """

            folium.Marker(
                location=[centre["lat"], centre["lon"]],
                popup=popup,
                tooltip=centre["name"],
                icon=folium.Icon(
                    color="blue",
                    icon="flag"
                ),
            ).add_to(peta)

    folium.LayerControl(
        collapsed=False
    ).add_to(peta)

    st_folium(
        peta,
        height=650,
        use_container_width=True
    )

    if polling_centres.empty:
        st.warning(
            "Pusat mengundi belum berjaya ditemui secara automatik. "
            "Cuba refresh aplikasi sekali lagi."
        )
    else:
        st.success(
            f"{len(polling_centres)} pusat mengundi berjaya dipin secara automatik."
        )


# --------------------------------------------------
# VOTER PROFILE TAB
# --------------------------------------------------

with tab2:
    st.subheader("Profil pengundi keseluruhan DUN")

    left, middle, right = st.columns(3)

    with left:
        st.write("Jantina")

        st.bar_chart(
            pd.DataFrame(
                {"Peratus": [50.8, 49.2]},
                index=["Perempuan", "Lelaki"]
            )
        )

    with middle:
        st.write("Kaum")

        st.bar_chart(
            pd.DataFrame(
                {"Peratus": [61.0, 30.0, 6.4, 2.6]},
                index=[
                    "Melayu",
                    "Cina",
                    "India",
                    "Lain-lain"
                ]
            )
        )

    with right:
        st.write("Umur")

        st.bar_chart(
            pd.DataFrame(
                {
                    "Peratus": [
                        37.6,
                        20.9,
                        16.4,
                        13.0,
                        8.1,
                        3.1,
                        1.0,
                    ]
                },
                index=[
                    "18-29",
                    "30-39",
                    "40-49",
                    "50-59",
                    "60-69",
                    "70-79",
                    "80+",
                ]
            )
        )

    st.caption(
        "Data ini ialah ringkasan keseluruhan DUN Paya Rumput."
    )


# --------------------------------------------------
# TRAFFIC TAB
# --------------------------------------------------

with tab3:
    st.subheader("Trafik")

    st.write(
        "Belum ada rekod trafik sejarah dalam dashboard ini."
    )

    st.info(
        "Selepas ini kita boleh tambah lokasi pasar, restoran, dewan komuniti "
        "dan rekod trafik mengikut masa."
    )

    st.markdown(
        "[Lihat trafik semasa dalam Google Maps](https://www.google.com/maps/@2.287,102.223,13z/data=!5m1!1e1)"
    )
