from ipaddress import ip_address, ip_network
from fastapi import Request, HTTPException
from typing import Optional

from .config import config

TELEGRAM_IP_RANGES = [
    ip_network("149.154.160.0/20"),
    ip_network("91.108.4.0/22"),
]


def get_client_ip(request: Request) -> str:
    """Obtiene la IP real del cliente, considerando proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "0.0.0.0"


def is_telegram_ip(ip_str: str) -> bool:
    """Verifica si la IP pertenece a los rangos de Telegram."""
    try:
        ip = ip_address(ip_str)
        return any(ip in network for network in TELEGRAM_IP_RANGES)
    except ValueError:
        return False


def verify_secret_token(token: Optional[str]) -> bool:
    """Verifica el secret token enviado por Telegram."""
    if not config.TELEGRAM_SECRET_TOKEN:
        return True
    return token == config.TELEGRAM_SECRET_TOKEN


def is_user_allowed(chat_id: int) -> bool:
    """Verifica si el usuario está en la lista blanca."""
    allowed = config.TELEGRAM_ALLOWED_USERS
    if not allowed:
        return True
    return chat_id in allowed


def verify_telegram_request(
    request: Request,
    secret_token: Optional[str],
    skip_ip_check: bool = False
) -> bool:
    """
    Verifica que el request proviene de Telegram.
    Combina validación de IP y secret token.
    """
    if not verify_secret_token(secret_token):
        return False
    
    if not skip_ip_check:
        client_ip = get_client_ip(request)
        if not is_telegram_ip(client_ip):
            return False
    
    return True


def require_telegram_auth(
    request: Request,
    secret_token: Optional[str],
    skip_ip_check: bool = False
):
    """Middleware de autenticación para el webhook."""
    if not verify_telegram_request(request, secret_token, skip_ip_check):
        raise HTTPException(status_code=403, detail="Unauthorized")
