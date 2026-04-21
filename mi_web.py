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
# --- 2. EL CEREBRO DE ESTILO (SUPER CSS PERSONALIZADO) ---
# ==============================================================================
st.markdown(
    """
    <style>
        /* --- ESTILO GLOBAL --- */
        :root {
            --coral-red: #FF4B4B;
            --dark-gray: #31333F;
            --border-gray: #DDD;
        }

        /* --- BARRA LATERAL: LOGO ARRIBA Y BOTÓN ABAJO --- */
        [data-testid="stSidebarNav"] { display: none !important; }
        
        /* Forzamos que el contenido de la sidebar sea un contenedor flexible */
        [data-testid="stSidebarUserContent"] {
            display: flex !important;
            flex-direction: column !important;
            height: 96vh !important;
        }

        /* El bloque de botones de mantenimiento y logo se queda arriba */
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
            flex-grow: 1 !important;
        }

        /* Empujamos específicamente el último botón (Cerrar Sesión) al fondo */
        /* Buscamos el contenedor del último botón */
        div.stButton:last-child {
            margin-top: auto !important;
            padding-bottom: 20px;
        }

        /* Ajuste del logo para que esté en la esquina */
        [data-testid="stSidebar"] img {
            margin-top: -45px !important;
            margin-bottom: 10px !important;
        }

        /* --- TÍTULO Y RADAR MEJORADO --- */
        .radar-header {
            display: flex;
            align-items: center;
            gap: 18px;
            margin-bottom: 10px;
        }
        .radar-header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--dark-gray);
            margin: 0;
            border: none;
        }
        .radar-svg {
            width: 50px;
            height: 50px;
        }

        /* --- PESTAÑAS (RADIO ESTILIZADO) --- */
        div[role="radiogroup"] {
            display: flex;
            gap: 30px;
            border-bottom: 1px solid var(--border-gray);
            padding-bottom: 0px;
        }
        div[role="radiogroup"] label {
            padding-bottom: 10px !important;
            border-radius: 0px !important;
            background: none !important;
            border: none !important;
            margin-bottom: -1px !important;
        }
        /* Ocultamos el círculo del radio */
        div[role="radiogroup"] label span[data-testid="stWidgetLabel"] {
            font-size: 1.1rem !important;
            font-weight: 600 !important;
        }
        div[role="radiogroup"] input[type="radio"] { display: none; }

        /* Efecto de línea roja debajo de la pestaña activa */
        div[role="radiogroup"] label:has(input:checked) {
            border-bottom: 3px solid var(--coral-red) !important;
        }

        /* Colores específicos para que coincidan con tu imagen */
        div[role="radiogroup"] label:nth-child(1) span { color: var(--coral-red) !important; }
        div[role="radiogroup"] label:nth-child(2) span { color: #666 !important; }

        /* --- BOTÓN ACTUALIZAR (ROJO CORAL) --- */
        .stButton button[kind="primary"] {
            background-color: var(--coral-red) !important;
            border: none !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 3. SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.title("🔒 Acceso Anerpro")
    pwd = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("⚠️ Incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    KEYWORDS = ["energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    def normalizar(t):
        return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')

    def formatear_moneda(v):
        if not v or "PDF" in str(v): return v
        try:
            limpio = "".join(c for c in str(v) if c.isdigit() or c in ".,")
            if "." in limpio and "," in limpio: limpio = limpio.replace(".", "").replace(",", ".")
            elif "," in limpio: limpio = limpio.replace(",", ".")
            return f"{float(limpio):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except: return v

    def extraer_presupuesto(texto):
        if not texto: return "Ver en PDF"
        texto = re.sub(r'<[^>]*>', ' ', texto)
        patrones = [r"(?:Importe|Valor estimado):\s*([\d\.]+(?:,\d{1,2})?)", r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€)"]
        for p in patrones:
            match = re.search(p, texto, re.I)
            if match: return formatear_moneda(match.group(1).strip())
        return "Ver en PDF"

    # --- 5. BARRA LATERAL ---
    with st.sidebar:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=140)
        
        st.divider()
        st.caption("⚙️ Mantenimiento")
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()
        
        # Este botón siempre se irá al fondo por el CSS 'margin-top: auto'
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 6. CUERPO PRINCIPAL ---
    
    # NUEVO ICONO DE RADAR MÁS PROFESIONAL (SVG)
    st.markdown(
        """
        <div class="radar-header">
            <svg class="radar-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="45" fill="none" stroke="#31333F" stroke-width="1" opacity="0.2"/>
                <circle cx="50" cy="50" r="30" fill="none" stroke="#31333F" stroke-width="1" opacity="0.2"/>
                <circle cx="50" cy="50" r="15" fill="none" stroke="#31333F" stroke-width="1" opacity="0.2"/>
                <line x1="50" y1="5" x2="50" y2="95" stroke="#31333F" stroke-width="1" opacity="0.2"/>
                <line x1="5" y1="50" x2="95" y2="50" stroke="#31333F" stroke-width="1" opacity="0.2"/>
                <path d="M 50 50 L 50 5 A 45 45 0 0 1 95 50 Z" fill="#FF4B4B" opacity="0.3"/>
                <line x1="50" y1="50" x2="50" y2="5" stroke="#FF4B4B" stroke-width="2"/>
                <circle cx="50" cy="50" r="3" fill="#31333F"/>
            </svg>
            <h1>Radar de Licitaciones</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("### Navegación")
    tab_seleccionada = st.radio(
        label="Menu",
        options=["🔍 Buscar Nuevas", "📁 Archivo e Informes"],
        label_visibility="collapsed",
        horizontal=True
    )
    
    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    if "🔍" in tab_seleccionada:
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
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

                if encontradas:
                    # Lógica de guardado simplificada para el ejemplo
                    st.success(f"¡Detectadas {len(encontradas)} nuevas!")
                    st.dataframe(pd.DataFrame(encontradas)[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay novedades.")

    else:
        st.info("Pestaña de historial y exportación a Excel activa.")
