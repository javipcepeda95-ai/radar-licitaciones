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
import time
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
            padding: 0.4rem 1rem !important; 
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

# --- ICONOS SVG PERSONALIZADOS ---
def mostrar_cabecera(titulo, tipo_icono="radar"):
    if tipo_icono == "lupa":
        svg_code = '''<svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65" stroke="#FF4B4B" stroke-width="3"></line>
        </svg>'''
    elif tipo_icono == "carpeta":
        svg_code = '''<svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            <line x1="12" y1="11" x2="12" y2="17" stroke="#FF4B4B" stroke-width="2.5"></line>
            <line x1="9" y1="14" x2="15" y2="14" stroke="#FF4B4B" stroke-width="2.5"></line>
        </svg>'''
    elif tipo_icono == "documento":
        svg_code = '''<svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8" stroke="#FF4B4B" stroke-width="2"></polyline>
            <line x1="16" y1="13" x2="8" y2="13" stroke="#FF4B4B" stroke-width="2.5"></line>
            <line x1="16" y1="17" x2="8" y2="17" stroke="#FF4B4B" stroke-width="2.5"></line>
        </svg>'''
    else:
        svg_code = '''<svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" stroke-width="1" opacity="0.2"></circle>
            <line x1="12" y1="12" x2="19" y2="5" stroke="#FF4B4B" stroke-width="2.5"></line>
            <circle cx="12" cy="12" r="2.5" fill="#FF4B4B" stroke="#FF4B4B"></circle>
            <path d="M12 2a10 10 0 0 1 10 10" opacity="0.4" stroke="#FF4B4B"></path>
        </svg>'''

    st.markdown(
        f"""
        <div class="radar-header">
            {svg_code}
            <div class="radar-title">{titulo}</div>
        </div>
        """, unsafe_allow_html=True
    )

# --- PROMPT MAESTRO ---
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

