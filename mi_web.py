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
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="🤖", layout="wide")

# --- TRUCO CSS: LOGO ARRIBA Y BOTÓN ABAJO ---
st.markdown(
    """
    <style>
        /* Elimina espacios innecesarios en la parte superior */
        [data-testid="stSidebarUserContent"] {
            padding-top: 0rem;
            display: flex;
            flex-direction: column;
            height: 90vh; /* Altura de la barra lateral */
        }
        
        /* Empuja el último elemento (botón cerrar sesión) al fondo */
        [data-testid="stSidebarUserContent"] > div:last-child {
            margin-top: auto;
            padding-bottom: 20px;
        }

        /* Sube el logo un poco más */
        [data-testid="stSidebar"] img {
            margin-top: -30px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.title("🔒 Acceso Corporativo")
    password_input = st.text_input("Introduce la contraseña para acceder:", type="password")
    if st.button("Entrar"):
        if password_input == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    # --- 3. CONFIGURACIÓN Y KEYWORDS ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    DIAS_RETENCION = 5
    
    KEYWORDS = [
        "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", 
        "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", 
        "industria 4.0", "scada", "certificado", "autoconsumo", "plc", 
        "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", 
        "digitalizacion industrial", "gemelo digital", "auditoria energetica"
    ]

    # --- 4. FUNCIONES DE PROCESAMIENTO ---
    def normalizar_texto(texto):
        if not texto: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

    def formatear_moneda_es(valor_str):
        if not valor_str or "Ver en PDF" in str(valor_str): return valor_str
        try:
            limpio = "".join(c for c in str(valor_str) if c.isdigit() or c in ".,")
            if "." in limpio and "," in limpio:
                limpio = limpio.replace(".", "").replace(",", ".")
            elif "," in limpio:
                limpio = limpio.replace(",", ".")
            numero = float(limpio)
            return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except:
            return valor_str

    def extraer_presupuesto(texto):
        if not texto: return "Ver en PDF"
        texto_limpio = re.sub(r'<[^>]*>', ' ', texto)
        patrones = [
            r"(?:Importe|Importe neto|Valor estimado|PVP):\s*([\d\.]+(?:,\d{1,2})?)",
            r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€|Euros)",
            r"([\d\.]+(?:\d{3})?)\s*(?:EUR|€|Euros)"
        ]
        for p in patrones:
            match = re.search(p, texto_limpio, re.IGNORECASE)
            if match:
                return formatear_moneda_es(match.group(1).strip())
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
                        if "Presupuesto" in item:
                            item["Presupuesto"] = formatear_moneda_es(item["Presupuesto"])
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
        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
            json.dump(historial_actual, f, indent=4, ensure_ascii=False)
        return historial_actual, añadidas

    # --- 5. BARRA LATERAL (Sidebar) ---
    with st.sidebar:
        # LOGO ARRIBA
        if os.path.exists("logo.png"):
            st.image("logo.png", width=150)
            st.divider()
        
        # MANTENIMIENTO EN EL MEDIO
        st.caption("⚙️ Mantenimiento")
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()

        # CIERRE DE SESIÓN AL FINAL (Gracias al CSS flexbox)
        # Ponemos un contenedor vacío para ayudar al margen si es necesario
        st.write("") 
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 6. CUERPO PRINCIPAL ---
    st.title("Radar de Licitaciones 🏢")
    
    tab1, tab2 = st.tabs(["🔍 Buscar Nuevas", "📁 Archivo e Informes"])
    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    with tab1:
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                ofertas_encontradas = []
                
                for entrada in feed.entries:
                    resumen_raw = entrada.summary if 'summary' in entrada else ""
                    texto_comp = normalizar_texto(entrada.title + " " + resumen_raw)
                    coin = sorted(list(set([kw.upper() for kw in KEYWORDS if normalizar_texto(kw) in texto_comp])))
                    
                    if coin:
                        organismo = "No detectado"
                        m_org = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", resumen_raw, re.I | re.S)
                        if m_org: organismo = m_org.group(1).strip()
                        elif entrada.get('author'): organismo = entrada.author

                        try: fecha_pub = datetime(*entrada.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: fecha_pub = datetime.now().strftime("%d/%m/%Y")

                        ofertas_encontradas.append({
                            "Publicado": fecha_pub, 
                            "Organismo": organismo,
                            "Título": entrada.title,
                            "Presupuesto": extraer_presupuesto(resumen_raw),
                            "Palabras Detectadas": ", ".join(coin), 
                            "Enlace Oficial": entrada.link
                        })

            historial, nuevas = guardar_en_historial(ofertas_encontradas)
            if nuevas > 0:
                st.success(f"¡Se han detectado {nuevas} nuevas!")
                df_nuevas = pd.DataFrame(historial[-nuevas:])
                for c in columnas_ver:
                    if c not in df_nuevas.columns: df_nuevas[c] = "N/A"
                st.dataframe(df_nuevas[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else:
                st.info("No hay novedades.")

    with tab2:
        historial = cargar_y_limpiar_historial()
        if historial:
            df_hist = pd.DataFrame(list(reversed(historial)))
            for c in columnas_ver:
                if c not in df_hist.columns: df_hist[c] = "N/A"
            
            busqueda = st.text_input("Buscar en el historial:")
            if busqueda:
                df_hist = df_hist[df_hist.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().str.cat(), axis=1)]

            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
            
            st.download_button(label="📥 Descargar Historial en Excel", data=buffer.getvalue(), file_name="informe_licitaciones.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
