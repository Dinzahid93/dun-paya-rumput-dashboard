"""Public historical incident snapshots; never infer speeds or missing hours."""
import json
from html import escape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

LEVELS = {1: ("Kecil", "#eab308"), 2: ("Sederhana", "#f97316"),
          3: ("Besar", "#dc2626")}


def load_snapshots(boundary, covers):
    data = json.loads(Path(__file__).with_name("traffic_snapshots.json").read_text())
    result = []
    for snapshot in data:
        local = datetime.fromisoformat(snapshot["observed_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
        rows = []
        for incident in snapshot["incidents"]:
            lat, lon = incident.get("lat"), incident.get("lon")
            if lat is None or lon is None or not covers(boundary["geometry"], lat, lon):
                continue
            # Early collector versions mislabelled category 6 as Accident.
            # Use the numeric TomTom category, not that erroneous label.
            if incident.get("cat") != 6:
                continue
            level, color = LEVELS.get(incident.get("delay"), ("Tidak diketahui", "#64748b"))
            rows.append({"Masa MYT": local.isoformat(), "Dari": incident.get("from", ""),
                         "Ke": incident.get("to", ""), "Tahap kelewatan": level,
                         "Lat": lat, "Lon": lon, "Warna": color,
                         "Sumber": snapshot["source_url"]})
        result.append({"hour": local.hour, "label": local.strftime("%d/%m/%Y · %H:%M:%S MYT"),
                       "rows": rows, "source": snapshot["source_url"]})
    return result


def traffic_html(boundary, snapshots):
    import folium
    from branca.element import MacroElement, Template

    m = folium.Map(tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        name="Satelit", overlay=False).add_to(m)
    boundary_layer = folium.GeoJson(boundary, name="Sempadan DUN · 2018",
        style_function=lambda f: {"color": "#06b6d4", "weight": 3, "fillOpacity": .03}).add_to(m)
    m.fit_bounds(boundary_layer.get_bounds())
    folium.LayerControl(collapsed=False).add_to(m)
    records = []
    for snapshot in snapshots:
        points = []
        for r in snapshot["rows"]:
            popup = (f'<b>{escape(r["Dari"])}</b><br>Ke: {escape(r["Ke"])}'
                     f'<br>Kelewatan: {escape(r["Tahap kelewatan"])}'
                     f'<br>{escape(snapshot["label"])}'
                     f'<br><a href="https://www.google.com/maps/search/?api=1&query={r["Lat"]},{r["Lon"]}" target="_blank" rel="noopener">Google Maps</a>')
            points.append({"lat": r["Lat"], "lon": r["Lon"], "color": r["Warna"], "popup": popup})
        records.append({"hour": snapshot["hour"], "label": snapshot["label"], "points": points})
    control = MacroElement()
    control.data = json.dumps(records).replace("<", "\\u003c")
    control._template = Template('''{% macro script(this, kwargs) %}
    (function () {
      const map = {{this._parent.get_name()}}, data = {{this.data | safe}};
      const dots = L.layerGroup().addTo(map);
      const Control = L.Control.extend({onAdd: function () {
        const div = L.DomUtil.create('div');
        div.style.cssText = 'background:white;color:#172554;padding:14px;border-radius:10px;max-width:290px;box-shadow:0 2px 12px #0003;font:14px Arial';
        div.innerHTML = '<b>Trafik lampau · 15 Ogos 2026</b><br><label>Jam MYT: <b class="hour"></b><input aria-label="Jam trafik MYT" type="range" min="6" max="24" step="1" value="19" style="display:block;width:260px;margin:12px 0"></label><p class="status" style="line-height:1.5"></p><small>🟡 Kecil · 🟠 Sederhana · 🔴 Besar<br>⚪ Tahap tidak diketahui<br>Warna = kelewatan insiden, bukan jumlah kereta.</small>';
        L.DomEvent.disableClickPropagation(div); L.DomEvent.disableScrollPropagation(div);
        const slider = div.querySelector('input');
        function update() {
          const hour = Number(slider.value); dots.clearLayers();
          div.querySelector('.hour').textContent = hour === 24 ? '00:00 (16 Ogos)' : String(hour).padStart(2,'0') + ':00';
          const selected = data.filter(s => s.hour === hour);
          div.querySelector('.status').textContent = selected.length
            ? selected.map(s => 'Rekod ' + s.label + ' · ' + s.points.length + ' titik').join(' / ') + '. Bukan purata seluruh jam.'
            : 'Tiada rekod untuk jam ini. Ini tidak bermaksud jalan lancar.';
          selected.forEach(s => s.points.forEach(p => L.circleMarker([p.lat,p.lon], {
            radius:9,color:'white',weight:2,fill:true,fillColor:p.color,fillOpacity:1
          }).bindPopup(p.popup).addTo(dots)));
        }
        slider.addEventListener('input',update); update(); return div;
      }});
      new Control({position:'bottomleft'}).addTo(map);
    })();
    {% endmacro %}''')
    m.add_child(control)
    return m.get_root().render()


def render_traffic(st, boundary, covers):
    from streamlit.components.v1 import html
    st.subheader("Trafik lampau")
    st.info("Arkib terhad: 15 Ogos 2026, 18:40 dan 19:01 MYT sahaja. Belum ada siri setahun / ramalan 06:00–00:00.")
    try:
        snapshots = load_snapshots(boundary, covers)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Fail trafik gagal dibaca: {exc}. Muat naik traffic_snapshots.json bersama app.py.")
        return
    page = traffic_html(boundary, snapshots)
    html(page, height=690)
    st.caption("Gerakkan masa di dalam peta tanpa muat semula. Titik ialah lokasi rujukan insiden dalam sempadan; sumber tidak menyimpan garisan jalan penuh, kelajuan atau bilangan kenderaan. Jalan tanpa titik tidak semestinya lancar.")
    rows = [r for snapshot in snapshots for r in snapshot["rows"]]
    frame = pd.DataFrame(rows).drop(columns=["Warna"], errors="ignore")
    with st.expander("Rekod & sumber trafik"):
        st.dataframe(frame, hide_index=True, use_container_width=True)
        st.markdown("Sumber: **TomTom**, melalui [repositori awam mygov](https://github.com/mfaizalzain/mygov). Kod pengumpul berlesen MIT; lesen kod tidak menjadikan data TomTom data terbuka berlesen MIT. Tiada API key diperlukan untuk membaca snapshot yang dibekalkan.")
        st.caption("Snapshot 19:01 menggunakan versi pembetulan terakhir dan mempunyai had 40 insiden untuk seluruh Melaka. Snapshot 18:40 tiada tahap kelewatan. Label kategori lama dibetulkan menggunakan kod rasmi TomTom: 6 = kesesakan. Masa mula/tamat insiden tidak digunakan untuk mengisi jam yang hilang. Sempadan rujukan 2018.")
        for s in snapshots:
            st.markdown(f'[{s["label"]} — fail sumber]({s["source"]})')
    st.download_button("Muat turun rekod trafik CSV", frame.to_csv(index=False).encode("utf-8-sig"),
                       "trafik_lampau.csv", "text/csv")
    st.download_button("Muat turun peta trafik HTML", page.encode("utf-8"),
                       "trafik_lampau.html", "text/html")
