import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime
import json
import os
import re
import io
import tempfile
import google.generativeai as genai
from xhtml2pdf import pisa

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="📡", layout="wide")

# ==============================================================================
# --- 2. CSS PARA INTERFAZ LIMPIA ---
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

# --- EL PROMPT MAESTRO (Tu original de analistaG.py) ---
PROMPT_MAESTRO = """
Actúa como un Analista Experto en Contratación Pública. Contexto: ANERPRO es empresa EPCista (ciclo del agua, MT/BT, biogás, automatización). ROLECE: I-5-2; I-6-3; I-8-1; I-9-3; J-2-3; J-3-2; J-4-3; J-5-4; K-9-1; O-4-1; P-1-1; P-2-3; P-3-3; P-5-1; Q-1-3.

ANALIZA los pliegos adjuntos y DEVUELVE ÚNICA Y EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO con la siguiente estructura (sin texto extra):

{
  "titulo_oferta": "Nombre exacto del proyecto",
  "datos_iniciales": [
    {"concepto": "Ubicación", "detalle": "Localidad y provincia"},
    {"concepto": "Expediente", "detalle": "Entidad y número"},
    {"concepto": "Visita", "detalle": "¿Obligatoria? Fecha y lugar"},
    {"concepto": "Plazos", "detalle": "Ejecución"},
    {"concepto": "Presupuesto", "detalle": "Importe sin IVA"},
    {"concepto": "Solvencia", "detalle": "¿Cumplimos ROLECE? Si no, solvencia alternativa"},
    {"concepto": "Medios", "detalle": "Personal y material mínimo"},
    {"concepto": "Adjudicación", "detalle": "Criterios en %"}
  ],
  "alcance": ["Punto clave 1", "Punto clave 2", "Punto clave 3..."],
  "pros": ["Ventaja 1", "Ventaja 2..."],
  "contras": ["Riesgo o penalización 1", "Riesgo 2..."],
  "valoracion_puntuacion": "Nota/10",
  "valoracion_texto": "Justificación ejecutiva."
}
"""

# --- 3. SISTEMA DE SEGURIDAD ---
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

    # --- 5. FUNCIONES AUXILIARES ---
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

    # --- VISTA 1: BÚSQUEDA ---
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
                            encontradas.append({
                                "Publicado": datetime.now().strftime("%d/%m/%Y"),
                                "Organismo": e.get('author', 'No detectado'),
                                "Título": e.title,
                                "Fin Plazo": f_cierre,
                                "Palabras Detectadas": ", ".join(coin),
                                "Enlace Oficial": e.link
                            })
            hist = cargar_historial()
            vistos = {o["Enlace Oficial"] for o in hist}
            nuevas = [o for o in encontradas if o["Enlace Oficial"] not in vistos]
            if nuevas:
                hist.extend(nuevas)
                with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f: json.dump(hist, f, indent=4)
                st.success(f"¡{len(nuevas)} nuevas ofertas!")
                st.dataframe(pd.DataFrame(nuevas), use_container_width=True)
            else: st.info("No hay novedades vigentes.")

    # --- VISTA 2: ARCHIVOS ---
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

    # --- VISTA 3: ANALISTA IA (FIXED 404 AND RESTORED PDF STYLE) ---
    elif opcion == "📄 Generación de Informes":
        st.subheader("Analista de Licitaciones IA")
        files = st.file_uploader("Sube pliegos PDF para analizar", type="pdf", accept_multiple_files=True)
        
        if st.button("Analizar con IA y Generar PDF", type="primary") and files:
            with st.spinner("🧠 Gemini analizando pliegos..."):
                try:
                    # Configuración robusta del modelo
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    # Usamos gemini-1.5-flash y forzamos salida JSON para evitar errores de parseo
                    model = genai.GenerativeModel(
                        model_name='gemini-1.5-flash',
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    docs_ia = []
                    temp_paths = []
                    for f in files:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(f.getvalue())
                            temp_paths.append(tmp.name)
                            docs_ia.append(genai.upload_file(path=tmp.name))
                    
                    # Llamada a la IA
                    response = model.generate_content([PROMPT_MAESTRO] + docs_ia)
                    datos = json.loads(response.text)
                    
                    # Limpieza de archivos temporales
                    for p in temp_paths: os.remove(p)

                    # --- RECONSTRUCCIÓN DEL HTML CORPORATIVO (De tu analistaG.py) ---
                    html_filas = "".join([f"<tr><td><strong>{i['concepto']}</strong></td><td>{i['detalle']}</td></tr>" for i in datos.get('datos_initiales', datos.get('datos_iniciales', []))])
                    
                    html_final = f"""
                    <html>
                    <head>
                    <style>
                        @page {{ size: A4; margin: 2cm; }}
                        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #333; }}
                        .titulo-principal {{ text-align: center; color: #002C5F; font-size: 16pt; font-weight: bold; border-bottom: 2px solid #002C5F; padding-bottom: 10px; margin-bottom: 20px; }}
                        .seccion {{ background-color: #F0F4F8; color: #002C5F; padding: 5px 10px; font-size: 12pt; font-weight: bold; border-left: 4px solid #002C5F; margin-top: 15px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                        th {{ background-color: #002C5F; color: white; padding: 8px; text-align: left; }}
                        td {{ padding: 8px; border-bottom: 1px solid #EEE; vertical-align: top; }}
                        .nota {{ font-size: 14pt; font-weight: bold; color: #002C5F; margin-top: 20px; }}
                        .pros {{ color: #006600; font-weight: bold; }}
                        .contras {{ color: #990000; font-weight: bold; }}
                    </style>
                    </head>
                    <body>
                        <div class="titulo-principal">ANÁLISIS DE OFERTA: {datos.get('titulo_oferta', 'S/N')}</div>
                        <div class="seccion">1. DATOS INICIALES</div>
                        <table>{html_filas}</table>
                        <div class="seccion">2. ALCANCE TÉCNICO</div>
                        <ul>{"".join([f"<li>{i}</li>" for i in datos.get('alcance', [])])}</ul>
                        <div class="seccion">3. VIABILIDAD (PROS Y CONTRAS)</div>
                        <p class="pros">VENTAJAS:</p>
                        <ul>{"".join([f"<li>{i}</li>" for i in datos.get('pros', [])])}</ul>
                        <p class="contras">RIESGOS:</p>
                        <ul>{"".join([f"<li>{i}</li>" for i in datos.get('contras', [])])}</ul>
                        <div class="seccion">4. VALORACIÓN FINAL</div>
                        <div class="nota">PUNTUACIÓN: {datos.get('valoracion_puntuacion', '-')}</div>
                        <p>{datos.get('valoracion_texto', '')}</p>
                    </body>
                    </html>
                    """
                    
                    # Generación de PDF
                    pdf_buf = io.BytesIO()
                    pisa.CreatePDF(html_final, dest=pdf_buf)
                    st.success("✅ Análisis completado con éxito")
                    st.download_button("📥 Descargar Informe Anerpro", data=pdf_buf.getvalue(), file_name=f"Analisis_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")
                
                except Exception as e:
                    st.error(f"Error en el análisis: {str(e)}")
