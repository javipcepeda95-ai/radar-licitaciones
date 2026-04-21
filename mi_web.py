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
# --- 2. CSS AVANZADO (DISEÑO CORPORATIVO) ---
# ==============================================================================
st.markdown(
    """
    <style>
        :root { --coral-red: #FF4B4B; --anerpro-blue: #002C5F; }
        
        /* Eliminar navegación por defecto de Streamlit */
        [data-testid="stSidebarNav"] { display: none !important; }
        
        /* Ajuste de márgenes */
        .block-container { padding-top: 2rem !important; }

        /* Estilo de Cabecera con Antena */
        .radar-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 25px;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
        }
        
        .radar-title {
            font-size: 2.2rem;
            font-weight: 700;
            color: #31333F;
            margin: 0;
        }

        /* Botones Rojos Anerpro */
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button {
            background-color: var(--coral-red) !important;
            color: white !important;
            border: none !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }
        
        /* Estilos de tablas */
        [data-testid="stDataFrame"] { border: 1px solid #f0f2f6; border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- ICONO SVG DE LA ANTENA (Reutilizable) ---
def mostrar_cabecera(titulo):
    st.markdown(
        f"""
        <div class="radar-header">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" stroke-width="1" opacity="0.3"></circle>
                <line x1="12" y1="12" x2="19" y2="5" stroke="#FF4B4B" stroke-width="2"></line>
                <circle cx="12" cy="12" r="2" fill="#FF4B4B" stroke="#FF4B4B"></circle>
                <path d="M12 2a10 10 0 0 1 10 10" opacity="0.5"></path>
            </svg>
            <div class="radar-title">{titulo}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- PROMPT MAESTRO ---
PROMPT_MAESTRO = """
Actúa como un Analista Experto en Contratación Pública. Contexto: ANERPRO es empresa EPCista. ROLECE: I-5-2; I-6-3; I-8-1; I-9-3; J-2-3; J-3-2; J-4-3; J-5-4; K-9-1; O-4-1; P-1-1; P-2-3; P-3-3; P-5-1; Q-1-3.
ANALIZA y devuelve JSON: { "titulo_oferta": "...", "datos_iniciales": [...], "alcance": [...], "pros": [...], "contras": [...], "valoracion_puntuacion": "...", "valoracion_texto": "..." }
"""

# --- 3. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("")
        if os.path.exists("logo.png"): 
            st.image("logo.png", width=200) # Tamaño de logo controlado
        st.markdown("<h4 style='text-align: center;'>Acceso Restringido</h4>", unsafe_allow_html=True)
        with st.form("login"):
            pwd = st.text_input("Contraseña corporativa:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if pwd == st.secrets["PASSWORD_WEB"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("❌ Contraseña incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    KEYWORDS = ["Confederación", "Hidrográfica", "Canales", "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    # --- 5. FUNCIONES ---
    def normalizar(t): return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn') if t else ""
    
    def extraer_presupuesto(texto):
        if not texto: return "Ver PDF"
        t = re.sub(r'<[^>]*>', ' ', texto)
        for p in [r"(?:Importe|Valor estimado):\s*([\d\.]+(?:,\d{1,2})?)", r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]:
            m = re.search(p, t, re.I)
            if m: return m.group(1).strip() + " €"
        return "Ver PDF"

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

    # --- 6. BARRA LATERAL CON DESPLEGABLE ---
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=150)
        st.write("---")
        st.markdown("### Navegación")
        opcion = st.selectbox(
            "Selecciona una sección:",
            ["🔍 Búsqueda Licitaciones", "📁 Archivo e Informes", "📄 Generación de Informes"],
            label_visibility="collapsed"
        )
        st.markdown("<div style='height: 45vh;'></div>", unsafe_allow_html=True)
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    # Configuración común de tablas
    column_config = {
        "Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace"),
        "Publicado": st.column_config.TextColumn("Publicado", width="small"),
        "Fin Plazo": st.column_config.TextColumn("Fin Plazo", width="small")
    }

    # --- VISTA 1: BÚSQUEDA ---
    if "Búsqueda" in opcion:
        mostrar_cabecera("Radar de Licitaciones")
        st.write("Pulsa para escanear las últimas novedades de la Plataforma de Contratación del Estado.")
        
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                hoy = datetime.now().date()
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar(e.title + " " + res)
                    coin = sorted(list(set([k.upper() for k in KEYWORDS if normalizar(k) in txt])))
                    
                    if coin:
                        f_cierre = extraer_fecha_cierre(e, res)
                        if f_cierre != "No indicada" and datetime.strptime(f_cierre, "%d/%m/%Y").date() < hoy: continue
                        
                        encontradas.append({
                            "Publicado": datetime.now().strftime("%d/%m/%Y"),
                            "Organismo": e.get('author', 'No indicado'),
                            "Título": e.title,
                            "Presupuesto": extraer_presupuesto(res),
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
                    st.success(f"¡Detectadas {len(nuevas)} nuevas oportunidades!")
                    st.dataframe(pd.DataFrame(nuevas), column_config=column_config, hide_index=True, use_container_width=True)
                else:
                    st.info("No se han encontrado nuevas licitaciones que cumplan los filtros.")

    # --- VISTA 2: ARCHIVO ---
    elif "Archivo" in opcion:
        mostrar_cabecera("Historial de Licitaciones")
        hist = cargar_historial()
        if hist:
            df = pd.DataFrame(list(reversed(hist)))
            busq = st.text_input("🔍 Filtrar por título u organismo:")
            if busq:
                df = df[df.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            
            st.dataframe(df, column_config=column_config, hide_index=True, use_container_width=True)
            
            col_ex, col_re = st.columns([1, 1])
            with col_ex:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="licitaciones_anerpro.xlsx", mime="application/vnd.ms-excel")
            with col_re:
                if st.button("🗑️ Resetear Historial"):
                    if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                    st.rerun()
        else:
            st.info("El historial está vacío.")

    # --- VISTA 3: GENERACIÓN DE INFORMES ---
    elif "Generación" in opcion:
        mostrar_cabecera("Analista de Licitaciones IA")
        st.write("Arrastra los pliegos PDF para que Gemini 2.0 Flash genere el informe corporativo.")
        
        files = st.file_uploader("Cargar Pliegos", type="pdf", accept_multiple_files=True)
        
        if st.button("Analizar con IA y Generar PDF", type="primary") and files:
            with st.spinner("🧠 Analizando documentos con Gemini 2.0 Flash..."):
                try:
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    docs_ia = []
                    rutas = []
                    for f in files:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(f.getvalue())
                            rutas.append(tmp.name)
                            docs_ia.append(client.files.upload(file=tmp.name))
                    
                    response = client.models.generate_content(model='gemini-2.0-flash', contents=[PROMPT_MAESTRO] + docs_ia)
                    for r in rutas: os.remove(r)
                    
                    datos = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
                    
                    # --- MAQUETACIÓN PREMIUM ---
                    html_filas = "".join([f"<tr><td><strong>{f['concepto']}</strong></td><td>{f['detalle']}</td></tr>" for f in datos.get('datos_iniciales', [])])
                    ruta_logo = os.path.abspath("logo.png")
                    tag_logo = f'<img src="{ruta_logo}" height="25" />' if os.path.exists(ruta_logo) else ''
                    
                    html_final = f"""
                    <html>
                    <head>
                    <style>
                        @page {{ size: A4; margin-top: 3.5cm; margin-bottom: 2.5cm; margin-left: 1.5cm; margin-right: 1.5cm;
                               @frame header_frame {{ -pdf-frame-content: h_c; top: 1cm; height: 1.5cm; }}
                               @frame footer_frame {{ -pdf-frame-content: f_c; bottom: 1cm; height: 1cm; }} }}
                        body {{ font-family: Helvetica, sans-serif; font-size: 11pt; color: #333; }}
                        #h_c {{ text-align: right; }} #f_c {{ text-align: right; font-size: 9pt; color: #888; }}
                        .tit {{ text-align: center; color: #002C5F; font-size: 16pt; font-weight: bold; border-bottom: 2px solid #002C5F; padding-bottom: 5px; }}
                        .sec {{ background-color: #F0F4F8; color: #002C5F; padding: 5px 10px; font-weight: bold; border-left: 4px solid #002C5F; margin-top: 15px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                        th {{ background-color: #002C5F; color: white; padding: 8px; text-align: left; }}
                        td {{ padding: 8px; border-bottom: 1px solid #EEE; vertical-align: top; }}
                    </style>
                    </head>
                    <body>
                        <div id="h_c">{tag_logo}</div>
                        <div id="f_c">Página <pdf:pagenumber> de <pdf:pagecount></div>
                        <div class="tit">ANÁLISIS DE OFERTA: {datos.get('titulo_oferta')}</div>
                        <div class="sec">1. DATOS INICIALES</div>
                        <table><tr><th width="25%">CONCEPTO</th><th>DETALLE</th></tr>{html_filas}</table>
                        <div class="sec">2. ALCANCE</div><ul>{"".join([f"<li>{i}</li>" for i in datos.get('alcance', [])])}</ul>
                        <div class="sec">3. ANÁLISIS DE VIABILIDAD</div>
                        <p style="color:green"><b>PROS:</b></p><ul>{"".join([f"<li>{i}</li>" for i in datos.get('pros', [])])}</ul>
                        <p style="color:red"><b>CONTRAS:</b></p><ul>{"".join([f"<li>{i}</li>" for i in datos.get('contras', [])])}</ul>
                        <div class="sec">4. VALORACIÓN</div>
                        <p><b>PUNTUACIÓN: {datos.get('valoracion_puntuacion')}</b></p>
                        <p style="text-align: justify;">{datos.get('valoracion_texto')}</p>
                    </body>
                    </html>
                    """
                    pdf_buf = io.BytesIO()
                    pisa.CreatePDF(html_final, dest=pdf_buf)
                    st.success("✅ Informe generado correctamente.")
                    st.download_button("📥 Descargar Informe PDF", data=pdf_buf.getvalue(), file_name="Informe_Anerpro.pdf", mime="application/pdf")
                except Exception as e: st.error(f"Error: {e}")
