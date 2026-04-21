import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import re
import io

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="📡", layout="wide")

# ==============================================================================
# --- 2. CSS LIMPIO Y TOTALMENTE SEGURO ---
# ==============================================================================
st.markdown(
    """
    <style>
        :root { --coral-red: #FF4B4B; }
        
        /* Ocultar barra superior vacía de Streamlit */
        [data-testid="stSidebarNav"] { display: none !important; }
        
        /* Ajustar el logo arriba */
        [data-testid="stSidebar"] img {
            margin-top: -30px !important;
            margin-bottom: 10px !important;
        }

        /* Subir el contenido principal quitando el margen gigante por defecto */
        .block-container {
            padding-top: 2rem !important; 
        }

        /* --- ESTILOS DE CABECERA --- */
        .radar-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
        }
        .radar-header h1 {
            font-size: 2.8rem;
            font-weight: 700;
            color: #31333F;
            margin: 0;
            padding: 0;
        }

        /* Botón rojo corporativo (Actualizar) */
        .stButton button[kind="primary"] {
            background-color: var(--coral-red) !important;
            color: white !important;
            border: none !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
        }
        .stButton button[kind="primary"]:hover {
            background-color: #e34343 !important;
        }
        
        /* Botones de acción en tablas (Descargar / Reset) */
        .action-buttons .stButton button {
            font-weight: 600 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 3. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"): st.image("logo.png", width=120)
    with col2: st.title("🔒 Acceso Anerpro")
    
    pwd = st.text_input("Contraseña corporativa:", type="password")
    if st.button("Entrar", type="primary"):
        if pwd == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    DIAS_RETENCION = 5
    KEYWORDS = ["energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    # --- 5. FUNCIONES ---
    def normalizar(t): return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn') if t else ""
    def formatear_moneda(v):
        if not v or "PDF" in str(v): return v
        try:
            l = "".join(c for c in str(v) if c.isdigit() or c in ".,")
            if "." in l and "," in l: l = l.replace(".", "").replace(",", ".")
            elif "," in l: l = l.replace(",", ".")
            return f"{float(l):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except: return v
    def extraer_presupuesto(texto):
        if not texto: return "Ver en PDF"
        t = re.sub(r'<[^>]*>', ' ', texto)
        for p in [r"(?:Importe|Valor estimado):\s*([\d\.]+(?:,\d{1,2})?)", r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]:
            m = re.search(p, t, re.I)
            if m: return formatear_moneda(m.group(1).strip())
        return "Ver en PDF"

    def cargar_y_limpiar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: d = json.load(f)
                except: return []
            fl = datetime.now() - timedelta(days=DIAS_RETENCION)
            dl = []
            for i in d:
                try:
                    fs = i.get("Detectado el") or i.get("Detectado")
                    fi = datetime.strptime(str(fs), "%Y-%m-%d %H:%M:%S") if "-" in str(fs) else datetime.strptime(str(fs), "%d/%m/%Y %H:%M")
                    if fi >= fl:
                        if "Presupuesto" in i: i["Presupuesto"] = formatear_moneda(i["Presupuesto"])
                        dl.append(i)
                except: pass
            return dl
        return []

    def guardar_en_historial(nuevas):
        hist = cargar_y_limpiar_historial()
        vistos = {o["Enlace Oficial"] for o in hist}
        añadidas = 0
        for o in nuevas:
            if o["Enlace Oficial"] not in vistos:
                o["Detectado el"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                hist.append(o)
                añadidas += 1
        if añadidas > 0:
            with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f: json.dump(hist, f, indent=4, ensure_ascii=False)
        return hist, añadidas

    # --- 6. BARRA LATERAL (NAVEGACIÓN) ---
    with st.sidebar:
        # Logo
        if os.path.exists("logo.png"): st.image("logo.png", width=140)
        
        st.divider()
        
        # Pestaña desplegable de navegación
        with st.expander("📡 Radar de Licitaciones", expanded=True):
            opcion_navegacion = st.radio(
                "Menú", 
                ["Busqueda Licitaciones", "Archivos e Informes"],
                label_visibility="collapsed"
            )
            
        # ESPACIADOR INVISIBLE para empujar el botón de Cerrar Sesión al fondo
        st.markdown("<div style='height: 55vh;'></div>", unsafe_allow_html=True)
        
        # Cerrar Sesión
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 7. CUERPO PRINCIPAL ---
    # Icono de Radar de Pantalla
    st.markdown(
        """
        <div class="radar-header">
            <svg width="45" height="45" viewBox="0 0 24 24" fill="none" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" stroke-width="1.5"></circle>
                <circle cx="12" cy="12" r="6" stroke-width="1" stroke-dasharray="2 2"></circle>
                <line x1="12" y1="2" x2="12" y2="22" stroke-width="1" opacity="0.3"></line>
                <line x1="2" y1="12" x2="22" y2="12" stroke-width="1" opacity="0.3"></line>
                <line x1="12" y1="12" x2="19" y2="5" stroke="#FF4B4B" stroke-width="2"></line>
                <circle cx="12" cy="12" r="2" fill="#FF4B4B" stroke="#FF4B4B"></circle>
            </svg>
            <h1>Radar de Licitaciones</h1>
        </div>
        """, unsafe_allow_html=True
    )

    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    # --- LÓGICA DE VISTAS BASADA EN EL MENÚ LATERAL ---
    
    # VISTA 1: BÚSQUEDA
    if opcion_navegacion == "Busqueda Licitaciones":
        st.subheader("Búsqueda en Tiempo Real")
        st.write("Pulsa el botón para escanear las últimas publicaciones de la Plataforma de Contratación del Estado.")
        
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma del Estado...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar(e.title + " " + res)
                    coin = sorted(list(set([k.upper() for k in KEYWORDS if normalizar(k) in txt])))
                    if coin:
                        org = "No detectado"
                        m = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", res, re.I | re.S)
                        if m: org = m.group(1).strip()
                        elif e.get('author'): org = e.author
                        try: f_pub = datetime(*e.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: f_pub = datetime.now().strftime("%d/%m/%Y")
                        encontradas.append({"Publicado": f_pub, "Organismo": org, "Título": e.title, "Presupuesto": extraer_presupuesto(res), "Palabras Detectadas": ", ".join(coin), "Enlace Oficial": e.link})

            historial, nuevas = guardar_en_historial(encontradas)
            if nuevas > 0:
                st.success(f"¡Detectadas {nuevas} nuevas oportunidades!")
                df = pd.DataFrame(historial[-nuevas:])
                for c in columnas_ver:
                    if c not in df.columns: df[c] = "N/A"
                st.dataframe(df[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else: st.info("No hay novedades interesantes en este momento. Inténtalo más tarde.")

    # VISTA 2: ARCHIVOS E INFORMES
    elif opcion_navegacion == "Archivos e Informes":
        st.subheader("Base de Datos e Informes")
        hist = cargar_y_limpiar_historial()
        
        if hist:
            df_hist = pd.DataFrame(list(reversed(hist)))
            for c in columnas_ver:
                if c not in df_hist.columns: df_hist[c] = "N/A"
                
            busq = st.text_input("Buscar por Organismo o Título:")
            if busq: df_hist = df_hist[df_hist.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            
            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            st.write("---") # Línea separadora
            
            # BOTONES JUNTOS AL FINAL DE LA PÁGINA
            st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([2, 2, 4]) # El col3 vacío empuja los botones a la izquierda
            
            with col1:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
                st.download_button(label="Descargar Excel", data=buffer.getvalue(), file_name="informe_licitaciones.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            with col2:
                # El botón ahora se llama solo "Reset"
                if st.button("Reset", use_container_width=True):
                    if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        else: 
            st.info("El historial está vacío. Ve a la sección 'Busqueda Licitaciones' para escanear.")
