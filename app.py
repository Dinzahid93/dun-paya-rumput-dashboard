import io
import json
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.font_manager import findfont
from matplotlib.patches import Polygon as PlotPolygon
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)

BOUNDARY_URL = "https://lake.electiondata.my/maps/delimitations/peninsular_2018_dun.geojson"
PROFILE_URL = "https://electiondata.my/seats/dun/n13-paya-rumput-melaka/"
LIST_URL = "https://en.wikipedia.org/wiki/Paya_Rumput_(state_constituency)"
APAC = "https://www.apac.com.my/"
COLOURS = ["#0d9488", "#7c3aed", "#e07a12", "#db2777", "#2563eb", "#647c18"]
PDMS = ["Hujong Padang", "Krubong", "Pantai Cheng", "Cheng Perdana", "Cheng", "Tanjung Minyak"]
PDM_COLOUR = dict(zip(PDMS, COLOURS))

# Published/user-provided coordinates, NOT field-verified. Never snap points inside.
# Names/PDM assignments are a historical 2022 list, not a current SPR guarantee.
RAW = [
    (1, PDMS[0], "SK Paya Rumput", 2.294033, 102.216130, APAC + "mba2031-sk-paya-rumput.html"),
    (2, PDMS[0], "SMK Paya Rumput", 2.294138, 102.213694, APAC + "mea2103-smk-paya-rumput.html"),
    (3, PDMS[1], "SK Krubong / Kerubong", 2.299454, 102.254192, APAC + "mba2030-sk-kerubong.html"),
    (4, PDMS[1], "SMK Krubong", 2.319217, 102.245009, "https://emis.my/sekolah/sekolah-menengah-kebangsaan-krubong-melaka/"),
    (5, PDMS[1], "Dewan Komuniti PPR Krubong", None, None, "https://hallsakato.wixsite.com/dewanmelaka/dewan-komuniti"),
    (6, PDMS[2], "SK Cheng", 2.260514, 102.224581, APAC + "mba2029-sk-cheng.html"),
    (7, PDMS[3], "SK Tanjung Minyak", 2.266660, 102.215000, APAC + "mba2045-sk-tanjung-minyak.html"),
    (8, PDMS[4], "SMK Tun Haji Abd Malek", 2.266380, 102.213000, APAC + "mea2094-smk-tun-haji-abd-malek.html"),
    (9, PDMS[5], "SK Tanjung Minyak 2", 2.268481, 102.194046, APAC + "mba2048-sk-tanjung-minyak-2.html"),
    (10, PDMS[5], "SRA JAIM Tanjung Minyak 2", 2.265000921808834, 102.2005232181811, "https://www.google.com/maps/search/?api=1&query=2.265000921808834,102.2005232181811"),
]
ETHNICITY = ["Melayu", "Cina", "India", "Lain-lain", "Bumi Sabah", "Bumi Sarawak", "Orang Asli"]
ETHNIC_VALUES = [61.0, 30.0, 6.4, 1.9, 0.4, 0.2, 0.0]
AGES = ["18-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
AGE_VALUES = [37.6, 20.9, 16.4, 13.0, 8.1, 3.1, 1.0]
PALETTE = COLOURS + ["#9a6bba"]


def polygons(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError("Sempadan mesti Polygon atau MultiPolygon.")


def ring_position(x, y, ring):
    """0 outside, 1 inside, 2 on edge. Coordinates are longitude, latitude."""
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        x1, y1 = a[:2]
        x2, y2 = b[:2]
        cross = (x-x1)*(y2-y1) - (y-y1)*(x2-x1)
        if (abs(cross) < 1e-12 and min(x1,x2)-1e-10 <= x <= max(x1,x2)+1e-10
                and min(y1,y2)-1e-10 <= y <= max(y1,y2)+1e-10):
            return 2
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            inside = not inside
    return int(inside)


def covers(geometry, lat, lon):
    for poly in polygons(geometry):
        outer = ring_position(lon, lat, poly[0])
        holes = [ring_position(lon, lat, h) for h in poly[1:]]
        if outer == 2 or (outer == 1 and 1 not in holes):
            return True
    return False


def validate_boundary(data):
    features = data.get("features", [data])
    matches = [f for f in features if
               f.get("properties", {}).get("state") == "Melaka" and
               f["properties"].get("code_dun") == "N.13" and
               "Paya Rumput" in f["properties"].get("dun", "")]
    if len(matches) != 1:
        raise ValueError("Tidak jumpa tepat satu sempadan Melaka N.13 Paya Rumput.")
    feature = matches[0]
    coords = [p for poly in polygons(feature["geometry"]) for ring in poly for p in ring]
    if not coords or not all(101 < p[0] < 103 and 1 < p[1] < 3 for p in coords):
        raise ValueError("Koordinat sempadan tidak sah / bukan WGS84 Melaka.")
    return feature


def load_boundary():
    local = Path(__file__).with_name("boundary.geojson")
    if local.exists():
        return validate_boundary(json.loads(local.read_text(encoding="utf-8")))
    req = Request(BOUNDARY_URL, headers={"User-Agent": "PayaRumputPublicMap/3.0"})
    with urlopen(req, timeout=30) as response:
        return validate_boundary(json.load(response))


def audit_locations(boundary):
    df = pd.DataFrame(RAW, columns=["No", "PDM", "Lokasi", "Lat", "Lon", "Sumber"])
    def status(row):
        if pd.isna(row.Lat) or pd.isna(row.Lon):
            return "Tiada koordinat"
        return "Dalam polygon" if covers(boundary["geometry"], row.Lat, row.Lon) else "Luar polygon - semak"
    df["Semakan"] = df.apply(status, axis=1)
    df["Kualiti"] = df.Lat.apply(lambda x: "Belum ditentukan" if pd.isna(x) else "Direktori; belum semakan lapangan")
    df.loc[df.No == 10, "Kualiti"] = "Koordinat diberikan pengguna; belum disahkan bebas"
    df["Google Maps"] = df.Lokasi.apply(lambda n: "https://www.google.com/maps/search/?api=1&query=" + quote_plus(n + ", Melaka"))
    return df


def profile_figure():
    fig = Figure(figsize=(12, 8), facecolor="white", constrained_layout=True)
    axes = fig.subplots(2, 2)
    for ax, labels, values, title in [
        (axes[0,0], ETHNICITY, ETHNIC_VALUES, "Etnik (%)"),
        (axes[0,1], AGES, AGE_VALUES, "Kumpulan umur (%)"),
    ]:
        bars = ax.barh(labels, values, color=PALETTE)
        ax.bar_label(bars, labels=[f"{v:.1f}%" for v in values], padding=5, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, max(values)*1.24)
        ax.set_title(title, loc="left", fontweight="bold", pad=14)
        ax.spines[["top", "right", "bottom"]].set_visible(False)
        ax.tick_params(axis="x", bottom=False, labelbottom=False)
    axes[1,0].pie([50.8,49.2], labels=["Wanita", "Lelaki"], autopct="%.1f%%",
                  colors=["#db2777", "#0d9488"], startangle=90,
                  wedgeprops={"width":0.4, "edgecolor":"white"})
    axes[1,0].set_title("Jantina (%)", loc="left", fontweight="bold")
    ax = axes[1,1]
    ax.axis("off")
    ax.text(0, .90, "PROFIL SELURUH DUN", fontsize=16, fontweight="bold", color="#0f766e", va="top")
    ax.text(0, .72, "ElectionData.MY | GE-15 (2022)", fontsize=12, va="top")
    ax.text(0, .55, "Bukan pecahan PDM atau pusat mengundi.\nPenapis peta tidak mengubah carta ini.\nJumlah mungkin berbeza sedikit daripada\n100% akibat pembundaran sumber.", fontsize=11, linespacing=1.7, va="top")
    return fig


def overview_figure(boundary, shown):
    fig = Figure(figsize=(10, 7), facecolor="white", constrained_layout=True)
    ax = fig.subplots()
    for poly in polygons(boundary["geometry"]):
        ax.add_patch(PlotPolygon(poly[0], facecolor="#e0f2fe", edgecolor="#0369a1", linewidth=2))
        for hole in poly[1:]:
            ax.add_patch(PlotPolygon(hole, facecolor="white", edgecolor="#0369a1"))
    for _, r in shown.iterrows():
        colour = PDM_COLOUR[r.PDM]
        edge = "#dc2626" if r.Semakan.startswith("Luar") else "white"
        ax.scatter(r.Lon, r.Lat, s=95, c=colour, edgecolors=edge, linewidths=2, zorder=3)
        ax.annotate(str(r.No), (r.Lon,r.Lat), xytext=(6,6), textcoords="offset points", fontsize=9)
    ax.autoscale_view()
    ax.margins(.08)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude (WGS84)")
    ax.set_ylabel("Latitude (WGS84)")
    ax.set_title("Sempadan 2018 dan pin dipaparkan (nombor rujuk jadual)", loc="left")
    ax.grid(alpha=.15)
    return fig


def figure_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor="white")
    buf.seek(0)
    return buf


def make_pdf(boundary, selected, shown):
    buf = io.BytesIO()
    pdfmetrics.registerFont(TTFont("DejaVu",findfont("DejaVu Sans")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold",findfont("DejaVu Sans:weight=bold")))
    styles = getSampleStyleSheet()
    styles["BodyText"].fontName = "DejaVu"
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["Title"].fontName = "DejaVu-Bold"
    p = lambda text: Paragraph(text, styles["BodyText"])
    stamp = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).strftime("%d/%m/%Y %H:%M MYT")
    story = [Paragraph("N13 Paya Rumput | Peta & Audit", styles["Title"]),
             p(stamp), Spacer(1,12),
             p(f"{len(selected)} rekod dipilih; {len(shown)} pin dipaparkan. Senarai pusat: rujukan 2022."),
             p("Sempadan: ElectionData.MY, persempadanan 2018. Bukan pengesahan undang-undang atau ukuran lot."),
             Image(figure_bytes(overview_figure(boundary, shown)), width=490, height=343),
             p("Peta cetakan ialah rajah sempadan, bukan imej satelit. Bulatan berbingkai merah = luar polygon sumber."),
             p("Koordinat direktori belum disahkan di lapangan. Koordinat SRA JAIM Tanjung Minyak 2 diberikan pengguna, belum disahkan bebas. Dewan Komuniti PPR Krubong masih tiada koordinat."),
             PageBreak(), Paragraph("Senarai dan semakan lokasi", styles["Title"])]
    table = [["No", "Lokasi / PDM", "Koordinat / semakan"]]
    visible = set(shown.No)
    for _, r in selected.iterrows():
        coord = "Tiada" if pd.isna(r.Lat) else f"{r.Lat:.6f}, {r.Lon:.6f}"
        map_status = "Dipaparkan" if r.No in visible else "Tidak dipaparkan"
        table.append([str(r.No), p(escape(r.Lokasi)+"<br/>"+escape(r.PDM)+
                     f'<br/><a href="{escape(r.Sumber)}" color="blue">Sumber lokasi</a>'),
                     p(coord+"<br/>"+r.Semakan+"<br/>"+map_status)])
    t = Table(table, colWidths=[28,235,227], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0f766e")),
                          ("FONTNAME",(0,0),(-1,-1),"DejaVu"),
                          ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                          ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.whitesmoke,colors.white]),
                          ("VALIGN",(0,0),(-1,-1),"TOP"),
                          ("TOPPADDING",(0,0),(-1,-1),7),
                          ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [t, Spacer(1,12), p("Sumber senarai: "+LIST_URL),
              PageBreak(), Paragraph("Profil demografi seluruh DUN",styles["Title"]),
              Image(figure_bytes(profile_figure()), width=490,height=327),
              p("Sumber: "+PROFILE_URL),
              p("Data GE-15 (2022), bukan data semasa. Carta tidak ditapis mengikut PDM. Tiada anggaran piramid umur-jantina kerana nilai silang itu belum disahkan.")]
    SimpleDocTemplate(buf, rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=35).build(story)
    return buf.getvalue()


def build_map(boundary, audit):
    """All layer toggles run in Leaflet; no Python widgets or fit-on-toggle."""
    import folium
    m = folium.Map(location=[2.285,102.225],tiles=None,control_scale=True)
    folium.TileLayer("OpenStreetMap",name="Peta jalan",show=True).add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        name="Satelit (Esri)",show=False,
    ).add_to(m)
    layer = folium.GeoJson(
        boundary,name="Sempadan DUN · 2018",show=True,
        style_function=lambda f: {"color":"#06b6d4","weight":3,"fillOpacity":.07},
    ).add_to(m)
    groups = {}
    for pdm in PDMS:
        name = f'<span style="color:{PDM_COLOUR[pdm]}">●</span> {escape(pdm)}'
        groups[pdm] = folium.FeatureGroup(name=name,overlay=True,show=True).add_to(m)
    bounds = layer.get_bounds()
    for _,r in audit.dropna(subset=["Lat","Lon"]).iterrows():
        bounds[0][0] = min(bounds[0][0],r.Lat)
        bounds[0][1] = min(bounds[0][1],r.Lon)
        bounds[1][0] = max(bounds[1][0],r.Lat)
        bounds[1][1] = max(bounds[1][1],r.Lon)
        exact = f"https://www.google.com/maps/search/?api=1&query={r.Lat},{r.Lon}"
        popup = (f"<b>{r.No}. {escape(r.Lokasi)}</b><br>PDM: {escape(r.PDM)}"
                 f"<br>{r.Lat:.6f}, {r.Lon:.6f}"
                 f'<br><a href="{exact}" target="_blank">Buka koordinat ini</a>'
                 f'<br><a href="{r["Google Maps"]}" target="_blank">Cari nama di Google Maps</a>'
                 f'<details style="margin-top:8px"><summary>Maklumat sumber</summary>'
                 f'{escape(r.Semakan)}<br>{escape(r.Kualiti)}'
                 f'<br><a href="{r.Sumber}" target="_blank">Sumber</a></details>')
        folium.CircleMarker(
            [r.Lat,r.Lon],radius=9,weight=2,color="white",fill=True,
            fill_color=PDM_COLOUR[r.PDM],fill_opacity=1,
            tooltip=f"{r.No}. {r.Lokasi} | PDM: {r.PDM}",
            popup=folium.Popup(popup,max_width=330),
        ).add_to(groups[r.PDM])
    # Runs only when the map is first built, not on overlayadd/overlayremove.
    m.fit_bounds(bounds,padding=(25,25))
    folium.LayerControl(position="topright",collapsed=False).add_to(m)
    return m


