"""
Cloudinary integration utilities.

Provides a single ``upload_profile_image`` helper that handles
configuration, validation, transformation, and error handling so
the view layer stays thin and the integration is easily testable.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_TYPES = frozenset([
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
])
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

PROFILE_IMAGE_FOLDER = "ese-task-manager/profiles"
PROFILE_IMAGE_TRANSFORMATION = [
    {"width": 300, "height": 300, "crop": "fill", "gravity": "face"},
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ImageValidationError(Exception):
    """Raised when an uploaded file fails pre-upload checks."""



def validate_image(image_file):
    """
    Validate an ``UploadedFile`` before sending it to Cloudinary.

    Raises
    ------
    ImageValidationError
        If content type or size is unacceptable.
    """
    if image_file.content_type not in ALLOWED_IMAGE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_TYPES))
        raise ImageValidationError(
            f"Unsupported file type '{image_file.content_type}'. "
            f"Allowed: {allowed}"
        )

    if image_file.size > MAX_IMAGE_SIZE:
        mb = MAX_IMAGE_SIZE // (1024 * 1024)
        raise ImageValidationError(
            f"Image file size ({image_file.size:,} bytes) exceeds "
            f"the {mb} MB limit."
        )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _configure_cloudinary():
    """
    Ensure the ``cloudinary`` library is configured from Django settings.

    Called once per upload rather than at module level so that tests can
    override settings freely.
    """
    import cloudinary

    cloudinary.config(
        cloud_name=getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
        api_key=getattr(settings, "CLOUDINARY_API_KEY", ""),
        api_secret=getattr(settings, "CLOUDINARY_API_SECRET", ""),
    )


def upload_profile_image(image_file, *, user_id=None):
    """
    Upload an image to Cloudinary with profile-photo transformations.

    Parameters
    ----------
    image_file : django.core.files.uploadedfile.UploadedFile
        The raw file from ``request.FILES``.
    user_id : str | None
        Optional user identifier appended to the Cloudinary public ID
        so each user's image has a stable, deterministic name (enabling
        implicit overwrites on re-upload).

    Returns
    -------
    str
        The HTTPS URL of the uploaded (and transformed) image.

    Raises
    ------
    ImageValidationError
        If the file fails type/size checks.
    RuntimeError
        If the Cloudinary upload itself fails.
    """
    validate_image(image_file)
    _configure_cloudinary()

    import cloudinary.uploader

    public_id = None
    if user_id:
        public_id = f"{PROFILE_IMAGE_FOLDER}/{user_id}"

    upload_kwargs = {
        "folder": PROFILE_IMAGE_FOLDER if not public_id else None,
        "public_id": public_id,
        "overwrite": True,
        "transformation": PROFILE_IMAGE_TRANSFORMATION,
        "resource_type": "image",
    }
    # Remove None values so Cloudinary uses its defaults
    upload_kwargs = {k: v for k, v in upload_kwargs.items() if v is not None}

    try:
        result = cloudinary.uploader.upload(image_file, **upload_kwargs)
        url = result["secure_url"]
        logger.info("Cloudinary upload succeeded: %s", url)
        return url
    except Exception as exc:
        logger.error("Cloudinary upload failed: %s", exc)
        raise RuntimeError("Image upload to Cloudinary failed.") from exc
