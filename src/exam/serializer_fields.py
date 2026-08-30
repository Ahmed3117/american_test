from rest_framework import serializers


class StoredFileField(serializers.FileField):
    """File field that keeps legacy absolute URLs readable.

    New uploads are rendered through Django's configured storage backend. This
    produces Cloudflare R2 URLs in production and local media URLs in tests and
    development. Absolute values saved before the FileField migration are
    returned unchanged until their videos are replaced.
    """

    def to_representation(self, value):
        if not value:
            return None

        name = getattr(value, "name", str(value))
        if name.startswith(("http://", "https://")):
            return name

        return super().to_representation(value)


def stored_file_url(value):
    """Return a storage URL while tolerating legacy absolute URL values."""
    if not value:
        return None

    name = getattr(value, "name", str(value))
    if name.startswith(("http://", "https://")):
        return name

    try:
        return value.url
    except (AttributeError, ValueError):
        return None