def render_live_traffic(st, boundary):
    from streamlit.components.v1 import iframe
    points = [p for poly in polygons(boundary["geometry"]) for ring in poly for p in ring]
    lat = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
    lon = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    st.subheader("Trafik semasa · Paya Rumput")
    st.caption("Waze Live Map · Paparan keadaan semasa, bukan ramalan sepanjang hari.")
    src = f"https://embed.waze.com/iframe?zoom=14&lat={lat:.6f}&lon={lon:.6f}"
    iframe(src, height=720, scrolling=False)
    st.caption("Zum dan gerakkan peta untuk melihat jalan serta laporan yang tersedia. Tiada warna kesesakan tidak semestinya bermaksud jalan lancar. Ikon pengguna Waze bukan ukuran kesesakan.")
    with st.expander("Liputan & sumber"):
        st.write("Peta berpusat pada kawasan Paya Rumput, tetapi jalan berdekatan turut kelihatan. Waze mengawal kandungan dan kemas kini. Sempadan DUN tidak boleh ditindih atau digunakan untuk memotong iframe ini. Paparan ini tidak menyediakan pilihan masa lampau atau ramalan 06:00–00:00, dan tidak termasuk dalam PDF dashboard.")
        st.markdown("[Sumber: Waze Live Map](https://developers.google.com/waze/iframe)")


