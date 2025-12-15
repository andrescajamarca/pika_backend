from __future__ import annotations

from pathlib import Path

import json
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_CHATS_DIR = BASE_DIR / "data" / "raw_chats"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


# Esquema fijo de columnas según los CSV exportados de WhatsApp Business
RAW_COLS = [
    "chat_id",
    "sent_at",
    "read_at",
    "direction",
    "col4",
    "contact",
    "status",
    "col8",
    "text",
    "media_filename",
    "media_type",
    "media_metadata",
]


def es_csv_valido(path: Path) -> bool:
    """Determina si un archivo CSV debe ser procesado (paso 2 del plan)."""

    if path.suffix.lower() != ".csv":
        return False

    name = path.name

    # Excluir archivo de notificaciones del propio WhatsApp Business
    if "WhatsApp Business.csv" in name:
        return False

    # Excluir CSV vacíos
    try:
        if path.stat().st_size == 0:
            return False
    except OSError:
        return False

    return True


def leer_chat_csv(path: Path) -> pd.DataFrame:
    """Lee un CSV de WhatsApp con el esquema fijo de 12 columnas (paso 3)."""

    df = pd.read_csv(
        path,
        header=None,
        names=RAW_COLS,
        sep=",",
        encoding="utf-8-sig",
        engine="python",  # maneja mejor textos con saltos de línea
        on_bad_lines="warn",  # ignora/avisa filas corruptas sin romper todo
    )

    df["filename"] = path.name
    df["file_path"] = str(path)
    return df


def limpiar_mensajes(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y tipa los datos básicos de un DataFrame de chat (paso 4)."""

    # Parseo de fechas
    df["sent_at"] = pd.to_datetime(df["sent_at"], errors="coerce")
    df["read_at"] = pd.to_datetime(df["read_at"], errors="coerce")

    # Eliminar filas sin fecha de envío válida
    df = df.dropna(subset=["sent_at"])

    # Eliminar notificaciones del sistema
    df = df[df["direction"] != "Notificación"]

    # Limpiar texto (manteniendo cadena vacía si no hay contenido)
    df["text"] = df["text"].fillna("").astype(str).str.strip()

    # Flag de media
    media_type = df["media_type"].fillna("").astype(str).str.strip()
    df["is_media"] = media_type != ""

    return df


def obtener_client_id(df: pd.DataFrame) -> pd.Series:
    contact = df["contact"].fillna("").astype(str).str.strip()
    chat = df["chat_id"].fillna("").astype(str).str.strip()

    base = contact.where(contact != "", chat)

    def normalizar(raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return ""

        plus = "+" if raw.startswith("+") else ""
        digits = "".join(ch for ch in raw if ch.isdigit())

        if len(digits) >= 8:
            return plus + digits

        return raw

    return base.apply(normalizar)


def asignar_ids_y_roles(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["conversation_id"] = result["filename"].str.replace(".csv", "", regex=False)
    result["client_id"] = obtener_client_id(result)

    result["role"] = pd.NA
    result.loc[result["direction"] == "Entrante", "role"] = "user"
    result.loc[result["direction"] == "Saliente", "role"] = "assistant"

    result = result.sort_values(["conversation_id", "sent_at"]).reset_index(drop=True)
    result["message_index"] = result.groupby("conversation_id").cumcount()

    time_diff = (
        result.groupby("conversation_id")["sent_at"].diff().dt.total_seconds()
        / 3600.0
    )
    time_diff = time_diff.fillna(0)
    result["time_diff_hours"] = time_diff

    session_break = result["time_diff_hours"] > 24
    result["session_index"] = session_break.groupby(result["conversation_id"]).cumsum()

    result["session_id"] = (
        result["conversation_id"]
        + "__s"
        + (result["session_index"] + 1).astype(str)
    )

    result = result.drop(columns=["time_diff_hours", "session_index"])

    return result


def generar_conversaciones_jsonl(df_all: pd.DataFrame, output_path: Path) -> None:
    """Genera un archivo JSONL con las conversaciones por sesión (paso 8)."""

    cols = [
        "conversation_id",
        "session_id",
        "client_id",
        "role",
        "text",
        "sent_at",
        "message_index",
    ]
    df = df_all[cols].copy()

    df = df[df["role"].isin(["user", "assistant"])]
    df = df[df["text"].str.len() > 0]

    df = df.sort_values(
        ["conversation_id", "session_id", "sent_at", "message_index"]
    )

    with output_path.open("w", encoding="utf-8") as f:
        for (conversation_id, session_id), group in df.groupby(
            ["conversation_id", "session_id"], sort=False
        ):
            client_ids = group["client_id"].dropna()
            client_id = client_ids.iloc[0] if not client_ids.empty else ""

            messages: list[dict] = []
            for _, row in group.iterrows():
                sent_at = row["sent_at"]
                if pd.isna(sent_at):
                    ts = None
                else:
                    ts = sent_at.isoformat()

                messages.append(
                    {
                        "role": row["role"],
                        "content": row["text"],
                        "timestamp": ts,
                    }
                )

            record = {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "client_id": client_id,
                "messages": messages,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    """Punto de entrada para ejecutar los pasos 3 y 4 sobre todos los CSV.

    - Recorre todos los CSV válidos en RAW_CHATS_DIR.
    - Lee cada archivo con el esquema fijo.
    - Aplica la limpieza básica.
    - Por ahora solo imprime un resumen (sin guardar todavía mensajes.parquet).
    """

    if not RAW_CHATS_DIR.exists():
        raise SystemExit(f"Directorio de chats no encontrado: {RAW_CHATS_DIR}")

    chat_files = sorted(
        p for p in RAW_CHATS_DIR.iterdir() if p.is_file() and es_csv_valido(p)
    )

    if not chat_files:
        raise SystemExit("No se encontraron archivos CSV válidos en raw_chats.")

    dataframes: list[pd.DataFrame] = []

    for path in chat_files:
        df_raw = leer_chat_csv(path)
        df_clean = limpiar_mensajes(df_raw)
        if not df_clean.empty:
            dataframes.append(df_clean)

    if not dataframes:
        raise SystemExit("No se encontraron mensajes válidos después de la limpieza.")

    df_all = pd.concat(dataframes, ignore_index=True)
    df_all = asignar_ids_y_roles(df_all)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_parquet = PROCESSED_DIR / "mensajes.parquet"
    out_csv = PROCESSED_DIR / "mensajes.csv"
    out_jsonl = PROCESSED_DIR / "conversaciones.jsonl"

    df_all.to_parquet(out_parquet, index=False)
    df_all.to_csv(out_csv, index=False)
    generar_conversaciones_jsonl(df_all, out_jsonl)

    total_mensajes = len(df_all)
    n_conversaciones = df_all["conversation_id"].nunique()
    n_sesiones = df_all["session_id"].nunique()

    print(f"Archivos CSV válidos procesados: {len(chat_files)}")
    print(f"Total de mensajes después de limpieza (sin notificaciones): {total_mensajes}")
    print(f"Conversaciones únicas: {n_conversaciones}")
    print(f"Sesiones únicas: {n_sesiones}")
    print(f"Guardado en: {out_parquet}")
    print(f"Guardado también como CSV: {out_csv}")
    print(f"Conversaciones JSONL: {out_jsonl}")


if __name__ == "__main__":
    main()
