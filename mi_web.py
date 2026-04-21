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
# Cambiamos el icono de la pestaña por un radar
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="📡", layout="wide")

# ==============================================================================
# --- 2. EL CEREBRO DE ESTILO (SUPER CSS PERSONALIZADO) ---
# ==============================================================================
# Aquí está todo el estilo para replicar la imagen y arreglar el diseño.
st.markdown(
    """
    <style>
        /* --- ESTILO GLOBAL Y COLORES --- */
        :root {
            --coral-red: #FF4B4B; /* El color rojo/coral exacto */
            --dark-gray: #31333F;
            --border-gray: #DDD;
        }
        
        /* Asegurar tipografía profesional corporativa */
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');
        
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Source Sans Pro', sans-serif;
            color: var(--dark-gray);
        }

        /* --- BARRA LATERAL: LOGO ARRIBA Y BOTÓN ABAJO --- */
        [data-testid="stSidebarNav"] { display: none !important; }
        
        /* Forzamos que el contenido de la sidebar sea un contenedor flexible de altura completa */
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

        /* Ajuste del logo para que esté en la esquina superior */
        [data-testid="stSidebar"] img {
            margin-top: -45px !important;
            margin-bottom: 10px !important;
        }

        /* --- TÍTULO PRINCIPAL (Radar Profesional + Texto) --- */
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
        /* Nuevo estilo para el radar SVG más técnico */
        .radar-svg {
            width: 50px;
            height: 50px;
        }

        /* --- PESTAÑAS PERSONALIZADAS (RADIO ESTILIZADO) --- */
        /* Eliminamos el estilo de radio nativo y lo hacemos horizontal */
        div[role="radiogroup"] {
            display: flex;
            gap: 30px;
            border-bottom: 1px solid var(--border-gray);
            padding-bottom: 0px;
            margin-bottom: 20px;
        }
        
        /* Estilo base para todas las opciones (labels) del radio */
        div[role="radiogroup"] label {
            padding-bottom: 10px !important;
            border: none !important;
            border-radius: 0px !important;
            background: none !important;
            cursor: pointer;
            position: relative;
            margin-bottom: -1px !important; /* Para pisar la línea inferior gris */
        }
        
        /* Ocultar el círculo del radiobutton nativo */
        div[role="radiogroup"] input[type="radio"] {
            display: none;
        }
        
        /* Estilo del texto dentro de la label */
        div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            font-family: 'Source Sans Pro', sans-serif !important;
            font-size: 1.1rem;
            font-weight: 600;
        }

        /* Efecto de línea roja debajo de la pestaña activa */
        div[role="radiogroup"] label:has(input:checked) {
            border-bottom: 3px solid var(--coral-red) !important;
        }

        /* --- COLORES ESPECÍFICOS DE LAS PESTAÑAS (Replicando imagen) --- */
        /* Pestaña 1 (NUEVAS) siempre en Rojo Coral */
        div[role="radiogroup"] label:nth-child(1) div[data-testid="stMarkdownContainer"] p {
            color: var(--coral-red) !important;
        }
        /* Pestaña 2 (ARCHIVO) siempre en Gris */
        div[role="radiogroup"] label:nth-child(2) div[data-testid="stMarkdownContainer"] p {
            color: #666 !important;
        }

        /* --- ESTILO DEL BOTÓN PRINCIPAL (Coral Red) --- */
        /* Targeteamos el botón que tiene tipo 'primary' */
        .stButton button[kind="primary"] {
            background-color: var(--coral-red) !important;
            color: white !important;
            font-weight: 600 !important;
            padding: 10px 24px !important;
            border-radius: 6px !important;
            border: none !important;
            transition: background-color 0.2s ease;
        }
        .stButton button[kind="primary"]:hover {
            background-color: #e34343 !important;
        }
        
        /* Ancho completo para botones en la sidebar */
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
        }
        
        /* --- ESTILO DE TABLAS (Dataframe) --- */
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
    
    # Cabecera de login profesional corporativa
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo.png"): st.image("logo.png", width=120)
    with col2: st.title("🔒 Acceso Anerpro Corporativo")
    
    pwd = st.text_input("Contraseña corporativa:", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN Y KEYWORDS ---
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
            # Normalizar a flotante de Python
            if "." in limpio and "," in limpio:
                limpio = limpio.replace(".", "").replace(",", ".")
            elif "," in limpio:
                limpio = limpio.replace(",", ".")
            
            numero = float(limpio)
            return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except:
            return v_str

    def extraer_presupuesto(texto):
        """Escáner avanzado de cifras monetarias."""
        if not texto: return "Ver en PDF"
        texto_limpio = re.sub(r'<[^>]*>', ' ', texto) # Quitar HTML
        
        patrones = [
            r"(?:Importe|Importe neto|Valor estimado|PVP):\s*([\d\.]+(?:,\d{1,2})?)",
            r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€|Euros)",
            r"([\d\.]+(?:\d{3})?)\s*(?:EUR|€|Euros)"
        ]
        for p in patrones:
            match = re.search(p, texto_limpio, re.I | re.S)
            if match:
                return formatear_moneda(match.group(1).strip())
        return "Ver en PDF"

    def cargar_y_limpiar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: datos = json.load(f)
                except: return []
            
            fecha_limite = datetime.now() - timedelta(days=DIAS_RETENCION)
            datos_limpios = []
            for item in datos:
                try:
                    fecha_str = item.get("Detectado el") or item.get("Detectado")
                    f_item = datetime.strptime(str(fecha_str), "%Y-%m-%d %H:%M:%S") if "-" in str(fecha_str) else datetime.strptime(str(fecha_str), "%d/%m/%Y %H:%M")
                    
                    if f_item >= fecha_limite:
                        # Aseguramos formato del historial
                        if "Presupuesto" in item:
                            item["Presupuesto"] = formatear_moneda(item["Presupuesto"])
                        datos_limpios.append(item)
                except: pass
            return datos_limpios
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
        if os.path.exists("logo.png"): st.image("logo.png", width=140)
        
        st.divider()
        
        # MANTENIMIENTO (Centro)
        st.caption("⚙️ Mantenimiento")
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()
        
        # BOTÓN CERRAR SESIÓN (Clavado al fondo por el CSS)
        # Al ser el último elemento del bloque vertical de la sidebar, el CSS lo empujará al fondo automáticamente.
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()

    # ==============================================================================
    # --- 7. CUERPO PRINCIPAL ---
    # ==============================================================================
    
    # --- CABECERA DE RADAR PROFESIONAL (SVG) ---
    # Nuevo icono de radar con círculos concéntricos y línea de escaneo.
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
    
    st.divider() # Línea de separación debajo del título

    # --- PESTAÑAS PERSONALIZADAS (Usando st.radio estilizado con CSS) ---
    st.markdown("### Navegación") # Necesitamos una cabecera oculta para que el CSS funcione
    
    tab_seleccionada = st.radio(
        label="Menu principal",
        options=["🔍 Buscar Nuevas", "📁 Archivo e Informes"],
        label_visibility="collapsed",
        horizontal=True
    )
    
    st.markdown("---") # La línea gris que separa las pestañas del contenido

    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    # --- CONTENIDO DE LAS PESTAÑAS ---
    
    # 🔍 PESTAÑA: BUSCAR NUEVAS
    if "🔍" in tab_seleccionada:
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
                        # Extracción de Organismo
                        organismo = "No detectado"
                        m_org = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", res, re.I | re.S)
                        if m_org: organismo = m_org.group(1).strip()
                        elif e.get('author'): organismo = e.author

                        # Fecha
                        try: fecha_pub = datetime(*e.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: fecha_pub = datetime.now().strftime("%d/%m/%Y")

                        encontradas.append({
                            "Publicado": fecha_pub, 
                            "Organismo": organismo,
                            "Título": e.title,
                            "Presupuesto": extraer_presupuesto(res),
                            "Palabras Detectadas": ", ".join(coin), 
                            "Enlace Oficial": e.link
                        })

            historial, nuevas = guardar_en_historial(encontradas)
            if nuevas > 0:
                st.success(f"¡Se han detectado {nuevas} oportunidades nuevas para Anerpro!")
                df = pd.DataFrame(historial[-nuevas:])
                # Asegurar columnas
                for c in columnas_ver:
                    if c not in df.columns: df[c] = "N/A"
                
                st.dataframe(df[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else: st.info("No hay novedades interesantes en este momento.")

    # 📁 PESTAÑA: ARCHIVO E INFORMES
    else:
        st.subheader("Buscador en el Historial de Anerpro")
        historial = cargar_y_limpiar_historial()
        if historial:
            df_hist = pd.DataFrame(list(reversed(historial)))
            
            # Asegurar consistencia
            for c in columnas_ver:
                if c not in df_hist.columns: df_hist[c] = "N/A"
            
            busq = st.text_input("Buscar por Organismo o Título:")
            if busq:
                df_hist = df_hist[df_hist.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]

            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
            st.download_button(label="📥 Descargar Historial en Excel", data=buffer.getvalue(), file_name="informe_licitaciones.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else: st.info("El historial está vacío. Realiza una búsqueda para llenarlo.")