def main():
    import streamlit as st
    from streamlit_folium import st_folium

    st.set_page_config(page_title="Paya Rumput | Peta & Profil",page_icon="📍",layout="wide")
    st.markdown("""<style>
    .block-container{padding-top:2rem;max-width:1450px}
    [data-testid="stMetric"]{border:1px solid #cbd5e1;border-top:4px solid #0d9488;
    border-radius:12px;padding:14px}
    </style>""",unsafe_allow_html=True)
    st.title("📍 Paya Rumput")
    st.caption("N13 · Melaka · Simulasi trafik & maklumat kawasan · Versi 3.8")
    try:
        boundary = st.cache_data(ttl=86400)(load_boundary)()
    except Exception as exc:
        st.error(f"Sempadan gagal dimuatkan: {exc}")
        st.info("Muat naik boundary.geojson daripada pakej ke folder yang sama dengan app.py. Tiada sempadan atau pin simulasi digunakan.")
        st.stop()
    audit = audit_locations(boundary)

    traffic_tab, map_tab, graph_tab, audit_tab = st.tabs(["Simulasi trafik", "Peta", "Info DUN", "Audit & muat turun"])

    with map_tab:
        st.columns([1,3])[0].metric("PDM",len(PDMS))
        st.caption("Tick / untick PDM di penjuru kanan peta. Warna pin mengikut PDM.")
        m = build_map(boundary,audit)
        st_folium(m,height=650,use_container_width=True,returned_objects=[],key="paya_rumput_map_v32")
        st.caption("Pilihan PDM menukar pin sahaja, tanpa menetapkan semula zoom. Tukar Peta jalan / Satelit melalui panel yang sama.")

    with graph_tab:
        st.subheader("Profil seluruh DUN · GE-15 (2022)")
        st.pyplot(profile_figure(),use_container_width=True)
        st.markdown(f"[Sumber demografi: ElectionData.MY]({PROFILE_URL})")
        st.caption("Profil penduduk mengundi seluruh DUN; bukan demografi pengguna jalan atau pengunjung lokasi.")

    with traffic_tab:
        from simulation import render_simulation
        render_simulation(st, boundary)

    with audit_tab:
        st.info("Semakan sumber: 7 koordinat dalam polygon, 2 luar, 1 belum ditentukan. Koordinat dan sempadan kekal tidak diubah.")
        st.subheader("Semua 10 rekod — termasuk yang tiada pin")
        st.dataframe(audit,use_container_width=True,hide_index=True,
                     column_config={"Google Maps":st.column_config.LinkColumn("Google Maps"),
                                    "Sumber":st.column_config.LinkColumn("Sumber")})
        st.caption("SK Tanjung Minyak 2 dan SRA JAIM Tanjung Minyak 2: percanggahan dengan polygon sumber belum diselesaikan. Semak bangunan/pintu masuk dan sempadan beresolusi lebih tinggi; jangan alih pin untuk memaksanya masuk.")
        st.markdown(f"[Senarai pusat / PDM rujukan 2022]({LIST_URL}) · [Sempadan sumber]({BOUNDARY_URL})")
        st.download_button("Muat turun audit 10 lokasi",audit.to_csv(index=False).encode("utf-8-sig"),
                           file_name="audit_lokasi.csv",mime="text/csv")
        st.download_button("Muat turun peta interaktif",m.get_root().render().encode("utf-8"),
                           file_name="peta_paya_rumput.html",mime="text/html")
        st.download_button("Muat turun PDF semua PDM",make_pdf(boundary,audit,audit.dropna(subset=["Lat","Lon"])),
                           file_name="paya_rumput_report.pdf",mime="application/pdf")
        st.caption("PDF, CSV dan HTML mengandungi semua PDM, bukan pilihan tick sementara dalam peta. Carta demografi kekal seluruh DUN. Peta PDF ialah rajah sempadan tanpa satelit; HTML memerlukan internet untuk jubin peta.")


if __name__ == "__main__":
    main()
