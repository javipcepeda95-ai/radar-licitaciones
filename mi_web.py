import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import re
import io
import tempfile
from google import genai
from xhtml2pdf import pisa

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="📡", layout="wide")

# ==============================================================================
# --- 2. CSS PARA LA INTERFAZ WEB ---
# ==============================================================================
st.markdown(
    """
    <style>
        :root { --coral-red: #FF4B4B; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebar"] img { margin-top: -30px !important; margin-bottom: 10px !important; }
        .block-container { padding-top: 2rem !important; }
        [data-testid="stForm"] { border: none !important; padding: 0 !important; }
        .radar-header { display: flex; align-items: center; gap: 15px; margin-bottom: 30px; border-bottom: 1px solid #eee; padding-top: 10px; padding-bottom: 15px; }
        .radar-title { font-size: 2.8rem; font-weight: 700; color: #31333F; margin: 0; padding: 0; line-height: 1.4; }
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button {
            background-color: var(--coral-red) !important;
            color: white !important;
            border: none !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
        }
        .stButton button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover { background-color: #e34343 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- PROMPT MAESTRO ---
PROMPT_MAESTRO = """
Actúa como un Analista Experto en Contratación Pública. Contexto: ANERPRO es empresa EPCista (ciclo del agua, MT/BT, biogás, automatización). ROLECE: I-5-2; I-6-3; I-8-1; I-9-3; J-2-3; J-3-2; J-4-3; J-5-4; K-9-1; O-4-1; P-1-1; P-2-3; P-3-3; P-5-1; Q-1-3.

ANALIZA los pliegos adjuntos y DEVUELVE ÚNICA Y EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO con la siguiente estructura:

{
  "titulo_oferta": "Nombre exacto del proyecto",
  "datos_iniciales": [
    {"concepto": "Ubicación", "detalle": "..."},
    {"concepto": "Expediente", "detalle": "..."},
    {"concepto": "Visita", "detalle": "..."},
    {"concepto": "Plazos", "detalle": "..."},
    {"concepto": "Presupuesto", "detalle": "..."},
    {"concepto": "Solvencia", "detalle": "..."},
    {"concepto": "Medios", "detalle": "..."},
    {"concepto": "Adjudicación", "detalle": "..."}
  ],
  "alcance": ["Punto 1", "Punto 2"],
  "pros": ["Ventaja 1"],
  "contras": ["Riesgo 1"],
  "valoracion_puntuacion": "Nota/10",
  "valoracion_texto": "Justificación."
}
"""

# --- 3. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.write("")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        st.markdown("<h3 style='text-align: center;'>Acceso al Buscador de Licitaciones</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            pwd = st.text_input("Contraseña:", type="password", placeholder="Introduce la contraseña...")
            if st.form_submit_button("Entrar", use_container_width=True):
                if pwd == st.secrets["PASSWORD_WEB"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("⚠️ Incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    KEYWORDS = ["Confederación", "Hidrográfica", "Canales", "energia", "nuclear", "hidrogeno", "eficiencia", "edar", "tratamiento", "agua", "automatizacion", "scada", "autoconsumo", "plc", "desalinizacion", "ciclo del agua"]

    # --- 5. FUNCIONES ---
    def normalizar(t): return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn') if t else ""
    
    def extraer_fecha_cierre(e, texto):
        raw = str(e).lower()
        m1 = re.search(r"['\"]?(?:cbc_)?enddate['\"]?\s*:\s*['\"](\d{4}-\d{2}-\d{2})", raw)
        if m1: return datetime.strptime(m1.group(1), "%Y-%m-%d").strftime("%d/%m/%Y")
        t_limpio = re.sub(r'<[^>]*>', ' ', texto or "").lower()
        m2 = re.search(r"(?:plazo|presentaci.n|l.mite|hasta).{0,60}?(\d{2}/\d{2}/\d{4})", t_limpio)
        return m2.group(1) if m2 else "No indicada"

    def cargar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: return json.load(f)
                except: return []
        return []

    # --- 6. NAVEGACIÓN ---
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=140)
        st.divider()
        opcion = st.radio("Menú", ["🔍 Búsqueda Licitaciones", "📁 Archivos e Informes", "📄 Generación de Informes"])
        st.markdown("<div style='height: 50vh;'></div>", unsafe_allow_html=True)
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    st.markdown('<div class="radar-header"><div class="radar-title">Radar de Licitaciones</div></div>', unsafe_allow_html=True)

    # --- VISTA 1 & 2 (RADAR Y ARCHIVO) ---
    if opcion == "🔍 Búsqueda Licitaciones":
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                hoy = datetime.now().date()
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar(e.title + " " + res)
                    coin = [k.upper() for k in KEYWORDS if normalizar(k) in txt]
                    if coin:
                        f_cierre = extraer_fecha_cierre(e, res)
                        valida = True
                        if f_cierre != "No indicada":
                            try:
                                if datetime.strptime(f_cierre, "%d/%m/%Y").date() < hoy: valida = False
                            except: pass
                        if valida:
                            encontradas.append({"Publicado": datetime.now().strftime("%d/%m/%Y"), "Organismo": e.get('author', 'N/D'), "Título": e.title, "Fin Plazo": f_cierre, "Palabras Detectadas": ", ".join(coin), "Enlace Oficial": e.link})
            hist = cargar_historial()
            vistos = {o["Enlace Oficial"] for o in hist}
            nuevas = [o for o in encontradas if o["Enlace Oficial"] not in vistos]
            if nuevas:
                hist.extend(nuevas)
                with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f: json.dump(hist, f, indent=4)
                st.success(f"¡{len(nuevas)} nuevas ofertas!")
                st.dataframe(pd.DataFrame(nuevas), use_container_width=True)
            else: st.info("Sin novedades vigentes.")

    elif opcion == "📁 Archivos e Informes":
        hist = cargar_historial()
        if hist:
            df = pd.DataFrame(list(reversed(hist)))
            busq = st.text_input("Buscar en el historial:")
            if busq: df = df[df.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            st.dataframe(df, use_container_width=True)
            if st.button("🗑️ Reset", use_container_width=True):
                if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                st.rerun()
        else: st.info("Historial vacío.")

    # --- VISTA 3: GENERACIÓN DE INFORMES (MOTOR MEJORADO) ---
    elif opcion == "📄 Generación de Informes":
        st.subheader("Analista de Licitaciones IA")
        files = st.file_uploader("Sube pliegos PDF para analizar", type="pdf", accept_multiple_files=True)
        
        if st.button("Analizar con IA y Generar PDF", type="primary") and files:
            with st.spinner("🧠 Gemini analizando pliegos (Maquetación Premium)..."):
                try:
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    docs_ia = []
                    rutas_temporales = []
                    for f in files:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(f.getvalue())
                            rutas_temporales.append(tmp.name)
                            docs_ia.append(client.files.upload(file=tmp.name))
                    
                    response = client.models.generate_content(
                        model='gemini-2.0-flash', # Usando el modelo más actual disponible
                        contents=[PROMPT_MAESTRO] + docs_ia
                    )
                    for r in rutas_temporales: os.remove(r)
                    
                    texto_limpio = response.text.strip().replace("```json", "").replace("```", "")
                    datos = json.loads(texto_limpio)
                    
                    # --- MAQUETACIÓN PROFESIONAL (Estilo analistaG) ---
                    html_filas = "".join([f"<tr><td><strong>{f['concepto']}</strong></td><td>{f['detalle']}</td></tr>" for f in datos.get('datos_iniciales', [])])
                    ruta_logo = os.path.abspath("logo.png")
                    logo_tag = f'<img src="{ruta_logo}" height="25" />' if os.path.exists(ruta_logo) else ''
                    
                    html_final = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <style>
                        @page {{
                            size: A4; margin-top: 3.5cm; margin-bottom: 2.5cm; margin-left: 1.5cm; margin-right: 1.5cm;
                            @frame header_frame {{ -pdf-frame-content: h_content; top: 1cm; height: 1.5cm; }}
                            @frame footer_frame {{ -pdf-frame-content: f_content; bottom: 1cm; height: 1cm; }}
                        }}
                        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #333; line-height: 1.4; }}
                        #h_content {{ text-align: right; margin-right: 1.5cm; }}
                        #f_content {{ text-align: right; font-size: 9pt; color: #888; margin-right: 1.5cm; }}
                        .titulo {{ text-align: center; color: #002C5F; font-size: 16pt; font-weight: bold; border-bottom: 1.5pt solid #002C5F; padding-bottom: 5pt; margin-bottom: 20pt; text-transform: uppercase; }}
                        .sec {{ background-color: #F0F4F8; color: #002C5F; padding: 4pt 8pt; font-size: 12pt; font-weight: bold; border-left: 4px solid #002C5F; margin-top: 15pt; margin-bottom: 10pt; }}
                        table {{ width: 100%; border-collapse: collapse; }}
                        th {{ background-color: #002C5F; color: white; padding: 6pt; text-align: left; }}
                        td {{ padding: 6pt; border-bottom: 1pt solid #DDD; vertical-align: top; }}
                        tr:nth-child(even) {{ background-color: #F9F9F9; }}
                        .pros {{ color: #006600; font-weight: bold; margin-top: 5pt; }}
                        .contras {{ color: #990000; font-weight: bold; margin-top: 10pt; }}
                        .puntuacion {{ font-size: 14pt; font-weight: bold; color: #002C5F; margin: 10pt 0; }}
                        .justificacion {{ text-align: justify; }}
                    </style>
                    </head>
                    <body>
                        <div id="h_content">{logo_tag}</div>
                        <div id="f_content">Página <pdf:pagenumber> de <pdf:pagecount></div>
                        <div class="titulo">ANÁLISIS DE OFERTA: {datos.get('titulo_oferta')}</div>
                        <div class="sec">1. DATOS INICIALES</div>
                        <table><tr><th width="25%">CONCEPTO</th><th>DETALLE</th></tr>{html_filas}</table>
                        <div class="sec">2. ALCANCE</div>
                        <ul>{"".join([f"<li>{i}</li>" for i in datos.get('alcance', [])])}</ul>
                        <div class="sec">3. ANÁLISIS DE VIABILIDAD</div>
                        <div class="pros">VENTAJAS (PROS):</div><ul>{"".join([f"<li>{i}</li>" for i in datos.get('pros', [])])}</ul>
                        <div class="contras">RIESGOS Y PENALIZACIONES (CONTRAS):</div><ul>{"".join([f"<li>{i}</li>" for i in datos.get('contras', [])])}</ul>
                        <div class="sec">4. VALORACIÓN FINAL</div>
                        <div class="puntuacion">PUNTUACIÓN: {datos.get('valoracion_puntuacion')}</div>
                        <div class="justificacion">{datos.get('valoracion_texto')}</div>
                    </body>
                    </html>
                    """
                    pdf_buf = io.BytesIO()
                    pisa.CreatePDF(html_final, dest=pdf_buf)
                    st.success("✅ Informe corporativo generado con éxito.")
                    st.download_button("📥 Descargar Informe Anerpro", data=pdf_buf.getvalue(), file_name=f"Analisis_Anerpro_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")
                except Exception as e: st.error(f"Error: {e}")
