import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

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


@st.cache_data(ttl=86400)
def load_paya_rumput_boundary():
    response = requests.get(BOUNDARY_URL, timeout=60)
    response.raise_for_status()

    geojson = response.json()

    for feature in geojson["features"]:
        dun_name = str(feature["properties"].get("dun", ""))

        if "Paya Rumput" in dun_name:
            return feature

    return None


st.title("DUN N13 Paya Rumput")
st.caption("Peta maklumat awam dan ringkasan kawasan.")

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

    st.divider()

    st.markdown(
        "[Buka Google Maps Traffic](https://www.google.com/maps/@2.287,102.223,13z/data=!5m1!1e1)"
    )

    st.caption(
        "Trafik Google dibuka dalam tab berasingan."
    )


col1, col2, col3, col4 = st.columns(4)

col1.metric("Pemilih berdaftar", "26,455")
col2.metric("Daerah mengundi", "6")
col3.metric("Pusat mengundi", "10")
col4.metric("Keluar mengundi 2021", "66.2%")


tab1, tab2, tab3 = st.tabs(
    ["Peta DUN", "Profil Pengundi", "Trafik"]
)


with tab1:
    st.subheader(f"Peta Paya Rumput: {time_slot}")

    map_data = load_paya_rumput_boundary()

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

    if map_data:
        folium.GeoJson(
            map_data,
            name="Sempadan DUN N13",
            style_function=lambda _: {
                "color": "#1565C0",
                "weight": 3,
                "fillColor": "#2196F3",
                "fillOpacity": 0.08,
            }
        ).add_to(peta)

    folium.LayerControl().add_to(peta)

    st_folium(
        peta,
        height=650,
        use_container_width=True
    )

    st.info(
        "Versi pertama ini memaparkan sempadan DUN dan pilihan peta jalan/satelit. "
        "Selepas ini kita tambah pusat mengundi, PDM, pasar dan lokasi komuniti."
    )


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
                index=["Melayu", "Cina", "India", "Lain-lain"]
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


with tab3:
    st.subheader("Trafik")

    st.write(
        "Belum ada rekod trafik sejarah dalam dashboard ini."
    )

    st.info(
        "Kita akan tambah fail trafik kemudian untuk simpan pemerhatian "
        "mengikut jalan, tarikh dan masa."
    )

    st.markdown(
        "[Lihat trafik semasa dalam Google Maps](https://www.google.com/maps/@2.287,102.223,13z/data=!5m1!1e1)"
    )
