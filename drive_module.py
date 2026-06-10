import os
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import io
import pickle

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE = "token.pickle"

PAYWALL_SIGNALS = [
    "sign in", "log in", "login", "subscribe", "purchase",
    "access denied", "checkout", "create account", "institutional access",
    "buy article", "rent article", "get access"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


def get_drive_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


def download_pdf(url):
    """Descarga un PDF con detección de paywall y rotación de User-Agent ante errores 403."""
    for attempt, user_agent in enumerate(USER_AGENTS, 1):
        try:
            print(f"Intento {attempt} — descargando: {url}")
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": user_agent, "Accept": "application/pdf,*/*"},
                allow_redirects=True
            )
            print(f"Status {response.status_code} | Content-Type: {response.headers.get('Content-Type', '?')} | Tamaño: {len(response.content)} bytes")

            if response.status_code == 403:
                print(f"403 Prohibido — probando siguiente User-Agent...")
                continue

            if response.status_code != 200:
                print(f"Error HTTP {response.status_code}")
                return None

            content_type = response.headers.get("Content-Type", "")

            if "pdf" in content_type or response.content[:4] == b"%PDF":
                print("PDF verificado correctamente")
                return response.content

            if "html" in content_type:
                page_text = response.text.lower()
                if any(signal in page_text for signal in PAYWALL_SIGNALS):
                    print("Paywall detectado — no se puede descargar el PDF")
                    return None
                print("Respuesta HTML sin paywall — no es un PDF descargable directamente")
                return None

            print(f"Formato no reconocido: {content_type}")
            return None

        except Exception as e:
            print(f"Excepción intento {attempt}: {e}")
            if attempt == len(USER_AGENTS):
                return None

    return None


def upload_to_drive(article):
    try:
        folder_id = os.getenv("DRIVE_FOLDER_ID")

        if not folder_id:
            print("ERROR: No se encontró DRIVE_FOLDER_ID en el archivo .env")
            return False

        service = get_drive_service()

        title = article.get("title", "articulo")
        url = article.get("url", "")
        has_pdf = article.get("has_pdf", False)
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:80]

        print(f"Procesando artículo: {title[:50]}")
        print(f"URL: {url}")
        print(f"PDF en acceso abierto localizado: {has_pdf}")

        # Intentar descargar el PDF si alguna fuente encontró una URL
        pdf_content = None
        if has_pdf and url:
            pdf_content = download_pdf(url)

        # Decidir qué subir
        if pdf_content:
            file_stream = io.BytesIO(pdf_content)
            media = MediaIoBaseUpload(file_stream, mimetype="application/pdf")
            file_name = f"{safe_title}.pdf"
            print(f"Subiendo como PDF: {file_name}")
        else:
            # Guardar info del artículo como texto
            if has_pdf and url:
                print("PDF localizado pero no descargable. Guardando info con enlace.")
            else:
                print("No hay PDF disponible. Guardando info del artículo.")

            info = (
                f"Título: {title}\n"
                f"Autores: {article.get('authors', '')}\n"
                f"Año: {article.get('year', '')}\n"
                f"Fuente: {article.get('source', '')}\n"
                f"URL del PDF: {url}\n"
                f"DOI: {article.get('doi', '')}\n\n"
                f"Resumen:\n{article.get('abstract', '')}\n\n"
                f"--- Accede al PDF manualmente en la URL de arriba ---"
            )
            file_stream = io.BytesIO(info.encode("utf-8"))
            media = MediaIoBaseUpload(file_stream, mimetype="text/plain")
            file_name = f"{safe_title}.txt"
            print(f"Subiendo como texto: {file_name}")

        file_metadata = {
            "name": file_name,
            "parents": [folder_id]
        }

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        print(f"Subido correctamente a Drive. ID: {uploaded.get('id')}")
        return True

    except Exception as e:
        print(f"Error subiendo a Drive: {e}")
        return False