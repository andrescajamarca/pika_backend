from pathlib import Path
import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_CHATS_DIR = BASE_DIR / "data" / "raw_chats"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_drive_service() -> "Resource":  # type: ignore[name-defined]
    creds: Credentials | None = None
    token_path = BASE_DIR / "token.json"
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                credentials_path = BASE_DIR / "credentials.json"
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            credentials_path = BASE_DIR / "credentials.json"
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with token_path.open("w") as token_file:
            token_file.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    return service


def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """Devuelve todos los archivos de una carpeta de Drive, manejando paginación."""

    query = f"'{folder_id}' in parents and trashed = false"
    files: list[dict] = []
    page_token: str | None = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return files


def download_new_files(service, folder_id: str) -> None:
    RAW_CHATS_DIR.mkdir(parents=True, exist_ok=True)

    existing_files = {p.name for p in RAW_CHATS_DIR.glob("*") if p.is_file()}
    files = list_files_in_folder(service, folder_id)

    for file_info in files:
        name = file_info["name"]
        file_id = file_info["id"]

        if name in existing_files:
            continue

        request = service.files().get_media(fileId=file_id)
        file_path = RAW_CHATS_DIR / name

        from googleapiclient.http import MediaIoBaseDownload
        import io

        fh = io.FileIO(file_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def verify_sync(service, folder_id: str) -> None:
    """Verifica cuántos archivos hay en Drive vs local y muestra un resumen."""

    RAW_CHATS_DIR.mkdir(parents=True, exist_ok=True)

    local_files = {p.name for p in RAW_CHATS_DIR.glob("*") if p.is_file()}
    remote_files = list_files_in_folder(service, folder_id)
    remote_names = {f["name"] for f in remote_files}

    missing_locally = remote_names - local_files
    extra_local = local_files - remote_names

    print("--- Resumen de sincronización de raw_chats ---")
    print(f"Archivos en Drive: {len(remote_names)}")
    print(f"Archivos locales: {len(local_files)}")
    print(f"Faltan por descargar (presentes en Drive, no en local): {len(missing_locally)}")
    print(f"Archivos solo locales (no están en Drive): {len(extra_local)}")

    if missing_locally:
        ejemplos = sorted(missing_locally)[:10]
        print("Ejemplos de archivos faltantes:")
        for name in ejemplos:
            print(f"  - {name}")


def main() -> None:
    folder_id = os.getenv("GDRIVE_RAW_CHATS_FOLDER_ID")
    if not folder_id:
        raise RuntimeError("GDRIVE_RAW_CHATS_FOLDER_ID no está configurado en el entorno")

    service = get_drive_service()
    download_new_files(service, folder_id)
    verify_sync(service, folder_id)


if __name__ == "__main__":
    main()
