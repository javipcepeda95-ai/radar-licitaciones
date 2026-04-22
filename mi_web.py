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
# --- 2. CSS AVANZADO (DISEÑO CORPORATIVO LIMPIO Y SEGURO) ---
# ==============================================================================
st.markdown(
    """
    <style>
        :root { --coral-red: #FF4B4B; --anerpro-blue: #002C5F; }
        
        /* Ocultar navegación y cabecera nativa de Streamlit */
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarHeader"] { display: none !important; }
        
        /* Subir la cabecera del cuerpo principal */
        .block-container {
            padding-top: 3.5rem !important; 
        }

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
            font-size: 2.5rem;
            font-weight: 700;
            color: #31333F;
            margin: 0;
            line-height: 1.1;
        }

        /* --- BOTONES --- */
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button {
            background-color: var(--coral-red) !important;
            color: white !important;
            border: none !important;
            padding: 0.6rem 2rem !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }

        /* Botón de Cerrar Sesión (Estilo Secundario en Sidebar) */
        [data-testid="stSidebar"] button[kind="secondary"] {
            border: 1px solid #ddd !important;
            color: #888 !important;
            background-color: transparent !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            transition: all 0.3s ease;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: var(--coral-red) !important;
            color: var(--coral-red) !important;
        }

        /* --- SIDEBAR Y MENÚ --- */
        [data-testid="stSidebar"] {
            background-color: #fcfcfc;
        }
        
        /* Quitar padding extra del sidebar para que el logo suba */
        [data-testid="stSidebarContent"] {
            padding-top: 1.5rem !important;
        }

        /* Expander Menu - Eliminar huecos */
        .st-expander {
            margin-top: 0px !important;
        }
        .st-expanderContent {
            padding: 0px 5px !important;
        }
        div[data-testid="stRadio"] > div {
            gap: 0px !important;
        }

        /* Evitar cortes de texto en las opciones */
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            overflow: visible !important;
            padding: 5px 0px !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label p {
            font-size: 0.95rem !important;
            white-space: nowrap !important;
            margin-left: 6px !important;
            margin-bottom: 0px !important;
        }

        /* Encabezado "Menu" */
        .st-expanderHeader {
            font-weight: bold !important;
            color: #31333F !important;
            border: 1px solid #f0f2f6 !important;
            border-radius: 8px !important;
            background-color: white !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- ICONO SVG DE LA ANTENA ---
def mostrar_cabecera(titulo):
    st.markdown(
        f"""
        <div class="radar-header">
            <svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" stroke-width="1" opacity="0.2"></circle>
                <line x1="12" y1="12" x2="19" y2="5" stroke="#FF4B4B" stroke-width="2.5"></line>
                <circle cx="12" cy="12" r="2.5" fill="#FF4B4B" stroke="#FF4B4B"></circle>
                <path d="M12 2a10 10 0 0 1 10 10" opacity="0.4" stroke="#FF4B4B"></path>
            </svg>
            <div class="radar-title">{titulo}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- PROMPT MAESTRO (Importado exactamente de analista.py) ---
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
    st.write("")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        if os.path.exists("logo.png"):
            _, mid_logo, _ = st.columns([0.5, 2, 0.5])
            with mid_logo:
                st.image("logo.png", use_container_width=True)
            
        st.markdown("<h3 style='text-align: center; color: #31333F; margin-top: 15px;'>Analisis de Licitaciones</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            pwd = st.text_input("Contraseña corporativa:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if pwd == st.secrets["PASSWORD_WEB"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: 
                    st.error("❌ Contraseña incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    KEYWORDS = ["Confederación", "Hidrográfica", "Canales", "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    # --- 5. FUNCIONES DE EXTRACCIÓN ---
    def normalizar(t): return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn') if t else ""
    
    def formatear_moneda(v):
        if not v or "PDF" in str(v): return v
        try:
            l = "".join(c for c in str(v) if c.isdigit() or c in ".,")
            if "." in l and "," in l: l = l.replace(".", "").replace(",", ".")
            elif "," in l: l = l.replace(",", ".")
            return f"{float(l):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except: return v

    def extraer_organismo(e, res):
        m = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", res, re.I | re.S)
        if m: 
            return re.sub(r'<[^>]*>', '', m.group(1).strip())
        elif e.get('author'): 
            return e.author
        return "No detectado"

    def extraer_presupuesto(res):
        if not res: return "Ver en PDF"
        t = re.sub(r'<[^>]*>', ' ', res)
        for p in [r"(?:Importe|Valor estimado):\s*([\d\.]+(?:,\d{1,2})?)", r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]:
            m = re.search(p, t, re.I)
            if m: return formatear_moneda(m.group(1).strip())
        return "Ver en PDF"

    def extraer_fecha_cierre(e, texto):
        try:
            raw = str(e).lower()
            m1 = re.search(r"['\"]?(?:cbc_)?enddate['\"]?\s*:\s*['\"](\d{4}-\d{2}-\d{2})", raw)
            if m1: return datetime.strptime(m1.group(1), "%Y-%m-%d").strftime("%d/%m/%Y")
        except: pass
        if texto:
            try:
                m_html = re.search(r"(?:plazo|presentaci.n|l.mite|hasta).*?(?:>|:|\s)(?:&nbsp;|\s)*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", texto, re.IGNORECASE | re.DOTALL)
                if m_html: 
                    f = m_html.group(1)
                    if "-" in f: return datetime.strptime(f, "%Y-%m-%d").strftime("%d/%m/%Y")
                    return f
                t_limpio = re.sub(r'<[^>]*>', ' ', texto).lower()
                m_txt = re.search(r"(?:plazo|presentaci.n|l.mite|hasta).{0,60}?(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", t_limpio)
                if m_txt: 
                    f = m_txt.group(1)
                    if "-" in f: return datetime.strptime(f, "%Y-%m-%d").strftime("%d/%m/%Y")
                    return f
            except: pass
        return "No indicada"

    def cargar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: return json.load(f)
                except: return []
        return []

    # --- 6. BARRA LATERAL ---
    with st.sidebar:
        # Logo arriba de forma nativa
        if os.path.exists("logo.png"): 
            st.image("logo.png", width=140)
            
        # Raya divisoria bajo el logo
        st.markdown('<hr style="margin: 5px 0px 15px 0px; border-top: 1.5px solid #e6e9ef;">', unsafe_allow_html=True)
        
        # Expander "Menu"
        with st.expander("Menu", expanded=False):
            opcion = st.radio(
                "", 
                ["🔍 Búsqueda Licitaciones", "📁 Archivo e Informes", "📄 Generación Informes"],
                label_visibility="collapsed"
            )
        
        # Espaciador nativo para empujar el botón "Cerrar Sesión" al fondo
        st.markdown("<div style='height: 45vh;'></div>", unsafe_allow_html=True)
        
        # Botón de cierre de sesión
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    # Configuración de tabla
    config_tabla = {
        "Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace"),
        "Publicado": st.column_config.TextColumn("Publicado", width="small"),
        "Fin Plazo": st.column_config.TextColumn("Fin Plazo", width="small"),
        "Importe": st.column_config.TextColumn("Importe", width="medium"),
        "Organismo": st.column_config.TextColumn("Organismo", width="large")
    }

    # --- VISTA 1: BÚSQUEDA ---
    if "Búsqueda" in opcion:
        mostrar_cabecera("Radar de Licitaciones")
        st.write("Escaner en tiempo real de la Plataforma de Contratación del Estado.")
        
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Conectando con el Estado...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                hoy = datetime.now().date()
                
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar(e.title + " " + res)
                    coin = sorted(list(set([k.upper() for k in KEYWORDS if normalizar(k) in txt])))
                    
                    if coin:
                        f_cierre = extraer_fecha_cierre(e, res)
                        
                        # Blindaje por si la fecha tiene un formato extraño del Estado
                        es_valida = True
                        if f_cierre != "No indicada":
                            try:
                                if datetime.strptime(f_cierre, "%d/%m/%Y").date() < hoy:
                                    es_valida = False
                            except ValueError:
                                pass # Si la fecha no se puede leer bien, la guardamos por precaución
                                
                        if not es_valida: continue
                        
                        encontradas.append({
                            "Publicado": datetime.now().strftime("%d/%m/%Y"),
                            "Organismo": extraer_organismo(e, res),
                            "Título": e.title,
                            "Importe": extraer_presupuesto(res),
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
                    st.success(f"¡Detectadas {len(nuevas)} nuevas licitaciones!")
                    st.dataframe(pd.DataFrame(nuevas), column_config=config_tabla, hide_index=True, use_container_width=True)
                elif len(encontradas) > 0: 
                    st.info(f"Escaneo completado. Se han detectado {len(encontradas)} ofertas con tus criterios, pero ya están todas guardadas en tu 'Archivo e Informes'. No hay novedades recientes.")
                else: 
                    st.info("No se ha encontrado ninguna oferta vigente en la plataforma con tus palabras clave.")

    # --- VISTA 2: ARCHIVO ---
    elif "Archivo" in opcion:
        mostrar_cabecera("Historial de Licitaciones")
        hist = cargar_historial()
        if hist:
            df = pd.DataFrame(list(reversed(hist)))
            busq = st.text_input("🔍 Filtrar por Organismo o Título:")
            if busq:
                df = df[df.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            
            st.dataframe(df, column_config=config_tabla, hide_index=True, use_container_width=True)
            
            col1, col2, col3 = st.columns([1.5, 1.5, 5])
            with col1:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="Radar_Anerpro.xlsx", use_container_width=True)
            with col2:
                if st.button("🗑️ Reset Historial", use_container_width=True):
                    if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                    st.rerun()
        else: 
            st.info("El historial está vacío.")

    # --- VISTA 3: GENERACIÓN INFORMES ---
    elif "Generación" in opcion:
        mostrar_cabecera("Analista de Licitaciones IA")
        st.write("Carga los pliegos PDF para generar el informe corporativo.")
        
        archivos = st.file_uploader("Subir pliegos", type="pdf", accept_multiple_files=True)
        
        if st.button("Analizar con IA y Generar PDF", type="primary") and archivos:
            with st.spinner("🧠 Analizando documentos con Gemini 2.5 Flash..."):
                try:
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    docs_ia, rutas = [], []
                    for f in archivos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(f.getvalue())
                            rutas.append(tmp.name)
                            docs_ia.append(client.files.upload(file=tmp.name))
                    
                    # CAMBIADO EXACTAMENTE AL MODELO QUE USAS EN ANALISTA.PY PARA EVITAR ERROR DE CUOTA
                    response = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=[PROMPT_MAESTRO] + docs_ia
                    )
                    
                    for r in rutas: os.remove(r)
                    
                    datos = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
                    
                    # MAQUETACIÓN CORPORATIVA IMPORTADA EXACTAMENTE DE ANALISTA.PY
                    html_filas_tabla = ""
                    for fila in datos.get('datos_iniciales', []):
                        html_filas_tabla += f"<tr><td><strong>{fila.get('concepto', '')}</strong></td><td>{fila.get('detalle', '')}</td></tr>\n"
                        
                    html_alcance = "".join([f"<li>{i}</li>" for i in datos.get('alcance', [])])
                    html_pros = "".join([f"<li>{i}</li>" for i in datos.get('pros', [])])
                    html_contras = "".join([f"<li>{i}</li>" for i in datos.get('contras', [])])
                    
                    ruta_logo = os.path.abspath("logo.png")
                    etiqueta_logo = f'<img src="{ruta_logo}" height="25" />' if os.path.exists(ruta_logo) else ''
                    
                    html_final = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <meta charset="UTF-8">
                    <style>
                        @page {{
                            size: A4;
                            margin-top: 3.5cm; 
                            margin-bottom: 2.5cm; 
                            margin-left: 1.5cm;
                            margin-right: 1.5cm;
                            
                            @frame header_frame {{
                                -pdf-frame-content: header_content;
                                top: 1cm;
                                margin-left: 1.5cm;
                                margin-right: 1.5cm;
                                height: 1.5cm;
                            }}
                            
                            @frame footer_frame {{
                                -pdf-frame-content: footer_content;
                                bottom: 1cm;
                                margin-left: 1.5cm;
                                margin-right: 1.5cm;
                                height: 1cm;
                            }}
                        }}
                        
                        /* FUENTE APTOS Y TAMAÑO 12PT (Igual que Word) */
                        body {{ font-family: "Aptos", Helvetica, Arial, sans-serif; font-size: 12pt; color: #333333; }}
                        
                        #header_content {{ text-align: right; }}
                        #footer_content {{ text-align: right; font-size: 10pt; color: #888888; }}
                        
                        .titulo-principal {{ text-align: center; color: #002C5F; font-size: 16pt; font-weight: bold; border-bottom: 1.5pt solid #002C5F; padding-bottom: 4pt; margin-bottom: 20pt; text-transform: uppercase; }}
                        
                        .seccion {{ background-color: #F0F4F8; color: #002C5F; padding: 4pt 8pt; font-size: 13pt; font-weight: bold; border-left: 3px solid #002C5F; margin-top: 15pt; margin-bottom: 10pt; text-transform: uppercase; }}
                        
                        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15pt; }}
                        th {{ background-color: #002C5F; color: white; padding: 6pt 8pt; text-align: left; font-size: 12pt; }}
                        td {{ padding: 6pt 8pt; border-bottom: 1pt solid #DDDDDD; font-size: 12pt; vertical-align: top; }}
                        tr:nth-child(even) {{ background-color: #FBFBFB; }}
                        
                        ul {{ margin-top: 5pt; margin-bottom: 15pt; padding-left: 18pt; }}
                        li {{ margin-bottom: 5pt; text-align: justify; line-height: 1.4; }}
                        .nota {{ font-size: 14pt; font-weight: bold; color: #002C5F; margin-bottom: 5pt; }}
                        .pros {{ color: #006600; font-weight: bold; margin-bottom: 3pt; font-size: 12pt; }}
                        .contras {{ color: #990000; font-weight: bold; margin-bottom: 3pt; margin-top: 10pt; font-size: 12pt; }}
                        .texto-justificado {{ text-align: justify; line-height: 1.4; }}
                    </style>
                    </head>
                    <body>
                        <div id="header_content">{etiqueta_logo}</div>
                        
                        <div id="footer_content">Página <pdf:pagenumber> de <pdf:pagecount></div>

                        <div class="titulo-principal">ANÁLISIS DE OFERTA: {datos.get('titulo_oferta', '')}</div>
                        
                        <div class="seccion">1. DATOS INICIALES</div>
                        <table>
                            <tr><th width="20%">CONCEPTO</th><th>DETALLE</th></tr>
                            {html_filas_tabla}
                        </table>
                        
                        <div class="seccion">2. ALCANCE</div>
                        <ul>
                            {html_alcance}
                        </ul>
                        
                        <div class="seccion">3. ANÁLISIS DE VIABILIDAD</div>
                        
                        <div class="pros">VENTAJAS (PROS):</div>
                        <ul>
                            {html_pros}
                        </ul>
                        
                        <div class="contras">RIESGOS Y PENALIZACIONES (CONTRAS):</div>
                        <ul>
                            {html_contras}
                        </ul>
                        
                        <div class="seccion">4. VALORACIÓN</div>
                        <div class="nota">PUNTUACIÓN: {datos.get('valoracion_puntuacion', '')}</div>
                        <div class="texto-justificado">{datos.get('valoracion_texto', '')}</div>
                    </body>
                    </html>
                    """
                    pdf_buf = io.BytesIO()
                    pisa.CreatePDF(html_final, dest=pdf_buf)
                    st.success("✅ Informe generado correctamente.")
                    st.download_button("📥 Descargar Informe Anerpro", data=pdf_buf.getvalue(), file_name=f"Analisis_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")
                
                except Exception as e: 
                    st.error(f"Error en el proceso: {e}")
