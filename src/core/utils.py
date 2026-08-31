from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import boto3

# Generate presigned URL valid for 1 hour

def generate_upload_url(object_name):
    if settings.MEDIA_STORAGE_BACKEND not in {'r2', 's3'}:
        raise ImproperlyConfigured(
            'Presigned uploads require a configured R2 or S3 media backend.'
        )

    options = settings.STORAGES['default']['OPTIONS']
    s3 = boto3.client(
        "s3",
        region_name=options['region_name'],
        endpoint_url=options.get('endpoint_url'),
        aws_access_key_id=options['access_key'],
        aws_secret_access_key=options['secret_key'],
    )

    url = s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': options['bucket_name'], 'Key': object_name},
        ExpiresIn=3600
    )
    return url
