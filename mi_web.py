import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import re
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro Licitaciones", page_icon="🤖", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🔒 Acceso Restringido")
    password_input = st.text_input("Introduce la contraseña para acceder:", type="password")
    if st.button("Entrar"):
        if password_input == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
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

    def normalizar_texto(texto):
        if not texto: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

    def extraer_presupuesto(texto):
        # Busca patrones numéricos seguidos de EUR, € o euros
        patron = r"([\d\.]+,\d{2})\s*(?:EUR|€|euros)"
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return match.group(1) + " €"
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
                    if "-" in str(fecha_str):
                        fecha_item = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        fecha_item = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                    if fecha_item >= fecha_limite:
                        datos_limpios.append(item)
                except: pass
            return datos_limpios
        return []

    def guardar_en_historial(nuevas_ofertas):
        historial_actual = cargar_y_limpiar_historial()
        enlaces_vistos = {oferta["Enlace Oficial"] for oferta in historial_actual}
        añadidas = 0
        for oferta in nuevas_ofertas:
            if oferta["Enlace Oficial"] not in enlaces_vistos:
                oferta["Detectado el"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                historial_actual.append(oferta)
                añadidas += 1
        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
            json.dump(historial_actual, f, indent=4, ensure_ascii=False)
        return historial_actual, añadidas

    # --- INTERFAZ ---
    with st.sidebar:
        st.header("Opciones")
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()
        st.divider()
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()

    st.title("Radar de Licitaciones 🏢")
    tab1, tab2 = st.tabs(["🔍 Buscar Nuevas", "📁 Archivo e Informes"])

    with tab1:
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                ofertas_encontradas = []
                for entrada in feed.entries:
                    resumen_raw = entrada.summary if 'summary' in entrada else ""
                    texto_completo = normalizar_texto(entrada.title + " " + resumen_raw)
                    coincidencias = sorted(list(set([kw.upper() for kw in KEYWORDS if normalizar_texto(kw) in texto_completo])))
                    
                    if coincidencias:
                        organismo = "No detectado"
                        match_org = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", resumen_raw, re.I | re.S)
                        if match_org: organismo = match_org.group(1).strip()
                        elif entrada.get('author'): organismo = entrada.author

                        try: fecha_pub = datetime(*entrada.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: fecha_pub = datetime.now().strftime("%d/%m/%Y")

                        ofertas_encontradas.append({
                            "Publicado": fecha_pub, 
                            "Organismo": organismo,
                            "Título": entrada.title,
                            "Presupuesto": extraer_presupuesto(resumen_raw),
                            "Palabras Detectadas": ", ".join(coincidencias), 
                            "Enlace Oficial": entrada.link
                        })

            historial, nuevas = guardar_en_historial(ofertas_encontradas)
            if nuevas > 0:
                st.success(f"¡Detectadas {nuevas} nuevas oportunidades!")
                df_nuevas = pd.DataFrame(historial[-nuevas:])
                columnas = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]
                st.dataframe(df_nuevas[columnas], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else:
                st.info("No hay novedades interesantes.")

    with tab2:
        historial = cargar_y_limpiar_historial()
        if historial:
            df_historial = pd.DataFrame(list(reversed(historial)))
            columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]
            
            # Buscador en historial
            busqueda = st.text_input("Filtrar historial por nombre o título:")
            if busqueda:
                df_historial = df_historial[df_historial.apply(lambda row: busqueda.lower() in row.astype(str).str.lower().str.cat(), axis=1)]

            st.dataframe(df_historial[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            # --- BOTÓN DE EXCEL ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_historial[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
            
            st.download_button(
                label="📥 Descargar este listado en Excel",
                data=buffer.getvalue(),
                file_name=f"informe_licitaciones_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Historial vacío.")
