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
# --- 2. CSS LIMPIO Y TOTALMENTE SEGURO ---
# ==============================================================================
st.markdown(
    """
    <style>
        :root { --coral-red: #FF4B4B; }
        
        [data-testid="stSidebarNav"] { display: none !important; }
        
        [data-testid="stSidebar"] img {
            margin-top: -30px !important;
            margin-bottom: 10px !important;
        }

        .block-container {
            padding-top: 2rem !important; 
        }

        [data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
        }

        .radar-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-top: 10px;
            padding-bottom: 15px;
        }
        
        .radar-title {
            font-size: 2.8rem;
            font-weight: 700;
            color: #31333F;
            margin: 0;
            padding: 0;
            line-height: 1.4; 
        }

        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button {
            background-color: var(--coral-red) !important;
            color: white !important;
            border: none !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
        }
        .stButton button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover {
            background-color: #e34343 !important;
        }
        
        .action-buttons .stButton button {
            font-weight: 600 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- PROMPT MAESTRO PARA GEMINI ---
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

# --- 3. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.write("")
    st.write("")
    st.write("")
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        logo_col1, logo_col2, logo_col3 = st.columns([1, 2, 1])
        with logo_col2:
            if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
            
        st.markdown("<h3 style='text-align: center; color: #31333F; margin-top: 10px; margin-bottom: 30px; font-weight: 600;'>Acceso al Buscador de Licitaciones</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            pwd = st.text_input(
                "Contraseña corporativa:", 
                type="password", 
                label_visibility="collapsed",
                placeholder="Introduce la contraseña corporativa..." 
            )
            enviado = st.form_submit_button("Entrar", use_container_width=True)
            
            if enviado:
                if pwd == st.secrets["PASSWORD_WEB"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: 
                    st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    # --- 4. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    DIAS_RETENCION = 5
    KEYWORDS = ["Confederación", "Hidrográfica", "Canales", "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

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

    def extraer_fecha_cierre(e, texto):
        try:
            raw = str(e).lower()
            m1 = re.search(r"['\"]?(?:cbc_)?enddate['\"]?\s*:\s*['\"](\d{4}-\d{2}-\d{2})", raw)
            if m1: 
                return datetime.strptime(m1.group(1), "%Y-%m-%d").strftime("%d/%m/%Y")
        except: pass
        if texto:
            try:
                m_html = re.search(r"(?:plazo|presentaci.n|l.mite|hasta).*?(?:>|:|\s)(?:&nbsp;|\s)*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", texto, re.IGNORECASE | re.DOTALL)
                if m_html: 
                    f_enc = m_html.group(1)
                    if "-" in f_enc: return datetime.strptime(f_enc, "%Y-%m-%d").strftime("%d/%m/%Y")
                    return f_enc
                t_limpio = re.sub(r'<[^>]*>', ' ', texto).lower()
                m_txt = re.search(r"(?:plazo|presentaci.n|l.mite|hasta).{0,60}?(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})", t_limpio)
                if m_txt: 
                    f_enc = m_txt.group(1)
                    if "-" in f_enc: return datetime.strptime(f_enc, "%Y-%m-%d").strftime("%d/%m/%Y")
                    return f_enc
            except: pass
        return "No indicada"

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

    # --- 6. BARRA LATERAL ---
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=140)
        
        st.divider()
        
        with st.expander("📡 Radar de Licitaciones", expanded=True):
            opcion_navegacion = st.radio(
                "Menú", 
                ["🔍 Búsqueda Licitaciones", "📁 Archivos e Informes", "📄 Generación de Informes"],
                label_visibility="collapsed"
            )
            
        st.markdown("<div style='height: 50vh;'></div>", unsafe_allow_html=True)
        
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 7. CUERPO PRINCIPAL ---
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
            <div class="radar-title">Radar de Licitaciones</div>
        </div>
        """, unsafe_allow_html=True
    )

    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Fin Plazo", "Palabras Detectadas", "Enlace Oficial"]

    # --- VISTA 1: BÚSQUEDA ---
    if opcion_navegacion == "🔍 Búsqueda Licitaciones":
        st.subheader("Búsqueda en Tiempo Real")
        st.write("Pulsa el botón para escanear las últimas publicaciones de la Plataforma de Contratación del Estado.")
        
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma del Estado y filtrando fechas caducadas...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                hoy = datetime.now().date() 
                
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar(e.title + " " + res)
                    coin = sorted(list(set([k.upper() for k in KEYWORDS if normalizar(k) in txt])))
                    
                    if coin:
                        fecha_cierre_str = extraer_fecha_cierre(e, res)
                        es_valida = True
                        if fecha_cierre_str != "No indicada":
                            try:
                                fecha_cierre_dt = datetime.strptime(fecha_cierre_str, "%d/%m/%Y").date()
                                if fecha_cierre_dt < hoy: es_valida = False 
                            except: pass 
                        
                        if es_valida:
                            org = "No detectado"
                            m = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", res, re.I | re.S)
                            if m: org = m.group(1).strip()
                            elif e.get('author'): org = e.author
                            try: f_pub = datetime(*e.published_parsed[:3]).strftime("%d/%m/%Y")
                            except: f_pub = datetime.now().strftime("%d/%m/%Y")
                            
                            encontradas.append({
                                "Publicado": f_pub, "Organismo": org, "Título": e.title, 
                                "Presupuesto": extraer_presupuesto(res), "Fin Plazo": fecha_cierre_str,
                                "Palabras Detectadas": ", ".join(coin), "Enlace Oficial": e.link
                            })

            historial, nuevas = guardar_en_historial(encontradas)
            if nuevas > 0:
                st.success(f"¡Detectadas {nuevas} nuevas oportunidades VIGENTES!")
                df = pd.DataFrame(historial[-nuevas:])
                for c in columnas_ver:
                    if c not in df.columns: df[c] = "N/A"
                st.dataframe(df[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else: st.info("No hay novedades vigentes en este momento.")

    # --- VISTA 2: ARCHIVOS E INFORMES ---
    elif opcion_navegacion == "📁 Archivos e Informes":
        st.subheader("Base de Datos e Informes")
        hist = cargar_y_limpiar_historial()
        
        if hist:
            df_hist = pd.DataFrame(list(reversed(hist)))
            for c in columnas_ver:
                if c not in df_hist.columns: df_hist[c] = "N/A"
                
            busq = st.text_input("Buscar por Organismo o Título:")
            if busq: df_hist = df_hist[df_hist.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            
            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            
            st.write("---") 
            st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([2, 2, 4]) 
            
            with col1:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
                st.download_button(label="📥 Descargar Excel", data=buffer.getvalue(), file_name="informe_licitaciones.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            with col2:
                if st.button("🗑️ Reset", use_container_width=True):
                    if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else: 
            st.info("El historial está vacío. Ve a la sección 'Búsqueda Licitaciones' para escanear.")

    # --- VISTA 3: GENERACIÓN DE INFORMES (GEMINI IA) ---
    elif opcion_navegacion == "📄 Generación de Informes":
        st.subheader("Analista de Licitaciones por IA")
        st.write("Arrastra aquí los pliegos (Técnico, Administrativo, etc.) descargados del Estado y deja que la IA genere un informe de viabilidad ejecutivo en formato PDF.")
        
        archivos_subidos = st.file_uploader("Cargar Pliegos (Formato PDF)", type=["pdf"], accept_multiple_files=True)
        
        if st.button("Analizar con IA y Generar PDF", type="primary"):
            if not archivos_subidos:
                st.warning("⚠️ Por favor, sube al menos un documento PDF para analizar.")
            else:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("⚠️ Falta la clave GEMINI_API_KEY en los secretos de Streamlit.")
                else:
                    with st.spinner("🧠 Leyendo pliegos y analizando viabilidad... Esto puede tardar 1 o 2 minutos."):
                        try:
                            # 1. Configurar Cliente Gemini
                            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                            documentos_para_ia = []
                            rutas_temporales = []
                            
                            # 2. Guardar temporalmente para que Gemini pueda leerlos
                            for archivo in archivos_subidos:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                    tmp.write(archivo.getvalue())
                                    tmp_path = tmp.name
                                    rutas_temporales.append(tmp_path)
                                
                                # Subir a Gemini
                                doc_ia = client.files.upload(file=tmp_path)
                                documentos_para_ia.append(doc_ia)
                                
                            # 3. Llamada a la IA
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[PROMPT_MAESTRO] + documentos_para_ia
                            )
                            
                            # Limpiar archivos temporales del servidor
                            for ruta in rutas_temporales:
                                os.remove(ruta)
                            
                            # 4. Procesar JSON devuelto
                            texto_limpio = response.text.strip().replace("```json", "").replace("```", "")
                            datos = json.loads(texto_limpio)
                            
                            # 5. Maquetación HTML del PDF
                            html_filas_tabla = ""
                            for fila in datos.get('datos_iniciales', []):
                                html_filas_tabla += f"<tr><td><strong>{fila.get('concepto', '')}</strong></td><td>{fila.get('detalle', '')}</td></tr>\n"
                                
                            html_alcance = "".join([f"<li>{i}</li>" for i in datos.get('alcance', [])])
                            html_pros = "".join([f"<li>{i}</li>" for i in datos.get('pros', [])])
                            html_contras = "".join([f"<li>{i}</li>" for i in datos.get('contras', [])])
                            
                            # Ruta del Logo
                            ruta_logo = "logo.png" if os.path.exists("logo.png") else ""
                            etiqueta_logo = f'<img src="{ruta_logo}" height="25" />' if ruta_logo else ''
                            
                            html_final = f"""
                            <!DOCTYPE html>
                            <html>
                            <head>
                            <meta charset="UTF-8">
                            <style>
                                @page {{
                                    size: A4;
                                    margin-top: 3.5cm; margin-bottom: 2.5cm; margin-left: 1.5cm; margin-right: 1.5cm;
                                    @frame header_frame {{ -pdf-frame-content: header_content; top: 1cm; margin-left: 1.5cm; margin-right: 1.5cm; height: 1.5cm; }}
                                    @frame footer_frame {{ -pdf-frame-content: footer_content; bottom: 1cm; margin-left: 1.5cm; margin-right: 1.5cm; height: 1cm; }}
                                }}
                                body {{ font-family: "Helvetica", Arial, sans-serif; font-size: 12pt; color: #333333; }}
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
                                <ul>{html_alcance}</ul>
                                <div class="seccion">3. ANÁLISIS DE VIABILIDAD</div>
                                <div class="pros">VENTAJAS (PROS):</div>
                                <ul>{html_pros}</ul>
                                <div class="contras">RIESGOS Y PENALIZACIONES (CONTRAS):</div>
                                <ul>{html_contras}</ul>
                                <div class="seccion">4. VALORACIÓN</div>
                                <div class="nota">PUNTUACIÓN: {datos.get('valoracion_puntuacion', '')}</div>
                                <div class="texto-justificado">{datos.get('valoracion_texto', '')}</div>
                            </body>
                            </html>
                            """
                            
                            # 6. Generar PDF en Buffer (sin guardar en disco)
                            pdf_buffer = io.BytesIO()
                            pisa_status = pisa.CreatePDF(html_final, dest=pdf_buffer)
                            
                            if pisa_status.err:
                                st.error("❌ Ocurrió un error al intentar crear el documento PDF.")
                            else:
                                st.success("✅ ¡Análisis completado! Tu informe ejecutivo está listo.")
                                
                                # Botón de descarga
                                st.download_button(
                                    label="📥 Descargar Informe en PDF",
                                    data=pdf_buffer.getvalue(),
                                    file_name=f"Viabilidad_{datos.get('titulo_oferta', 'Anerpro')[:20]}.pdf",
                                    mime="application/pdf",
                                    type="primary"
                                )
                                
                        except Exception as e:
                            st.error(f"❌ Error durante el procesamiento con IA: {e}")
