# Simulador de Gastos Personales

Una aplicación web interactiva construida en **Python** y **Streamlit** diseñada para ayudarte a simular, registrar y analizar tus finanzas personales (ingresos y gastos) de manera sencilla.

## Características Principales
- **Registro Rápido:** Agrega ingresos o gastos en segundos desde el panel lateral.
- **Base de Datos Local:** Utiliza `SQLite3` de forma nativa para almacenar tu historial sin necesidad de instalaciones pesadas.
- **Importación Inteligente:** Sube tus propios archivos Excel o CSV. El sistema detecta y evita duplicados automáticamente.
- **Buscador y Editor Interactivo:** Busca cualquier transacción instantáneamente y edítala o elimínala en tiempo real directamente desde una tabla dinámica, con sistema de validación anti-errores.
- **Categorías Dinámicas:** Personaliza tus categorías fácilmente a través de un archivo externo (`categorias.json`).
- **Análisis Visual:** Gráficos de distribución de categorías y tendencias generados con `Matplotlib`.
- **Predicciones Matemáticas:** Algoritmo simple de predicción de gastos basado en tu historial reciente y regresión lineal.
- **Exportación a PDF y CSV:** Extrae tus datos a CSV o genera un elegante reporte PDF con `fpdf2` que incluye todos tus gráficos y balances consolidados.

## Requisitos e Instalación

1. Clona el repositorio:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd analisis-gasto-personal
   ```

2. Crea y activa tu entorno virtual (recomendado):
   ```bash
   python -m venv env
   # En Windows:
   env\Scripts\activate
   # En Mac/Linux:
   source env/bin/activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Para ejecutar la aplicación localmente, simplemente inicia el servidor de Streamlit:

```bash
streamlit run app.py
```
Se abrirá automáticamente una pestaña en tu navegador en `http://localhost:8501`. 

## Estructura del Proyecto
- `app.py`: Contiene la lógica de la interfaz web en Streamlit y la generación del PDF.
- `simulador_gastos.py`: Contiene la clase principal que gestiona la base de datos SQLite y los cálculos con Pandas/NumPy.
- `categorias.json`: Archivo de configuración donde puedes añadir o quitar las categorías predefinidas que aparecen en los menús desplegables.
- `requirements.txt`: Lista de librerías de Python requeridas.

---

**Notas:**
1. *El PDF que se exporta es simple y no es muy estético, se recomienda editarlo y mejorarlo a gusto personal. Ya que está hecho con fpdf2 y no es muy personalizable.*
2. *Este proyecto fue hecho con la ayuda de [Gemini 3 Pro](https://gemini.google.com/) para solucionar un pequeño problema que tenía con el proyecto, sobre la forma de guardar los cambios en la tabla interactiva y el buscador de transacciones, algo simple pero con esta IA pude ahorrarme algo de tiempo. Además de pedirle que agregue comentarios a las funciones para que cualquiera pueda entender mejor el código.*
