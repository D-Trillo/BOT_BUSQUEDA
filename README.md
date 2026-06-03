# BOT-BUSQUEDA — Bot de Investigación Científica

Bot de Telegram que busca artículos científicos en múltiples bases de datos y los guarda automáticamente en Google Drive.

## Funcionalidades

- Búsqueda simultánea en **PubMed**, **Scopus** y **ScienceDirect**
- Filtrado por relevancia: solo devuelve artículos que contienen las palabras clave en título o abstract
- Descarga automática de PDFs en acceso abierto via **Unpaywall**
- Guardado de artículos seleccionados en **Google Drive** (PDF o ficha en texto)
- Deduplicación de resultados entre fuentes
- Interfaz conversacional con botones inline en Telegram

## Uso

Escribe al bot en Telegram con el siguiente formato:

```
palabras clave | año inicio | año fin
```

**Ejemplo:**
```
machine learning, cancer | 2021 | 2024
```

El bot presentará los artículos uno a uno. Para cada uno puedes:
- ✅ **Me interesa** → descarga el PDF (si está disponible) y lo sube a Drive
- ❌ **Descartar** → pasa al siguiente artículo

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/BOT-BUSQUEDA.git
cd BOT-BUSQUEDA
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install python-telegram-bot biopython requests python-dotenv google-api-python-client google-auth-oauthlib
```

### 4. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
TELEGRAM_TOKEN=tu_token_de_telegram
PUBMED_API_KEY=tu_api_key_de_pubmed
ELSEVIER_API_KEY=tu_api_key_de_elsevier
DRIVE_FOLDER_ID=id_de_tu_carpeta_en_drive
YOUR_EMAIL=tu_email@gmail.com
```

### 5. Configurar Google Drive

Coloca tu archivo de credenciales OAuth de Google como `oauth_credentials.json` en la raíz del proyecto. La primera ejecución abrirá el navegador para autorizarte.

### 6. Ejecutar

```bash
python bot.py
```

## Obtener las API Keys

| Servicio | Dónde obtenerla |
|---|---|
| Telegram | [@BotFather](https://t.me/BotFather) en Telegram |
| PubMed | [NCBI API Key](https://www.ncbi.nlm.nih.gov/account/) |
| Elsevier (Scopus + ScienceDirect) | [Elsevier Developer Portal](https://dev.elsevier.com/) |
| Google Drive | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → OAuth 2.0 |

## Estructura del proyecto

```
BOT-BUSQUEDA/
├── bot.py               # Punto de entrada, interfaz Telegram
├── search_module.py     # Búsqueda en PubMed, Scopus y ScienceDirect
├── drive_module.py      # Descarga de PDFs y subida a Google Drive
├── .env                 # Variables de entorno (no incluido en el repo)
└── oauth_credentials.json  # Credenciales OAuth Google (no incluido en el repo)
```

## Licencia

MIT — ver [LICENSE](LICENSE)
