import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
import numpy as np

class SimuladorGastos:
    def __init__(self, db_file='gastos.db'):
        self.db_file = db_file
        # Usamos check_same_thread=False para evitar problemas con la recarga de Streamlit
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self._inicializar_db()
        self.df = self.cargar_datos()

    def _inicializar_db(self):
        """Crea la tabla en SQLite si no existe."""
        query = """
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT,
            Tipo TEXT,
            Categoria TEXT,
            Monto REAL,
            Descripcion TEXT
        )
        """
        cursor = self.conn.cursor()
        cursor.execute(query)
        self.conn.commit()

    def cargar_datos(self):
        """Carga el historial completo desde SQLite."""
        query = "SELECT id, Fecha, Tipo, Categoria, Monto, Descripcion FROM transacciones ORDER BY Fecha ASC"
        df = pd.read_sql(query, self.conn)
        
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            df.set_index('id', inplace=True)
            return df
        else:
            return self._crear_df_vacio()

    def _crear_df_vacio(self):
        df = pd.DataFrame(columns=['id', 'Fecha', 'Tipo', 'Categoria', 'Monto', 'Descripcion'])
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        df.set_index('id', inplace=True)
        return df

    def agregar_registro(self, tipo, categoria, monto, descripcion, fecha=None):
        """Inserta un nuevo ingreso o gasto directamente a SQLite."""
        if fecha is None or fecha.strip() == "":
            fecha = datetime.now().strftime("%Y-%m-%d")
        
        try:
            query = "INSERT INTO transacciones (Fecha, Tipo, Categoria, Monto, Descripcion) VALUES (?, ?, ?, ?, ?)"
            cursor = self.conn.cursor()
            cursor.execute(query, (fecha, tipo.capitalize(), categoria.capitalize(), float(monto), descripcion))
            self.conn.commit()
            
            # Recargar memoria
            self.df = self.cargar_datos()
        except Exception as e:
            print(f"Error al agregar registro en BD: {e}")

    def actualizar_registro(self, id_registro, columna, nuevo_valor):
        """Actualiza un campo específico de un registro por su ID."""
        try:
            if columna == 'Fecha' and hasattr(nuevo_valor, 'strftime'):
                nuevo_valor = nuevo_valor.strftime('%Y-%m-%d')
            elif columna == 'Fecha' and isinstance(nuevo_valor, pd.Timestamp):
                nuevo_valor = nuevo_valor.strftime('%Y-%m-%d')
                
            query = f"UPDATE transacciones SET {columna} = ? WHERE id = ?"
            cursor = self.conn.cursor()
            cursor.execute(query, (nuevo_valor, id_registro))
            self.conn.commit()
        except Exception as e:
            print(f"Error al actualizar registro {id_registro}: {e}")

    def eliminar_registros(self, lista_ids):
        """Elimina múltiples registros por su ID."""
        if not lista_ids:
            return
            
        try:
            placeholders = ','.join(['?'] * len(lista_ids))
            query = f"DELETE FROM transacciones WHERE id IN ({placeholders})"
            cursor = self.conn.cursor()
            cursor.execute(query, tuple(lista_ids))
            self.conn.commit()
        except Exception as e:
            print(f"Error al eliminar registros: {e}")

    def importar_datos(self, df_externo):
        """Inserta registros masivos desde un DataFrame externo hacia SQLite, ignorando los duplicados."""
        # Estandarizamos el dataframe
        df_nuevo = df_externo.copy()
        
        if 'Fecha' in df_nuevo.columns:
            df_nuevo['Fecha'] = pd.to_datetime(df_nuevo['Fecha']).dt.strftime('%Y-%m-%d')
        if 'Tipo' in df_nuevo.columns:
            df_nuevo['Tipo'] = df_nuevo['Tipo'].astype(str).str.capitalize()
        if 'Categoria' in df_nuevo.columns:
            df_nuevo['Categoria'] = df_nuevo['Categoria'].astype(str).str.capitalize()
            
        # Rellenar columnas faltantes requeridas por la DB
        columnas_requeridas = ['Fecha', 'Tipo', 'Categoria', 'Monto', 'Descripcion']
        for col in columnas_requeridas:
            if col not in df_nuevo.columns:
                if col in ['Monto']:
                    df_nuevo[col] = 0.0
                else:
                    df_nuevo[col] = ''
        
        df_final = df_nuevo[columnas_requeridas]
        
        # Eliminar duplicados internos dentro del mismo CSV
        df_final = df_final.drop_duplicates()
        
        # Cargar datos actuales para comparar y evitar duplicados en DB
        df_actual = self.cargar_datos()
        
        if not df_actual.empty:
            df_actual_comp = df_actual.copy()
            df_actual_comp['Fecha'] = df_actual_comp['Fecha'].dt.strftime('%Y-%m-%d')
            
            # Hacemos un cruce (merge) comparando TODAS las columnas. 
            # Si cambia la descripcion o el monto por un centavo, se considera un registro diferente.
            df_merged = pd.merge(df_final, df_actual_comp, on=columnas_requeridas, how='left', indicator=True)
            
            # Nos quedamos SOLAMENTE con los que no tuvieron coincidencia en la DB ('left_only')
            df_final = df_merged[df_merged['_merge'] == 'left_only'][columnas_requeridas]
        
        nuevos_registros = len(df_final)
        
        # Insertar solo si hay registros nuevos
        if nuevos_registros > 0:
            df_final.to_sql('transacciones', self.conn, if_exists='append', index=False)
            self.conn.commit()
            # Recargar memoria
            self.df = self.cargar_datos()
            
        return nuevos_registros

    def balance_mensual(self):
        """Muestra el balance agrupado por mes."""
        if self.df.empty:
            return None

        df_mes = self.df.copy()
        df_mes['Mes'] = df_mes['Fecha'].dt.to_period('M')
        
        resumen = df_mes.groupby(['Mes', 'Tipo'])['Monto'].sum().unstack().fillna(0)
        
        if 'Ingreso' not in resumen.columns:
            resumen['Ingreso'] = 0
        if 'Gasto' not in resumen.columns:
            resumen['Gasto'] = 0
            
        resumen['Balance'] = resumen['Ingreso'] - resumen['Gasto']
        return resumen

    def graficar_gastos_categoria(self):
        """Retorna la figura de distribución de gastos por categoría."""
        gastos = self.df[self.df['Tipo'] == 'Gasto']
        if gastos.empty:
            return None

        gastos_cat = gastos.groupby('Categoria')['Monto'].sum()
        
        fig = plt.figure(figsize=(10, 6))
        gastos_cat.plot(kind='pie', autopct='%1.1f%%', startangle=90, cmap='Set3', shadow=True)
        plt.title('Distribución de Gastos por Categoría', fontsize=14, fontweight='bold')
        plt.ylabel('')
        plt.tight_layout()
        return fig

    def graficar_tendencia(self):
        """Retorna la figura de tendencia histórica."""
        if self.df.empty:
            return None

        df_mes = self.df.copy()
        df_mes['Mes'] = df_mes['Fecha'].dt.to_period('M').astype(str)
        resumen = df_mes.groupby(['Mes', 'Tipo'])['Monto'].sum().unstack().fillna(0)
        
        if 'Ingreso' not in resumen.columns: resumen['Ingreso'] = 0
        if 'Gasto' not in resumen.columns: resumen['Gasto'] = 0

        fig = plt.figure(figsize=(12, 6))
        plt.plot(resumen.index, resumen['Ingreso'], marker='o', label='Ingresos', color='#2ca02c', linewidth=2, markersize=8)
        plt.plot(resumen.index, resumen['Gasto'], marker='s', label='Gastos', color='#d62728', linewidth=2, markersize=8)
        
        plt.title('Tendencia Histórica de Ingresos y Gastos', fontsize=14, fontweight='bold')
        plt.xlabel('Mes', fontsize=12)
        plt.ylabel('Monto (S/.)', fontsize=12)
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig

    def prediccion_simple(self):
        """Retorna (promedio_reciente, prediccion_regresion)."""
        gastos = self.df[self.df['Tipo'] == 'Gasto'].copy()
        if gastos.empty:
            return None, None

        gastos['Mes'] = gastos['Fecha'].dt.to_period('M')
        gastos_mensuales = gastos.groupby('Mes')['Monto'].sum()

        if len(gastos_mensuales) < 2:
            return None, None

        promedio = gastos_mensuales.tail(3).mean()
        
        x = np.arange(len(gastos_mensuales))
        y = gastos_mensuales.values
        z = np.polyfit(x, y, 1) 
        p = np.poly1d(z)
        prediccion_regresion = p(len(gastos_mensuales))

        return promedio, max(0, prediccion_regresion)
