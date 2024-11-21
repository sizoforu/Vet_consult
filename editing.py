import streamlit as st
import sqlite3
import pandas as pd

def obtener_conexion_db():
    """Conectar a la base de datos SQLite."""
    conn = sqlite3.connect('vet_consult.db')
    return conn

def obtener_consultas():
    """Obtener todas las consultas de la base de datos."""
    conn = obtener_conexion_db()
    df = pd.read_sql_query("SELECT * FROM consultations", conn)
    conn.close()
    return df

def eliminar_consulta(id_consulta):
    """Eliminar una consulta de la base de datos."""
    conn = obtener_conexion_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM consultations WHERE id = ?", (id_consulta,))
    conn.commit()
    conn.close()

def actualizar_consulta(id_consulta, datos):
    """Actualizar una consulta en la base de datos."""
    conn = obtener_conexion_db()
    cursor = conn.cursor()
    
    # Obtener los nombres de las columnas
    cursor.execute("PRAGMA table_info(consultations)")
    columnas = [col[1] for col in cursor.fetchall()]
    columnas.remove('id')  # Removemos el ID ya que es la condición WHERE
    
    # Construir la consulta SQL dinámicamente
    set_clause = ", ".join([f"{col} = ?" for col in columnas])
    query = f"UPDATE consultations SET {set_clause} WHERE id = ?"
    
    # Crear la tupla de valores en el mismo orden que las columnas
    valores = tuple(datos[col] for col in columnas) + (id_consulta,)
    
    cursor.execute(query, valores)
    conn.commit()
    conn.close()

def main():
    st.title("🐾 Sistema de Gestión de Consultas Veterinarias")
    
    tabs = ["📋 Ver Registros", "✏️ Editar Registro", "🗑️ Eliminar Registro"]
    pestaña_seleccionada = st.tabs(tabs)
    
    # Pestaña Ver Registros
    with pestaña_seleccionada[0]:
        st.subheader("Registros de Consultas 📊")
        df = obtener_consultas()
        
        if not df.empty:
            termino_busqueda = st.text_input("🔍 Buscar Registros", 
                placeholder="buscar mascota nombre, nombre proprietario o sintomas")
            
            if termino_busqueda:
                df_filtrada = df[df.apply(lambda row: row.astype(str).str.contains(
                    termino_busqueda, case=False).any(), axis=1)]
                st.dataframe(df_filtrada, use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)
    
    # Pestaña Editar Registro
    with pestaña_seleccionada[1]:
        st.subheader("Editar Registro de Consulta ✏️")
        df = obtener_consultas()
        
        if not df.empty:
            id_consulta = st.selectbox(
                "Seleccionar Registro a Editar", 
                df['id'].tolist(),
                format_func=lambda x: f"Registro #{x}"
            )
            
            if id_consulta:
                datos_consulta = df[df['id'] == id_consulta].iloc[0]
                
                with st.form("formulario_editar_consulta"):
                    # Crear campos de formulario dinámicamente basados en las columnas existentes
                    nuevos_datos = {}
                    columnas = [col for col in df.columns if col != 'id']
                    
                    col1, col2 = st.columns(2)
                    mitad = len(columnas) // 2
                    
                    with col1:
                        for col in columnas[:mitad]:
                            if 'date' in col.lower():
                                nuevos_datos[col] = st.date_input(
                                    f"{col} 🗓️",
                                    pd.to_datetime(datos_consulta[col])
                                )
                            elif 'age' in col.lower():
                                nuevos_datos[col] = st.number_input(
                                    f"{col} 🎂",
                                    value=float(datos_consulta[col]),
                                    min_value=0.0,
                                    step=0.1
                                )
                            else:
                                nuevos_datos[col] = st.text_input(
                                    f"{col}",
                                    value=str(datos_consulta[col])
                                )
                    
                    with col2:
                        for col in columnas[mitad:]:
                            if 'symptoms' in col.lower() or 'diagnosis' in col.lower() or 'recommendations' in col.lower():
                                nuevos_datos[col] = st.text_area(
                                    f"{col}",
                                    value=str(datos_consulta[col])
                                )
                            else:
                                nuevos_datos[col] = st.text_input(
                                    f"{col}",
                                    value=str(datos_consulta[col])
                                )
                    
                    boton_enviar = st.form_submit_button("Actualizar Registro ✅")
                    
                    if boton_enviar:
                        # Convertir fecha si existe
                        for key in nuevos_datos:
                            if 'date' in key.lower() and isinstance(nuevos_datos[key], pd._libs.tslibs.timestamps.Timestamp):
                                nuevos_datos[key] = nuevos_datos[key].strftime('%Y-%m-%d')
                        
                        actualizar_consulta(id_consulta, nuevos_datos)
                        st.success("¡Registro actualizado correctamente! 🎉")
                        st.rerun()
        else:
            st.info("No hay registros disponibles para editar.")
    
    # Pestaña Eliminar Registro
    with pestaña_seleccionada[2]:
        st.subheader("Eliminar Registro de Consulta 🗑️")
        df = obtener_consultas()
        
        if not df.empty:
            id_consulta = st.selectbox(
                "Seleccionar Registro a Eliminar", 
                df['id'].tolist(),
                format_func=lambda x: f"Registro #{x}"
            )
            
            if id_consulta:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Eliminar Registro ❌"):
                        eliminar_consulta(id_consulta)
                        st.success("¡Registro eliminado correctamente! 🗑️")
                        st.rerun()
        else:
            st.info("No hay registros disponibles para eliminar.")

if __name__ == '__main__':
    main()