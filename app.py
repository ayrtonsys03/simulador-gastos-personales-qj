import streamlit as st
import pandas as pd
from simulador_gastos import SimuladorGastos
from fpdf import FPDF
import tempfile
import os
import json

st.set_page_config(page_title="Simulador de Gastos", page_icon="", layout="wide")

# Inicializamos el simulador. Usamos cache_resource para mantener la instancia.
@st.cache_resource
def get_simulador():
    return SimuladorGastos('gastos.db')

sim = get_simulador()


st.title("Simulador de Gastos Personales")

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("Añadir Transacción")
    
    # Se saca de "st.form" para que cambiarlo actualice la página de inmediato
    tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
    
    with st.form("form_transaccion", clear_on_submit=True):
        monto = st.number_input("Monto (S/.)", min_value=1.00, format="%.2f")
        
        # Cargar categorías predefinidas desde JSON
        try:
            with open('categorias.json', 'r', encoding='utf-8') as f:
                cats = json.load(f)
        except Exception:
            cats = {"Ingreso": ["Salario"], "Gasto": ["Comida", "Transporte"]}
            
        opciones_cat = cats.get(tipo, []) + ["Otra (Especificar)"]
        categoria_sel = st.selectbox("Categoría", opciones_cat)
        
        # Campo opcional por si quiere agregar una categoría nueva que no está en la lista
        categoria_custom = st.text_input("Especificar nueva categoría (solo si elegiste 'Otra')")
        
        descripcion = st.text_input("Descripción breve")
        fecha = st.date_input("Fecha")
        
        submit = st.form_submit_button("Guardar Registro")
        
        if submit:
            if categoria_sel == "Otra (Especificar)":
                # Agrupamos para no ensuciar el gráfico
                categoria_final = "Otros Ingresos" if tipo == "Ingreso" else "Otros Gastos"
                
                # Rescatamos lo que escribió y lo sumamos a la descripción
                detalle = categoria_custom.strip()
                if detalle:
                    descripcion = f"[{detalle}] {descripcion}".strip()
            else:
                categoria_final = categoria_sel
            
            if categoria_final and monto > 0:
                sim.agregar_registro(tipo, categoria_final, monto, descripcion, fecha.strftime("%Y-%m-%d"))
                st.success(f"¡{tipo} de S/.{monto} guardado exitosamente!")
                # Recargar dataframe después de agregar
                sim.df = sim.cargar_datos()
            else:
                st.error("Por favor, selecciona o ingresa una categoría válida y un monto mayor a 0.")
                
    st.divider()
    st.header("Importar Datos Externos")
    archivo_subido = st.file_uploader("Sube tu archivo CSV o Excel", type=['csv', 'xlsx', 'xls'])
    if archivo_subido is not None:
        if st.button("Procesar e Importar a Base de Datos"):
            try:
                if archivo_subido.name.endswith('.csv'):
                    df_ext = pd.read_csv(archivo_subido)
                else:
                    df_ext = pd.read_excel(archivo_subido)
                nuevos = sim.importar_datos(df_ext)
                if nuevos > 0:
                    st.success(f"¡Se analizaron {len(df_ext)} filas y se importaron {nuevos} registros nuevos a la base de datos!")
                else:
                    st.info(f"Se analizaron {len(df_ext)} filas pero todas ya existían en la base de datos (0 duplicados insertados).")
            except Exception as e:
                st.error(f"Hubo un error importando el archivo: {e}")

# --- PANEL PRINCIPAL (TABS) ---
tab1, tab2, tab3, tab4 = st.tabs(["📋 Balance y Registros", "📊 Gráficos", "🔮 Predicciones", "📥 Exportar PDF"])

