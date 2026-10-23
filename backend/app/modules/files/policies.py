"""
The rules for each kind of upload: who can see it, how big it may be, how large the picture
may be. One policy per purpose, so adding a purpose means adding one entry here.
"""

from dataclasses import dataclass

from app.modules.files.models import FilePurpose, FileVisibility

MIB = 1024 * 1024

# Decoded size cap, not file size: a small PNG can expand into gigabytes of pixels.
MAX_PIXELS = 25_000_000

# Every upload route shares this, so the body limit for the upload route covers the largest
# policy plus the multipart envelope.
UPLOAD_MAX_BODY_BYTES = 6 * MIB

# What one person may keep, and how fast they may add. The count includes everything they
# own, attached or not.
MAX_FILES_PER_USER = 50
UPLOADS_PER_HOUR = 20


@dataclass(frozen=True)
class UploadPolicy:
    purpose: FilePurpose
    visibility: FileVisibility
    max_bytes: int
    max_dimension: int
    max_pixels: int = MAX_PIXELS


POLICIES: dict[FilePurpose, UploadPolicy] = {
    # Avatars are private files: they are shown through short-lived signed links, handed out
    # only to people who may see the profile.
    FilePurpose.AVATAR: UploadPolicy(
        purpose=FilePurpose.AVATAR,
        visibility=FileVisibility.PRIVATE,
        max_bytes=2 * MIB,
        max_dimension=1024,
    ),
    # Logos and posters are public: anyone may load them from a permanent address.
    FilePurpose.ORGANIZATION_LOGO: UploadPolicy(
        purpose=FilePurpose.ORGANIZATION_LOGO,
        visibility=FileVisibility.PUBLIC,
        max_bytes=2 * MIB,
        max_dimension=1024,
    ),
    FilePurpose.EVENT_POSTER: UploadPolicy(
        purpose=FilePurpose.EVENT_POSTER,
        visibility=FileVisibility.PUBLIC,
        max_bytes=5 * MIB,
        max_dimension=2048,
    ),
}

assert max(p.max_bytes for p in POLICIES.values()) < UPLOAD_MAX_BODY_BYTES