# --- 3. SISTEMA DE SEGURIDAD (PANTALLA DE INICIO COMPACTA) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.write("")
    st.write("")
    st.write("")
    
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    
    with col2:
        if os.path.exists("logo2.png"):
            _, mid_logo, _ = st.columns([1, 1.2, 1])
            with mid_logo:
                st.image("logo2.png", use_container_width=True)
        elif os.path.exists("logo2.jpg"): 
            _, mid_logo, _ = st.columns([1, 1.2, 1])
            with mid_logo:
                st.image("logo2.jpg", use_container_width=True)
        elif os.path.exists("logo.png"): 
            _, mid_logo, _ = st.columns([1, 1.2, 1])
            with mid_logo:
                st.image("logo.png", use_container_width=True)
            
        st.markdown("<h3 style='text-align: center; color: #31333F; margin-top: 10px;'>bib analista de licitaciones</h3>", unsafe_allow_html=True)
        
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
    URL_FEED_BASE = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    KEYWORDS = ["Confederación", "Hidrográfica", "Canales", "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica", "PERTE"]

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
        for p in [r"(?:Importe|Valor estimado|Presupuesto)[\s\w]*:\s*([\d\.\s]+(?:,\d{1,2})?)", r"([\d\.\s]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]:
            m = re.search(p, t, re.I)
            if m: return formatear_moneda(m.group(1).strip())
        return "Ver en PDF"

    # Lógica a prueba de balas contra espacios invisibles
    def extraer_valor_numerico(res):
        if not res: return None
        t = re.sub(r'<[^>]*>', ' ', res)
        for p in [r"(?:Importe|Valor estimado|Presupuesto)[\s\w]*:\s*([\d\.\s]+(?:,\d{1,2})?)", r"([\d\.\s]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]:
            m = re.search(p, t, re.I)
            if m:
                val_str = m.group(1)
                l = "".join(c for c in str(val_str) if c.isdigit() or c in ".,")
                if "." in l and "," in l: 
                    l = l.replace(".", "").replace(",", ".")
                elif "," in l: 
                    l = l.replace(",", ".")
                try:
                    return float(l)
                except:
                    return None
        return None

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
        if os.path.exists("logo.png"): 
            st.image("logo.png", width=140)
            
        st.markdown('<hr style="margin: 5px 0px 15px 0px; border-top: 1.5px solid #e6e9ef;">', unsafe_allow_html=True)
        
        with st.expander("Menu", expanded=False):
            opcion = st.radio(
                "", 
                ["🔍 Búsqueda Licitaciones", "📁 Archivo e Informes", "📄 Generación Informes"],
                label_visibility="collapsed"
            )
        
        st.markdown("<div style='height: 45vh;'></div>", unsafe_allow_html=True)
        
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    config_tabla = {
        "Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace"),
        "Publicado": st.column_config.TextColumn("Publicado", width="small"),
        "Fin Plazo": st.column_config.TextColumn("Fin Plazo", width="small"),
        "Importe": st.column_config.TextColumn("Importe", width="medium"),
        "Organismo": st.column_config.TextColumn("Organismo", width="large")
    }

    # --- VISTA 1: BÚSQUEDA ---
    if "Búsqueda" in opcion:
        mostrar_cabecera("Buscador de Licitaciones", "lupa")
        st.write("Escaner en tiempo real de la Plataforma de Contratación del Estado.")
        
        default_kw_str = ", ".join(KEYWORDS)
        
        # INVERTIDO: Importe mínimo a la izquierda, Palabras clave a la derecha
        col_importe, col_espacio = st.columns([1, 3])
        with col_importe:
            st.markdown("<p style='font-size: 1rem; font-weight: 600; margin-bottom: -10px; color: var(--anerpro-blue);'>Importe mínimo (€):</p>", unsafe_allow_html=True)
            limite_presupuesto = st.number_input("", value=200000, step=50000, format="%d")
            
        with col_espacio:
            st.markdown("<p style='font-size: 1rem; font-weight: 600; margin-bottom: -10px; color: var(--anerpro-blue);'>Filtros de Búsqueda (separados por comas):</p>", unsafe_allow_html=True)
            keywords_input = st.text_area("", value=default_kw_str, height=100)
        
        if keywords_input.strip():
            keywords_activas = [k.strip() for k in keywords_input.split(',') if k.strip()]
        else:
            keywords_activas = []
        
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            if not keywords_activas:
                st.warning("⚠️ Introduce al menos una palabra clave para iniciar la búsqueda.")
            else:
                with st.spinner('Conectando con el Estado y paginando hacia atrás (Escaneo Profundo)...'):
                    encontradas = []
                    enlaces_escaneados = set() 
                    hoy = datetime.now().date()
                    
                    url_actual = URL_FEED_BASE
                    paginas_a_escanear = 15 
                    paginas_leidas = 0
                    ofertas_descartadas_por_precio = 0 
                    
                    for pagina in range(paginas_a_escanear):
                        if not url_actual: break 
                        
                        feed = feedparser.parse(url_actual)
                        paginas_leidas += 1
                        
                        for e in feed.entries:
                            if e.link in enlaces_escaneados: continue
                                
                            res = e.summary if 'summary' in e else ""
                            txt = normalizar(e.title + " " + res)
                            
                            coin = sorted(list(set([k.upper() for k in keywords_activas if normalizar(k) in txt])))
                            
                            if coin:
                                f_cierre = extraer_fecha_cierre(e, res)
                                es_valida = True
                                if f_cierre != "No indicada":
                                    try:
                                        if datetime.strptime(f_cierre, "%d/%m/%Y").date() < hoy:
                                            es_valida = False
                                    except ValueError:
                                        pass 
                                        
                                if not es_valida: continue
                                
                                val_num = extraer_valor_numerico(res)
                                if val_num is not None and val_num < limite_presupuesto:
                                    ofertas_descartadas_por_precio += 1
                                    continue
                                
                                try: 
                                    f_pub = datetime(*e.published_parsed[:3]).strftime("%d/%m/%Y")
                                except: 
                                    f_pub = datetime.now().strftime("%d/%m/%Y")
                                
                                enlaces_escaneados.add(e.link)
                                encontradas.append({
                                    "Publicado": f_pub,
                                    "Organismo": extraer_organismo(e, res),
                                    "Título": e.title,
                                    "Importe": extraer_presupuesto(res),
                                    "Fin Plazo": f_cierre,
                                    "Palabras Detectadas": ", ".join(coin),
                                    "Enlace Oficial": e.link
                                })
                                
                        url_siguiente = None
                        if hasattr(feed, 'feed') and 'links' in feed.feed:
                            for link in feed.feed.links:
                                if link.get('rel') == 'next':
                                    url_siguiente = link.get('href')
                                    break
                        url_actual = url_siguiente 
                    
                    hist = cargar_historial()
                    vistos = {o["Enlace Oficial"] for o in hist}
                    nuevas = [o for o in encontradas if o["Enlace Oficial"] not in vistos]
                    
                    if nuevas:
                        hist.extend(nuevas)
                        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f: json.dump(hist, f, indent=4)
                        st.success(f"¡Detectadas {len(nuevas)} nuevas licitaciones en las últimas {paginas_leidas} páginas del Estado!")
                        if ofertas_descartadas_por_precio > 0:
                            st.info(f"🚫 Se han ocultado {ofertas_descartadas_por_precio} ofertas adicionales por no llegar a los {limite_presupuesto:,.0f} € mínimos.")
                        st.dataframe(pd.DataFrame(nuevas), column_config=config_tabla, hide_index=True, use_container_width=True)
                    elif len(encontradas) > 0: 
                        st.info(f"Se han escaneado {paginas_leidas} páginas del Estado y detectado {len(encontradas)} ofertas con tus criterios, pero ya están todas guardadas en tu 'Archivo e Informes'. No hay novedades recientes.")
                        if ofertas_descartadas_por_precio > 0:
                            st.info(f"🚫 Además, se descartaron en silencio {ofertas_descartadas_por_precio} ofertas por debajo de {limite_presupuesto:,.0f} €.")
                    else: 
                        st.info("No se ha encontrado ninguna oferta vigente en la plataforma con tus palabras clave y tu límite de presupuesto.")

    # --- VISTA 2: ARCHIVO ---
    elif "Archivo" in opcion:
        mostrar_cabecera("Historial de Licitaciones", "carpeta")
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
        mostrar_cabecera("Generación de Informes", "documento")
        st.write("Carga los pliegos PDF para generar el informe corporativo.")
        
        if "uploader_key" not in st.session_state:
            st.session_state["uploader_key"] = 1
            
        archivos = st.file_uploader("Subir pliegos", type="pdf", accept_multiple_files=True, key=f"pdf_uploader_{st.session_state['uploader_key']}")
        
        col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 6], gap="small")
        with col_btn1:
            btn_analizar = st.button("Generar Análisis", type="primary", use_container_width=True)
        with col_btn2:
            if st.button("Eliminar Adjuntos", use_container_width=True):
                st.session_state["uploader_key"] += 1
                st.rerun()
        
        if btn_analizar and archivos:
            with st.spinner("🧠 Analizando documentos con Gemini 2.5 Flash..."):
                try:
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    docs_ia, rutas = [], []
                    for f in archivos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(f.getvalue())
                            rutas.append(tmp.name)
                            docs_ia.append(client.files.upload(file=tmp.name))
                    
                    max_reintentos = 5
                    response = None
                    tiempo_espera = 2
                    
                    aviso_estado = st.empty() 
                    
                    for intento in range(max_reintentos):
                        try:
                            response = client.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=[PROMPT_MAESTRO] + docs_ia
                            )
                            aviso_estado.empty() 
                            break 
                        except Exception as api_e:
                            error_str = str(api_e)
                            if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str:
                                if intento < max_reintentos - 1:
                                    aviso_estado.warning(f"⏳ Los servidores de Google están saturados ahora mismo. Forzando reintento en {tiempo_espera}s... (Intento {intento + 1}/{max_reintentos})")
                                    time.sleep(tiempo_espera)
                                    tiempo_espera *= 2
                                    continue
                            raise api_e

                    for r in rutas: os.remove(r)
                    
                    datos = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
                    
                    st.markdown("---")
                    st.markdown(f"<h2 style='text-align: center; color: var(--anerpro-blue);'>{datos.get('titulo_oferta', 'Análisis de Licitación')}</h2>", unsafe_allow_html=True)
                    
                    col_datos, col_alcance = st.columns([1, 1])
                    
                    with col_datos:
                        st.markdown("<h4 style='color: var(--anerpro-blue); margin-bottom: 10px;'>📋 Datos Iniciales</h4>", unsafe_allow_html=True)
                        df_datos = pd.DataFrame(datos.get('datos_iniciales', []))
                        if not df_datos.empty and "concepto" in df_datos.columns:
                            df_datos.columns = ["Concepto", "Detalle"]
                            st.dataframe(df_datos, hide_index=True, use_container_width=True)
                            
                    with col_alcance:
                        st.markdown("<h4 style='color: var(--anerpro-blue); margin-bottom: 10px;'>🎯 Alcance</h4>", unsafe_allow_html=True)
                        for item in datos.get('alcance', []):
                            st.markdown(f"- {item}")
                            
                    st.markdown("<h4 style='color: var(--anerpro-blue); margin-top: 20px;'>⚖️ Análisis de Viabilidad</h4>", unsafe_allow_html=True)
                    col_pros, col_contras = st.columns(2)
                    with col_pros:
                        st.markdown("**🟢 VENTAJAS (PROS):**")
                        for item in datos.get('pros', []):
                            st.markdown(f"- {item}")
                    with col_contras:
                        st.markdown("**🔴 RIESGOS (CONTRAS):**")
                        for item in datos.get('contras', []):
                            st.markdown(f"- {item}")
                            
                    st.markdown("<h4 style='color: var(--anerpro-blue); margin-top: 20px;'>🏆 Valoración Final</h4>", unsafe_allow_html=True)
                    st.markdown(f"**PUNTUACIÓN:** {datos.get('valoracion_puntuacion', '')}")
                    st.info(datos.get('valoracion_texto', ''))
                    
                    st.markdown("---")
                    
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
                    
                    _, col_descarga, _ = st.columns([1, 2, 1])
                    with col_descarga:
                        st.success("✅ Informe PDF listo para descargar.")
                        st.download_button("📥 Descargar Informe Anerpro (PDF)", data=pdf_buf.getvalue(), file_name=f"Analisis_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)
                
                except Exception as e: 
                    error_str = str(e)
                    if "503" in error_str or "UNAVAILABLE" in error_str:
                        st.error("❌ **Google Gemini Caído**: Los servidores están sufriendo una caída temporal. Inténtalo de nuevo en unos minutos.")
                    elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        st.error("❌ **Límite alcanzado**: Has agotado tu cuota de Gemini. Revisa Google AI Studio.")
                    else:
                        st.error(f"Error interno: {e}")