with tab1:
    st.subheader("Balance Mensual Consolidado")
    resumen = sim.balance_mensual()
    if resumen is not None and not resumen.empty:
        # Formatear números para mejor visualización
        st.dataframe(resumen.style.format("S/.{:,.2f}"), use_container_width=True)
        
        # Botón para exportar Balance
        csv_resumen = resumen.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Descargar Balance Mensual (CSV)",
            data=csv_resumen,
            file_name='balance_mensual.csv',
            mime='text/csv',
        )
        
        st.divider()
        st.subheader("Historial de Registros (Buscador y Editor)")
        
        # Buscador en tiempo real
        busqueda = st.text_input("🔍 Buscar transacción (por categoría, descripción, fecha o monto)", "")
        
        # Reseteamos el index para manejar la columna 'id' como columna normal
        df_mostrar = sim.df.copy().reset_index()
        
        if busqueda:
            mask = df_mostrar.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)
            df_mostrar = df_mostrar[mask]
        
        # Resetear el índice numérico para que siempre sea 0, 1, 2...
        # Esto es CRÍTICO: si no, al filtrar, los índices quedan como 5, 12, 23...
        # y data_editor reporta posiciones 0, 1, 2... que no coinciden con .loc[]
        df_mostrar = df_mostrar.reset_index(drop=True)
        
        # Callback: cuando el usuario edita la tabla, Streamlit llama a esta función
        # ANTES de re-ejecutar el script, así los cambios se guardan en session_state
        def _guardar_cambios_editor():
            import copy
            estado = st.session_state.get("editor_transacciones", {})
            st.session_state["_cambios_pendientes"] = copy.deepcopy(estado)
        
        # Mostrar mensaje de éxito si venimos de una recarga post-guardado
        if "_mensaje_exito" in st.session_state:
            st.success(st.session_state["_mensaje_exito"])
            del st.session_state["_mensaje_exito"]
            
        # Tabla Interactiva
        st.data_editor(
            df_mostrar,
            use_container_width=True,
            num_rows="dynamic",
            key="editor_transacciones",
            on_change=_guardar_cambios_editor,
            column_config={
                "id": None,  # Ocultar el ID interno de la base de datos
                "Fecha": st.column_config.DateColumn("Fecha", required=True),
                "Monto": st.column_config.NumberColumn("Monto (S/.)", min_value=0.01, format="%.2f", required=True),
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Ingreso", "Gasto"], required=True),
                "Categoria": st.column_config.TextColumn("Categoría", required=True),
                "Descripcion": st.column_config.TextColumn("Descripción")
            }
        )
        
        # Interfaz de Confirmación de Cambios
        cambios = st.session_state.get("_cambios_pendientes", {})
        ediciones = cambios.get("edited_rows", {})
        eliminaciones = cambios.get("deleted_rows", [])
        adiciones = cambios.get("added_rows", [])
        
        hay_pendientes = bool(ediciones or eliminaciones or adiciones)
        
        if hay_pendientes:
            st.divider()
            st.markdown("### ⚠️ Cambios Pendientes por Guardar")
            
            # Mostrar advertencias visuales
            if eliminaciones:
                st.error(f"🗑️ **Peligro:** Estás a punto de eliminar {len(eliminaciones)} registro(s) permanentemente.")
            if ediciones:
                st.warning(f"✏️ Vas a modificar {len(ediciones)} registro(s) existente(s).")
            if adiciones:
                st.info(f"➕ Vas a añadir {len(adiciones)} registro(s) nuevo(s).")
                
            confirmar = st.checkbox("✅ Confirmo que he revisado y deseo aplicar estos cambios")
            
            if confirmar:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("💾 Aplicar Cambios Ahora", type="primary", use_container_width=True):
                        hay_cambios = False
                        
                        # 1. Procesar ediciones
                        if ediciones:
                            for pos_str, modificaciones in ediciones.items():
                                pos_idx = int(pos_str)
                                id_real = int(df_mostrar.iloc[pos_idx]['id'])
                                for col, val in modificaciones.items():
                                    sim.actualizar_registro(id_real, col, val)
                            hay_cambios = True
                            
                        # 2. Procesar eliminaciones
                        if eliminaciones:
                            ids_a_borrar = [int(df_mostrar.iloc[i]['id']) for i in eliminaciones]
                            sim.eliminar_registros(ids_a_borrar)
                            hay_cambios = True
                            
                        # 3. Procesar adiciones
                        if adiciones:
                            for fila in adiciones:
                                t = fila.get("Tipo", "Gasto")
                                c = fila.get("Categoria", "Otros")
                                m = fila.get("Monto", 0.01)
                                d = fila.get("Descripcion", "")
                                f = fila.get("Fecha", None)
                                sim.agregar_registro(t, c, m, d, str(f) if f else None)
                            hay_cambios = True
                            
                        if hay_cambios:
                            sim.df = sim.cargar_datos()
                            st.session_state.pop("_cambios_pendientes", None)
                            
                            partes_msg = []
                            if len(ediciones) > 0: partes_msg.append(f"{len(ediciones)} actualizado(s)")
                            if len(eliminaciones) > 0: partes_msg.append(f"{len(eliminaciones)} eliminado(s)")
                            if len(adiciones) > 0: partes_msg.append(f"{len(adiciones)} añadido(s)")
                            st.session_state["_mensaje_exito"] = "💾 Cambios guardados correctamente: " + ", ".join(partes_msg) + "."
                            st.rerun()
                            
                with col2:
                    if st.button("❌ Descartar Cambios", use_container_width=True):
                        st.session_state.pop("_cambios_pendientes", None)
                        st.rerun()
        
        # Botón para exportar Registros
        csv_registros = sim.df.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial de Registros (CSV)",
            data=csv_registros,
            file_name='historial_registros.csv',
            mime='text/csv',
        )
    else:
        st.info("No hay suficientes datos registrados. Agrega un ingreso o gasto en el panel lateral.")

