"""Clearly labelled fictional traffic over existing sample road geometries."""
import io
import json
import math
from html import escape
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

NOTICE = "SIMULASI TRAFIK"


def score(index, hour):
    """Illustrative index, NOT fitted to observations or a traffic service."""
    offset = ((index % 3) - 1) * 0.55
    morning = (26 + index % 4 * 6) * math.exp(-0.5 * ((hour - 8 - offset) / 1.2) ** 2)
    lunch = (22 + index % 5 * 8) * math.exp(-0.5 * ((hour - 12.7 + offset) / 1.6) ** 2)
    evening = (48 + index % 4 * 8) * math.exp(-0.5 * ((hour - 19 - offset) / 1.8) ** 2)
    return max(0, min(100, round(12 + index % 4 * 3 + morning + lunch + evening)))


def level(value):
    if value < 30:
        return "Rendah", "#16a34a"
    if value < 50:
        return "Sederhana", "#eab308"
    if value < 70:
        return "Tinggi", "#f97316"
    return "Sangat tinggi", "#dc2626"


def load_roads():
    return json.loads(Path(__file__).with_name("demo_roads.geojson").read_text(encoding="utf-8"))["features"]


def make_data(roads):
    return [{"Status": NOTICE, "Jam": f"{h:02d}:00" if h < 24 else "00:00 (+1 hari)",
             "ID": road["properties"]["id"], "Segmen": road["properties"]["name"],
             "Skor simulasi 0-100": score(i, h), "Tahap simulasi": level(score(i, h))[0]}
            for h in range(6, 25) for i, road in enumerate(roads)]


def demo_html(boundary, roads):
    import folium
    from branca.element import Element, MacroElement, Template
    m = folium.Map(tiles="OpenStreetMap", control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        name="Satelit", overlay=False).add_to(m)
    layer = folium.GeoJson(boundary, name="Sempadan DUN 2018",
        style_function=lambda f: {"color": "#06b6d4", "weight": 3, "fillOpacity": .025}).add_to(m)
    m.fit_bounds(layer.get_bounds(), padding=(25, 25))
    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(Element('''<div style="position:fixed;top:12px;left:55px;z-index:9999;background:#f0fdfa;color:#115e59;border:1px solid #5eead4;border-radius:9px;padding:10px 14px;font:bold 14px Arial;pointer-events:none">SIMULASI TRAFIK<br><span style="font-size:11px;font-weight:normal">Bukan trafik sebenar atau ramalan Google</span></div>'''))
    records = []
    for i, road in enumerate(roads):
        values = [score(i, 6 + n / 2) for n in range(37)]
        records.append({"geometry": road["geometry"], "name": escape(road["properties"]["name"]),
                        "id": road["properties"]["id"], "values": values})
    ctl = MacroElement()
    ctl.data = json.dumps(records).replace("<", "\\u003c")
    ctl._template = Template('''{% macro script(this, kwargs) %}
    (function(){
      const map = {{this._parent.get_name()}}, roads = {{this.data | safe}};
      function color(v){return v<30?'#16a34a':v<50?'#eab308':v<70?'#f97316':'#dc2626';}
      function label(v){return v<30?'Rendah':v<50?'Sederhana':v<70?'Tinggi':'Sangat tinggi';}
      const layers = roads.map(r => {
        const glow = L.geoJSON(r.geometry,{style:{color:'#eab308',weight:16,opacity:.23,interactive:false}}).addTo(map);
        const line = L.geoJSON(r.geometry,{style:{color:'#eab308',weight:7,opacity:1}}).addTo(map);
        return {glow,line};
      });
      const Control = L.Control.extend({onAdd:function(){
        const div=L.DomUtil.create('div');
        div.style.cssText='width:290px;background:white;color:#0f172a;padding:16px;border-radius:12px;box-shadow:0 3px 18px #0003;font:14px Arial';
        div.innerHTML='<b style="color:#0f766e">SIMULASI TRAFIK</b><div class="time" style="font-size:27px;font-weight:bold;margin:8px 0"></div><input aria-label="Masa simulasi" type="range" min="6" max="24" step="0.5" value="12" style="width:100%;accent-color:#0d9488"><div style="display:flex;justify-content:space-between;font-size:11px"><span>6 AM</span><span>12 AM (hari berikut)</span></div><div style="display:flex;gap:8px;margin:14px 0"><button class="noon">12 PM</button><button class="night">8 PM</button></div><div class="stats" style="padding:9px;background:#f1f5f9;border-radius:8px"></div><div style="font-size:12px;line-height:1.8;margin-top:10px"><span style="color:#16a34a">━━</span> Rendah (0–29)<br><span style="color:#eab308">━━</span> Sederhana (30–49)<br><span style="color:#f97316">━━</span> Tinggi (50–69)<br><span style="color:#dc2626">━━</span> Sangat tinggi (70–100)</div><small>Skor simulasi, bukan kelajuan atau jumlah kenderaan.</small>';
        div.querySelectorAll('button').forEach(b=>b.style.cssText='background:#0f766e;color:white;border:0;border-radius:7px;padding:9px 18px;font-weight:bold;cursor:pointer');
        L.DomEvent.disableClickPropagation(div);L.DomEvent.disableScrollPropagation(div);
        const slider=div.querySelector('input');
        function update(){
          const hour=Number(slider.value), idx=Math.round((hour-6)*2);
          const time=hour===24?'12:00 AM (+1 hari)':String(Math.floor(hour)%12||12)+':'+(hour%1?'30':'00')+(hour<12?' AM':' PM');
          div.querySelector('.time').textContent=time;
          let sum=0, high=0;
          roads.forEach((r,i)=>{
            const v=r.values[idx];sum+=v;if(v>=70)high++;
            layers[i].glow.setStyle({color:color(v)});layers[i].line.setStyle({color:color(v)});
            layers[i].line.eachLayer(l=>{
              const popup='<b>SIMULASI TRAFIK</b><br><b>'+r.id+' · '+r.name+'</b><br>'+time+' · '+label(v)+'<br>Skor simulasi: '+v+'/100<br>Bukan trafik sebenar atau ramalan Google.';
              if(l.getPopup())l.setPopupContent(popup);else l.bindPopup(popup);
              const tip=r.id+' · '+label(v)+' · '+v+'/100 (simulasi)';
              if(l.getTooltip())l.setTooltipContent(tip);else l.bindTooltip(tip);
            });
          });
          div.querySelector('.stats').textContent='Purata simulasi '+Math.round(sum/roads.length)+'/100 · '+high+' segmen merah / '+roads.length;
        }
        slider.addEventListener('input',update);
        div.querySelector('.noon').onclick=()=>{slider.value=12;update();};
        div.querySelector('.night').onclick=()=>{slider.value=20;update();};
        update();return div;
      }});new Control({position:'bottomleft'}).addTo(map);
    })();
    {% endmacro %}''')
    m.add_child(ctl)
    return m.get_root().render()


