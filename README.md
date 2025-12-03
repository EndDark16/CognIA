# CognIA - Backend
Backend de la tesis "Aplicativo web con Random Forest para la alerta temprana de cinco trastornos psicologicos en ninos de 6 a 11 anos". Expone una API REST que procesa datos clinicos/psicologicos estructurados, aplica un modelo de Random Forest y devuelve alertas de riesgo. Solo trabaja con datos simulados o anonimizados y funciona como apoyo temprano, no como diagnostico clinico definitivo.

## Contexto academico y objetivo del proyecto
Trabajo de grado de Ingenieria de Sistemas y Computacion en la Universidad de Cundinamarca, extension Facatativa, dentro del grupo de investigacion GISTFA. Atiende la necesidad de apoyar la deteccion temprana de trastornos frecuentes en la infancia (conducta, TDAH, eliminacion, ansiedad y depresion) donde la falta de herramientas objetivas y la deteccion tardia impactan el bienestar infantil. El backend recibe datos estructurados, ejecuta el modelo de Random Forest y expone resultados via API para integrarse con clientes web.

## Arquitectura general del backend
- Framework: Flask con Blueprints, CORS y configuraciones por entorno.
- Capas: rutas/controladores (api/routes), esquemas de validacion (api/schemas), servicios de dominio (api/services), utilidades y carga de modelos (core/models), configuracion (config).
- Modelo de ML: archivos .pkl en models/ cargados con core/models/predictor.py (ej. models/adhd_model.pkl).
- Configuracion: clases DevelopmentConfig, ProductionConfig y TestingConfig en config/settings.py; variables .env para MONGO_URI, MODEL_PATH, SECRET_KEY.

Flujo de peticion:
```
HTTP POST /api/predict
 -> Blueprint predict (api/routes/predict.py)
 -> Validacion con Marshmallow (api/schemas/predict_schema.py)
 -> Servicio predict_all_probabilities (api/services/model_service.py)
 -> Carga de modelo Random Forest desde models/ (core/models/predictor.py)
 -> Respuesta JSON con probabilidades
```

## Tecnologias y dependencias principales
- Lenguaje: Python 3.10+.
- Web: Flask 3.1.1, Flask-CORS 6.0.1.
- ML y datos: scikit-learn 1.7.1, pandas 2.3.1, numpy 2.3.2, seaborn/matplotlib para analisis.
- Validacion: marshmallow 4.0.0.
- Base de datos (planeada): pymongo 4.13.2 con MONGO_URI configurado, aun no consumido en el codigo.
- Configuracion y despliegue: python-dotenv 1.1.1, gunicorn 23.0.0.
- Pruebas: pytest 8.4.1.

## Funcionalidades principales del backend
### Gestion de usuarios y seguridad
- No hay autenticacion ni autorizacion implementadas. El backend habilita CORS y valida datos de entrada con Marshmallow. Se recomienda agregar autenticacion (tokens/JWT) y control de roles antes de exponer en entornos reales.

### Gestion de evaluaciones
- El endpoint disponible procesa una evaluacion simulada via POST /api/predict y retorna probabilidades de riesgo (actualmente TDAH). Campos requeridos: age, sex, conners_inattention_score, conners_hyperactivity, cbcl_attention_score, sleep_problems. No se almacenan datos; se espera uso anonimo/simulado.

### Motor de IA (Random Forest)
- Inferencia: api/services/model_service.py prepara el DataFrame y llama a predict_proba (en core/models/predictor.py), cargando el modelo desde models/adhd_model.pkl.
- Modelo: clasificador Random Forest entrenado con datos simulados (pipeline en scripts/train_model.py). La respuesta actual devuelve la probabilidad para TDAH; otras condiciones se planean.

### Registro, metricas y logging
- Logging basico activado en modo no debug (configuracion de logging en api/app.py).
- Scripts de entrenamiento imprimen classification_report de scikit-learn para evaluar precision/recall/specificidad de forma local.

## Estructura del proyecto
```
cognia_app/
|-- api/
|   |-- app.py              # Fabrica Flask y registro de blueprints
|   |-- routes/             # Endpoints (p.ej. predict)
|   |-- schemas/            # Validacion de entrada (Marshmallow)
|   |-- services/           # Logica de negocio y llamadas al modelo
|-- config/                 # Configuracion por entorno y variables .env
|-- core/
|   |-- models/             # Carga y wrappers del modelo ML
|-- data/                   # Datasets simulados (CSV)
|-- models/                 # Artefactos entrenados (.pkl)
|-- scripts/                # Entrenamiento y analisis (train_model.py)
|-- tests/                  # Pruebas (actualmente plantillas)
|-- run.py                  # Punto de entrada en desarrollo
|-- requirements.txt        # Dependencias del backend y ML
```

