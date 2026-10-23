"""
Where a file can be fetched from.

Public files (logos, posters) have one permanent address that never changes and can be
cached forever: replacing a logo makes a new file with a new address.

Private files (avatars) are fetched through a signed address that stops working after five
minutes. The browser cannot send a login token with an <img> tag, so the link itself carries
the permission, and the API only hands such a link to someone who may see the thing the file
belongs to (for an avatar, the profile).
"""

import uuid

import jwt

from app.core.config import get_settings
from app.modules.files.models import File, FileVisibility
from app.modules.identity.security import create_purpose_token, decode_purpose_token

FILE_TOKEN_PURPOSE = "file_access"
FILE_URL_LIFETIME_MINUTES = 5


def public_file_path(file_id: uuid.UUID) -> str:
    return f"{get_settings().api_v1_prefix}/files/{file_id}/content"


def signed_file_path(file_id: uuid.UUID) -> str:
    token = create_purpose_token(
        file_id, purpose=FILE_TOKEN_PURPOSE, expire_minutes=FILE_URL_LIFETIME_MINUTES
    )
    return f"{public_file_path(file_id)}?token={token}"


def url_for(file: File) -> str:
    if file.visibility == FileVisibility.PUBLIC:
        return public_file_path(file.id)
    return signed_file_path(file.id)


def token_allows(token: str, file_id: uuid.UUID) -> bool:
    """True only for an unexpired token that was signed for exactly this file."""
    try:
        payload = decode_purpose_token(token, purpose=FILE_TOKEN_PURPOSE)
    except jwt.PyJWTError:
        return False
    return payload.get("sub") == str(file_id)
