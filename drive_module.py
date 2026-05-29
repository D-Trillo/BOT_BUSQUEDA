import os
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import io
import pickle

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
OAUTH_CREDENTIALS_FILE = "oauth_credentials.json"
TOKEN_FILE = "token.pickle"


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
    """Intenta descargar un PDF desde una URL y devuelve el contenido en bytes"""
    try:
        print(f"Intentando descargar PDF desde: {url}")
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/pdf,*/*"
            },
            allow_redirects=True
        )
        print(f"Respuesta descarga: Status {response.status_code}, Content-Type: {response.headers.get('Content-Type', 'desconocido')}, Tamaño: {len(response.content)} bytes")

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            # Verificar que es realmente un PDF
            if "pdf" in content_type or response.content[:4] == b"%PDF":
                print("PDF verificado correctamente")
                return response.content
            else:
                print(f"El archivo descargado no es un PDF. Content-Type: {content_type}")
                return None
        else:
            print(f"Error al descargar: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"Excepción al descargar PDF: {e}")
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
        print(f"Tiene PDF según Unpaywall: {has_pdf}")

        # Intentar descargar el PDF si Unpaywall dijo que existe
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
                print("Unpaywall encontró PDF pero no se pudo descargar. Guardando info con enlace.")
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