## Requisitos previos
- Python 3.10 o superior.
- Sistemas: Linux, macOS o Windows.
- Herramientas: git, pip, entorno virtual (venv o similar).

## Configuracion e instalacion
1) Clonar el repositorio:
   ```
   git clone <URL_DEL_REPO>
   cd cognia_app
   ```
2) Crear y activar entorno virtual:
   - Windows:
     ```
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - Linux/macOS:
     ```
     python -m venv venv
     source venv/bin/activate
     ```
3) Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```
4) Crear archivo .env en la raiz:
   ```
   SECRET_KEY=dev-secret-key
   MONGO_URI=mongodb://localhost:27017/cognia
   MODEL_PATH=models/adhd_model.pkl
   ```

## Ejecucion en desarrollo
1) Activar el entorno virtual.
2) Iniciar la API:
   ```
   python run.py
   ```
   - Host: 0.0.0.0
   - Puerto por defecto: 5000
3) Verificar enviando una peticion a POST http://localhost:5000/api/predict (ver ejemplos abajo).

## Ejecucion en produccion
- Ejemplo con gunicorn (Linux/macOS):
  ```
  gunicorn -w 4 -b 0.0.0.0:8000 run:app
  ```
- Recomendaciones: usar reverse proxy (Nginx), gestionar variables de entorno y certificados TLS, y agregar autenticacion/autorizacion antes de exponer publicamente. En Windows usar un servidor WSGI alternativo o contenedor Docker.

## Entrenamiento y actualizacion del modelo de IA
- Script principal: scripts/train_model.py
  - Dataset esperado: data/adhd_dataset_simulated.csv (simulado/anonimizado).
  - Ejecucion:
    ```
    python scripts/train_model.py
    ```
  - Salida: models/adhd_model.pkl (cargado por el backend para inferencia).
- Para usar un modelo nuevo, coloque el .pkl en models/ y asegure que MODEL_PATH apunte a esa ruta si se modifica el nombre.
- Entrenamiento solo con datos simulados o anonimizados; nunca use informacion identificable de menores.

## Uso de la API
### POST /api/predict
- Descripcion: calcula probabilidades de riesgo (actualmente TDAH) a partir de una evaluacion estructurada.
- Cuerpo JSON requerido:
```json
{
  "age": 10,
  "sex": 1,
  "conners_inattention_score": 12.5,
  "conners_hyperactivity": 8.1,
  "cbcl_attention_score": 14.0,
  "sleep_problems": 0
}
```
- Respuesta exitosa (200):
```json
{
  "predictions": {
    "adhd": 0.42
  }
}
```
- Errores de validacion (400):
```json
{
  "errors": {
    "age": ["Must be greater than or equal to 3."]
  }
}
```
- Otros codigos: 500 en caso de error interno del servidor.

## Consideraciones eticas y limitaciones
- Prototipo academico en entorno simulado; no sustituye evaluacion clinica profesional.
- Genera alertas de riesgo, no diagnosticos definitivos.
- No debe usarse con pacientes reales sin aprobacion etica, validacion clinica y cumplimiento legal.
- Los trastornos abordados (conducta, TDAH, eliminacion, ansiedad, depresion) son sensibles; el proyecto busca alinearse con los ODS 3 (salud) y 4 (educacion) promoviendo uso responsable y proteccion de datos.

## Pruebas
- Ejecutar:
  ```
  pytest
  ```
- Los tests actuales son plantillas; se recomienda ampliarlos para cubrir endpoints, validacion y logica de modelo.

## Trabajo futuro
- Incorporar autenticacion/autorizacion con roles (psicologos, docentes, padres/tutores, administradores).
- Ampliar inferencia a los cinco trastornos objetivo (conducta, TDAH, eliminacion, ansiedad, depresion) y soportar multietiqueta.
- Persistir evaluaciones y retroalimentacion en MongoDB; exponer endpoints de consulta historica.
- Integracion con estandares clinicos (FHIR/HL7) y generacion de reportes interpretables.
- Mejorar monitoreo y logging, incluyendo metricas de uso y rendimiento del modelo.
- Integracion completa con frontend web y futuras apps moviles.

## Creditos
- Andres Felipe Melo Chaguala - Estudiante investigador
- Johan Thomas Cristancho Silva - Estudiante investigador
- Oscar Jobany Gomez Ochoa - Director
- Universidad de Cundinamarca, grupo de investigacion GISTFA
- Uso academico restringido salvo indicacion contraria (sin licencia explicita en el repositorio).
