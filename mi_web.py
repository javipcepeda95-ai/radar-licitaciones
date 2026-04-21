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
st.set_page_config(page_title="Radar de Licitaciones - Anerpro", page_icon="📡", layout="wide")

# ==============================================================================
# --- 2. EL CEREBRO DE ESTILO (SUPER CSS PERSONALIZADO) ---
# ==============================================================================
# Aquí está todo el estilo para replicar la imagen que me enviaste.
# Esto incluye el título, el icono del radar, las pestañas de colores y el botón.
st.markdown(
    """
    <style>
        /* --- ESTILO GLOBAL Y COLORES --- */
        :root {
            --coral-red: #FF4B4B; /* El color rojo/coral exacto de la imagen */
            --dark-gray: #31333F;
            --tab-gray: #555;
            --border-gray: #DDD;
        }
        
        /* Asegurar tipografía profesional */
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');
        
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Source Sans Pro', sans-serif;
            color: var(--dark-gray);
        }

        /* --- ESTILO DE LA BARRA LATERAL (Ajuste del logo arriba) --- */
        [data-testid="stSidebarNav"] { display: none !important; }
        section[data-testid="stSidebar"] .st-emotion-cache-6qob1r { padding-top: 0rem !important; }
        [data-testid="stSidebar"] img { margin-top: -30px !important; }
        [data-testid="stSidebarUserContent"] {
            display: flex !important;
            flex-direction: column !important;
            height: 95vh !important;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div:last-child {
            margin-top: auto !important;
            padding-bottom: 20px !important;
        }

        /* --- ESTILO DEL TÍTULO PRINCIPAL (Radar + Texto) --- */
        .radar-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: 10px;
            margin-bottom: 5px;
        }
        .radar-header h1 {
            font-size: 2.8rem;
            font-weight: 700;
            color: var(--dark-gray);
            margin: 0;
            padding: 0;
            border: none;
        }
        .radar-icon {
            width: 40px;
            height: 40px;
        }

        /* --- ESTILO DE LAS PESTAÑAS (Imitando la imagen) --- */
        /* Eliminamos el estilo de radio nativo y lo hacemos horizontal */
        div[data-testid="stMarkdownContainer"] + div[role="radiogroup"] {
            display: flex;
            flex-direction: row;
            border-bottom: 1px solid var(--border-gray);
            margin-bottom: 20px;
            gap: 20px;
            padding-bottom: 0px;
        }
        
        /* Estilo base para todas las opciones (labels) del radio */
        div[role="radiogroup"] label {
            padding: 5px 10px 10px 10px !important;
            border: none !important;
            border-radius: 0px !important;
            background: none !important;
            cursor: pointer;
            position: relative;
            margin: 0 !important;
            font-weight: 400;
            transition: all 0.2s ease;
        }
        
        /* Estilo base para el texto dentro de la label */
        div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
            color: var(--tab-gray) !important;
            font-size: 1.1rem;
        }
        
        /* Ocultar el círculo del radiobutton */
        div[role="radiogroup"] input[type="radio"] {
            display: none;
        }

        /* --- PESTAÑA 1: "Buscar Nuevas" --- */
        /* Targeteamos la primera opción del radio */
        div[role="radiogroup"] label:nth-child(1) div[data-testid="stMarkdownContainer"] p {
            font-family: 'Source Sans Pro', sans-serif !important;
        }
        
        /* Cuando la primera opción está seleccionada (ACTIVA) */
        div[role="radiogroup"] label:nth-child(1):has(input:checked) {
            border-bottom: 3px solid var(--coral-red) !important;
        }
        
        /* Color del texto de la primera pestaña (NUEVAS) SIEMPRE en ROJO como en la imagen */
        div[role="radiogroup"] label:nth-child(1) div[data-testid="stMarkdownContainer"] * {
            color: var(--coral-red) !important;
        }

        /* --- PESTAÑA 2: "Archivo e Informes" --- */
        /* Cuando la segunda opción está seleccionada (ACTIVA) */
        div[role="radiogroup"] label:nth-child(2):has(input:checked) {
            border-bottom: 3px solid var(--coral-red) !important;
        }
        
        /* Color del texto de la segunda pestaña SIEMPRE en GRIS */
        div[role="radiogroup"] label:nth-child(2) div[data-testid="stMarkdownContainer"] * {
            color: var(--tab-gray) !important;
        }

        /* Efecto hover ligero para ambas */
        div[role="radiogroup"] label:hover {
            opacity: 0.8;
        }

        /* --- ESTILO DEL BOTÓN PRINCIPAL (Coral Red) --- */
        /* Targeteamos botones que son primarios */
        .stButton button[kind="primary"] {
            background-color: var(--coral-red) !important;
            color: white !important;
            font-weight: 600 !important;
            padding: 10px 24px !important;
            border-radius: 6px !important;
            border: none !important;
            font-size: 1rem !important;
            transition: background-color 0.2s ease;
        }
        .stButton button[kind="primary"]:hover {
            background-color: #e34343 !important; /* Un rojo un poco más oscuro al pasar el ratón */
        }
        .stButton button[kind="primary"]:active {
            background-color: #cc3c3c !important;
        }
        
        /* Ancho completo para botones en la sidebar */
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
        }
        
        /* --- ESTILO DE TABLAS (Dataframe) --- */
        /* Hacer que las tablas sean limpias y legibles */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--border-gray);
            border-radius: 6px;
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
    
    # Cabecera de login simple
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"): st.image("logo.png", width=120)
    with col2: st.title("🔒 Acceso Corporativo")
    
    pwd = st.text_input("Contraseña corporativa:", type="password")
    if st.button("Entrar"):
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
    
    # Palabras clave profesionales de Anerpro
    KEYWORDS = ["energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    # --- 5. FUNCIONES DE PROCESAMIENTO ---
    def normalizar(t):
        if not t: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')

    def formatear_moneda(v_str):
        if not v_str or "Ver en PDF" in str(v_str): return v_str
        try:
            limpio = "".join(c for c in str(v_str) if c.isdigit() or c in ".,")
            if "." in limpio and "," in limpio: limpio = limpio.replace(".", "").replace(",", ".")
            elif "," in limpio: limpio = limpio.replace(",", ".")
            num = float(limpio)
            return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except: return v_str

    def extraer_presupuesto(texto):
        if not texto: return "Ver en PDF"
        texto_l = re.sub(r'<[^>]*>', ' ', texto)
        patrones = [
            r"(?:Importe|Importe neto|Valor estimado|PVP):\s*([\d\.]+(?:,\d{1,2})?)",
            r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€|Euros)",
            r"([\d\.]+(?:\d{3})?)\s*(?:EUR|€|Euros)"
        ]
        for p in patrones:
            match = re.search(p, texto_l, re.I)
            if match: return formatear_moneda(match.group(1).strip())
        return "Ver en PDF"

    def cargar_y_limpiar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: datos = json.load(f)
                except: return []
            f_limite = datetime.now() - timedelta(days=DIAS_RETENCION)
            datos_l = []
            for item in datos:
                try:
                    f_str = item.get("Detectado el") or item.get("Detectado")
                    f_item = datetime.strptime(str(f_str), "%Y-%m-%d %H:%M:%S") if "-" in str(f_str) else datetime.strptime(str(f_str), "%d/%m/%Y %H:%M")
                    if f_item >= f_limite:
                        if "Presupuesto" in item: item["Presupuesto"] = formatear_moneda(item["Presupuesto"])
                        datos_l.append(item)
                except: pass
            return datos_l
        return []

    def guardar_en_historial(nuevas_ofertas):
        historial_actual = cargar_y_limpiar_historial()
        enlaces_vistos = {o["Enlace Oficial"] for o in historial_actual}
        añadidas = 0
        for o in nuevas_ofertas:
            if o["Enlace Oficial"] not in enlaces_vistos:
                o["Detectado el"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                historial_actual.append(o)
                añadidas += 1
        if añadidas > 0:
            with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
                json.dump(historial_actual, f, indent=4, ensure_ascii=False)
        return historial_actual, añadidas

    # --- 6. BARRA LATERAL ---
    with st.sidebar:
        # LOGO ARRIBA (Subido con CSS)
        if os.path.exists("logo.png"): st.image("logo.png", width=130)
        
        st.divider()
        
        # MANTENIMIENTO (Centro)
        st.caption("⚙️ Mantenimiento")
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()
        
        # BOTÓN CERRAR SESIÓN (Al fondo con CSS)
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()

    # ==============================================================================
    # --- 7. CUERPO PRINCIPAL ---
    # ==============================================================================
    
    # --- TÍTULO Y ICONO DE RADAR (Replicando la imagen) ---
    # Icono de radar SVG creado directamente en el código
    st.markdown(
        """
        <div class="radar-header">
            <svg class="radar-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 21V12M12 12H12.01M12 12C9.23858 12 7 14.2386 7 17M12 12C14.7614 12 17 14.2386 17 17M12 7C17.5228 7 22 11.4772 22 17M12 7C6.47715 7 2 11.4772 2 17" stroke="#31333F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M12 2C15.866 2 19 5.13401 19 9M12 2C8.13401 2 5 5.13401 5 9" stroke="#FF4B4B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <h1>Radar de Licitaciones</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.divider() # Línea de separación debajo del título

    # --- PESTAÑAS PERSONALIZADAS (Usando st.radio estilizado con CSS) ---
    st.markdown("### Navegación") # Necesitamos una cabecera oculta para que el CSS funcione
    
    pestanas = [
        "🔍 Buscar Nuevas", 
        "📁 Archivo e Informes"
    ]
    # Este radio se comportará como las pestañas de colores de tu imagen
    tab_seleccionada = st.radio(
        label="Menu principal",
        options=pestanas,
        label_visibility="collapsed",
        horizontal=True
    )
    
    st.markdown("---") # La línea gris que separa las pestañas del contenido

    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    # --- CONTENIDO DE LAS PESTAÑAS ---
    
    # 🔍 PESTAÑA: BUSCAR NUEVAS
    if tab_seleccionada == pestanas[0]:
        # El botón rojo coral que querías (kind="primary" para estilizarlo con CSS)
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
                st.success(f"¡Se han detectado {nuevas} oportunidades nuevas para Anerpro!")
                df = pd.DataFrame(historial[-nuevas:])
                st.dataframe(df[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else: st.info("No hay novedades interesantes en este momento.")

    # 📁 PESTAÑA: ARCHIVO E INFORMES
    else:
        st.subheader("Buscador en el Historial de Anerpro")
        historial = cargar_y_limpiar_historial()
        if historial:
            df_hist = pd.DataFrame(list(reversed(historial)))
            busq = st.text_input("Buscar por Organismo o Título:")
            if busq: df_hist = df_hist[df_hist.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
            st.download_button(label="📥 Descargar Historial en Excel", data=buffer.getvalue(), file_name="informe.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else: st.info("El historial está vacío. Realiza una búsqueda para llenarlo.")