with tab2:
    st.subheader("Análisis Visual")
    col1, col2 = st.columns(2)
    
    fig_cat = sim.graficar_gastos_categoria()
    fig_tendencia = sim.graficar_tendencia()
    
    with col1:
        if fig_cat:
            st.pyplot(fig_cat)
        else:
            st.info("No hay gastos registrados para graficar categorías.")
            
    with col2:
        if fig_tendencia:
            st.pyplot(fig_tendencia)
        else:
            st.info("No hay suficientes datos para graficar tendencias históricas.")

with tab3:
    st.subheader("Predicción de Gastos para el Próximo Mes")
    promedio, regresion = sim.prediccion_simple()
    if promedio is not None:
        col1, col2 = st.columns(2)
        col1.metric("Basado en el promedio reciente (3 meses)", f"S/.{promedio:,.2f}")
        col2.metric("Basado en la tendencia lineal general", f"S/.{regresion:,.2f}")
        
        st.divider()
        st.markdown("#### ¿Cómo se calculan estos resultados?")
        st.info("**Promedio reciente:** Suma tus últimos 3 meses y los divide. Es ideal para conocer tu realidad *inmediata*, asumiendo que tus hábitos recientes se mantendrán estables.")
        st.success("**Tendencia lineal:** Evalúa todo tu historial desde el primer día buscando un patrón. Si llevas meses reduciendo tus gastos, la tendencia bajará agresivamente (premiando tu ahorro). Si gastas más cada mes, la tendencia subirá advirtiendo el peligro.")
        
        st.caption("Nota: Ambas predicciones son puramente matemáticas y asumen que no tendrás gastos de emergencia sorpresa.")
    else:
        st.info("Se necesitan al menos 2 meses de historial de gastos para calcular una predicción.")

with tab4:
    st.subheader("Exportar Reporte de Gastos Personales a PDF")
    st.write("Genera y descarga un reporte consolidado con tu balance mensual y tus gráficos generados.")
    
    def crear_pdf():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16, style='B')
        pdf.cell(200, 10, txt="Reporte de Gastos Personales", ln=True, align='C')
        pdf.ln(10)
        
        # Tabla de Balance
        pdf.set_font("Arial", size=12, style='B')
        if resumen is not None and not resumen.empty:
            pdf.cell(200, 10, txt="Balance Mensual Resumido:", ln=True)
            pdf.set_font("Arial", size=10)
            for index, row in resumen.iterrows():
                texto = f"Mes: {index}  |  Ingreso: S/.{row.get('Ingreso', 0):.2f}  |  Gasto: S/.{row.get('Gasto', 0):.2f}  |  Balance: S/.{row.get('Balance', 0):.2f}"
                pdf.cell(200, 8, txt=texto, ln=True)
        
        pdf.ln(5)
        
        # Predicciones
        if promedio is not None:
            pdf.set_font("Arial", size=12, style='B')
            pdf.cell(200, 10, txt="Prediccion de Gastos (Proximo mes):", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.cell(200, 8, txt=f"Promedio reciente: S/.{promedio:.2f}", ln=True)
            pdf.cell(200, 8, txt=f"Tendencia lineal: S/.{regresion:.2f}", ln=True)
            
        # Graficos
        temp_dir = tempfile.gettempdir()
        cat_path = os.path.join(temp_dir, "grafico_cat.png")
        tendencia_path = os.path.join(temp_dir, "grafico_tendencia.png")
        
        # Guardar imagenes temporalmente y añadirlas al PDF
        if fig_cat:
            fig_cat.savefig(cat_path)
            pdf.add_page()
            pdf.set_font("Arial", size=12, style='B')
            pdf.cell(200, 10, txt="Distribucion de Gastos:", ln=True)
            pdf.image(cat_path, x=10, y=30, w=180)
            
        if fig_tendencia:
            fig_tendencia.savefig(tendencia_path)
            pdf.add_page()
            pdf.set_font("Arial", size=12, style='B')
            pdf.cell(200, 10, txt="Tendencia Historica:", ln=True)
            pdf.image(tendencia_path, x=10, y=30, w=180)

        # Generar PDF en temporal
        pdf_path = os.path.join(temp_dir, "Reporte_Gastos.pdf")
        pdf.output(pdf_path)
        
        with open(pdf_path, "rb") as f:
            bytes_pdf = f.read()
        return bytes_pdf

    # Validamos que haya datos antes de habilitar el botón
    if not sim.df.empty:
        pdf_bytes = crear_pdf()
        st.download_button(
            label="📥 Generar y Descargar Reporte PDF",
            data=pdf_bytes,
            file_name="Reporte_Financiero.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.warning("Agrega datos primero para poder generar un PDF.")