def curve_figure(roads):
    fig = Figure(figsize=(11, 2.6), facecolor="white", constrained_layout=True)
    ax = fig.subplots()
    hours = list(range(6,25))
    means = [sum(score(i,h) for i in range(len(roads)))/len(roads) for h in hours]
    ax.bar(hours, means, color=[level(v)[1] for v in means], width=.65)
    ax.set(ylim=(0,100), ylabel="Skor simulasi (0-100)", title="SIMULASI TRAFIK - purata segmen contoh")
    ax.set_xticks(hours, [str(h) if h<24 else "00*" for h in hours])
    ax.set_xlabel("Jam MYT (andaian) | *00 = tengah malam hari berikutnya")
    ax.spines[["top","right"]].set_visible(False)
    return fig


def comparison_figure(boundary, roads):
    fig = Figure(figsize=(11, 6.3), facecolor="white", constrained_layout=True)
    axes = fig.subplots(1,2)
    polys = [boundary["geometry"]["coordinates"]] if boundary["geometry"]["type"] == "Polygon" else boundary["geometry"]["coordinates"]
    for ax,h in zip(axes,[12,20]):
        for poly in polys:
            ax.add_patch(Polygon(poly[0],facecolor="#ecfeff",edgecolor="#0891b2",linewidth=1.3))
        for i,road in enumerate(roads):
            geom=road["geometry"]
            parts=[geom["coordinates"]] if geom["type"]=="LineString" else geom["coordinates"]
            for part in parts:
                ax.plot([p[0] for p in part],[p[1] for p in part],color=level(score(i,h))[1],linewidth=4,solid_capstyle="round")
            midpoint=parts[0][len(parts[0])//2]
            offset={2:(-26,0),3:(6,13),4:(9,-9)}.get(i,(4,4))
            ax.annotate(road['properties']['id'],midpoint,xytext=offset,textcoords='offset points',fontsize=7,color='#334155')
        ax.autoscale_view()
        ax.set_aspect('equal')
        ax.set_title(f"{h:02d}:00 MYT - SIMULASI",fontweight='bold',color='#0f766e')
        ax.set_xlabel('Longitude');ax.set_ylabel('Latitude')
        ax.ticklabel_format(useOffset=False)
        ax.grid(alpha=.15)
    return fig


def make_demo_pdf(boundary, roads):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from matplotlib.font_manager import findfont
    pdfmetrics.registerFont(TTFont('DemoSans',findfont('DejaVu Sans')))
    pdfmetrics.registerFont(TTFont('DemoSans-Bold',findfont('DejaVu Sans:weight=bold')))
    out=io.BytesIO();c=canvas.Canvas(out,pagesize=landscape(A4));w,h=landscape(A4)
    c.setTitle('SIMULASI TRAFIK - Paya Rumput')
    def header(title):
        c.setFillColor(HexColor('#0f766e'));c.setFont('DemoSans-Bold',18)
        c.drawString(35,h-38,'SIMULASI TRAFIK')
        c.setFillColor(HexColor('#0f172a'));c.setFont('DemoSans',12);c.drawString(35,h-60,title)
        c.setFont('DemoSans',9);c.drawString(35,23,'Bukan trafik sebenar, ramalan Google, kelajuan atau bilangan kenderaan. Untuk demonstrasi sahaja.')
    def figure(fig,x,y,width,height):
        img=io.BytesIO();fig.savefig(img,format='png',dpi=160);img.seek(0)
        c.drawImage(ImageReader(img),x,y,width=width,height=height,mask='auto')
    header('Paya Rumput | Perbandingan 12:00 PM dan 8:00 PM | 9 segmen contoh')
    figure(comparison_figure(boundary,roads),45,76,w-90,h-155)
    for i,(label,color) in enumerate([('Rendah 0-29','#16a34a'),('Sederhana 30-49','#eab308'),('Tinggi 50-69','#f97316'),('Sangat tinggi 70-100','#dc2626')]):
        x=45+i*190;c.setFillColor(HexColor(color));c.rect(x,52,16,6,fill=1,stroke=0)
        c.setFillColor(HexColor('#334155'));c.setFont('DemoSans',9);c.drawString(x+23,51,label)
    c.showPage();header('Pola harian simulasi | 06:00 hingga 00:00 hari berikutnya')
    figure(curve_figure(roads),35,h-285,w-70,200)
    c.setFont('DemoSans-Bold',10);c.drawString(40,h-309,'Segmen contoh (geometri rujukan sahaja; semua skor ialah simulasi)')
    c.setFont('DemoSans',8)
    for i,road in enumerate(roads):
        name=road['properties']['name']
        c.drawString(40,h-331-i*16,f"{road['properties']['id']}: {name[:135]}")
    c.setFont('DemoSans',8)
    c.drawString(40,78,'Andaian: puncak pagi, tengah hari dan petang dengan variasi mengikut segmen; tiada latihan atau pengesahan data.')
    c.drawString(40,63,'Sempadan: ElectionData.MY 2018. Garisan contoh: TomTom melalui arkib awam mygov, dipotong pada sempadan.')
    c.drawString(40,48,'Liputan tidak mewakili semua jalan. Fail demo_roads.geojson menyimpan pautan sumber geometri.')
    c.save();return out.getvalue()


def render_simulation(st,boundary):
    from streamlit.components.v1 import html
    st.subheader('Simulasi hotspot trafik · Paya Rumput')
    st.caption('Mod simulasi · Bukan data trafik sebenar.')
    try:
        roads=load_roads()
    except (OSError,ValueError) as exc:
        st.error(f'Muat naik demo_roads.geojson bersama app.py dan simulation.py. {exc}')
        return
    page=demo_html(boundary,roads)
    html(page,height=760)
    st.caption('Gerakkan masa 6 AM–12 AM di dalam peta; butang 12 PM / 8 PM tersedia. Warna berubah tanpa memuat semula peta. Hanya 9 segmen contoh dipaparkan, bukan semua jalan.')
    st.pyplot(curve_figure(roads),use_container_width=True)
    with st.expander('Cara simulasi dibina'):
        st.write('Skor 0–100 dijana daripada lengkung puncak pagi, tengah hari dan petang berdasarkan andaian, dengan variasi simulasi mengikut segmen. Tiada data Google, Waze, kiraan kenderaan, demografi atau ramalan terlatih digunakan untuk skor. Geometri jalan contoh dan sempadan datang daripada fail rujukan sedia ada; ini bukan peta liputan semua jalan.')
    c1,c2,c3=st.columns(3)
    c1.download_button('PDF simulasi · 12 PM & 8 PM',make_demo_pdf(boundary,roads),'SIMULASI_paya_rumput.pdf','application/pdf')
    c2.download_button('CSV simulasi · semua jam',pd.DataFrame(make_data(roads)).to_csv(index=False).encode('utf-8-sig'),'SIMULASI_trafik.csv','text/csv')
    c3.download_button('Peta simulasi HTML',page.encode('utf-8'),'SIMULASI_peta.html','text/html')
