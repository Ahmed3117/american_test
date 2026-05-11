from rest_framework import serializers
from django.conf import settings

from .models import User, UserDevice


def get_full_file_url(file_field, request=None):
    """
    Get the full URL for a file/image field.
    Returns the complete URL including domain.
    """
    if not file_field:
        return None
    
    # Get the file path/name
    file_path = file_field.name if hasattr(file_field, 'name') else str(file_field)
    
    if not file_path:
        return None
    
    # If already a full URL, return as-is
    if file_path.startswith('http://') or file_path.startswith('https://'):
        return file_path
    
    # Build full URL using S3 custom domain or request
    custom_domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
    
    if custom_domain:
        # Use S3/R2 custom domain
        return f"https://{custom_domain}/{file_path}"
    elif request:
        # Use request to build absolute URI
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{file_path}")
    else:
        # Fallback to MEDIA_URL
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        if media_url.startswith('http'):
            return f"{media_url.rstrip('/')}/{file_path}"
        return f"{media_url}{file_path}"


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)  # Make password optional for updates
    # user_profile_image removed per request

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'password', 'name','government',
            'is_staff', 'is_superuser', 'user_type', 'parent_phone',
            'created_at'
        )
        extra_kwargs = {
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
            'email': {'required': False, 'allow_null': True, 'allow_blank': True},
            'user_type': {'required': True},  # Now required since field is NOT NULL
            'parent_phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'password': {'required': False},  # Make password optional for updates
        }
    
    def validate_username(self, value):
        """Validate that username is a valid Egyptian phone number for students only"""
        # Skip validation during updates if user_type is not being changed
        # We'll validate in the validate() method where we have access to all fields
        return value.strip()
    
    def validate(self, data):
        """Validate username format based on user_type"""
        import re
        
        username = data.get('username')
        user_type = data.get('user_type')
        
        # For updates, get the current user_type if not provided
        if self.instance and not user_type:
            user_type = self.instance.user_type
        
        # Only validate phone format for students
        if user_type == 'student' and username:
            # Check if it matches Egyptian phone pattern (starts with 01 and has 11 digits)
            if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', username):
                raise serializers.ValidationError({
                    'username': 'بالنسبة للطلاب، يجب أن يكون اسم المستخدم رقم هاتف مصري صالح (مثل 01012345678)'
                })
        
        return data
    
    def update(self, instance, validated_data):
        """
        Handle user updates with proper password hashing
        """
        # Extract password from validated_data
        password = validated_data.pop('password', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle password separately to ensure proper hashing
        if password:
            instance.set_password(password)  # This properly hashes the password
        
        instance.save()
        return instance

    def create(self, validated_data):
        """
        Handle user creation with proper password hashing
        """
        email = validated_data.get('email', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=email,
            password=validated_data['password'],
            name=validated_data.get('name', ''),
            is_staff=validated_data.get('is_staff', False),
            is_superuser=validated_data.get('is_superuser', False),
            user_type=validated_data.get('user_type', None),
            parent_phone=validated_data.get('parent_phone', None),
            government=validated_data.get('government', None),
        )
        return user


class AdminListUserSerializer(serializers.ModelSerializer):
    """Serializer for admin listing (admins only)."""
    # user_profile_image removed from admin listing

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'name', 'is_staff', 'is_superuser',
            'is_banned', 'banned_at', 'ban_reason', 'created_at'
        )


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for non-admin users listing."""
    # user_profile_image removed from public listing

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'name', 'government', 'user_type',
            'parent_phone',
            'is_banned', 'banned_at', 'ban_reason', 'created_at'
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    
    def validate_username(self, value):
        """Validate that username exists and is a valid phone number for students"""
        import re
        from .models import User
        
        # Remove any whitespace
        value = value.strip()
        
        # Check if user exists
        try:
            user = User.objects.get(username=value)
            # Only validate phone format for students
            if user.user_type == 'student':
                if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', value):
                    raise serializers.ValidationError(
                        'بالنسبة للطلاب، يجب أن يكون اسم المستخدم رقم هاتف مصري صالح (مثل 01012345678)'
                    )
        except User.DoesNotExist:
            # Don't reveal whether user exists or not for security
            pass
        
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    username = serializers.CharField()
    otp = serializers.CharField()
    new_password = serializers.CharField()
    
    def validate_username(self, value):
        """Validate that username is a valid phone number for students"""
        import re
        from .models import User
        
        # Remove any whitespace
        value = value.strip()
        
        # Check if user exists
        try:
            user = User.objects.get(username=value)
            # Only validate phone format for students
            if user.user_type == 'student':
                if not re.match(r'^01[0-2,5]{1}[0-9]{8}$', value):
                    raise serializers.ValidationError(
                        'بالنسبة للطلاب، يجب أن يكون اسم المستخدم رقم هاتف مصري صالح (مثل 01012345678)'
                    )
        except User.DoesNotExist:
            # Don't reveal whether user exists or not for security
            pass
        
        return value

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)


# ============== Device Management Serializers ==============

class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for viewing device information"""
    class Meta:
        model = UserDevice
        fields = [
            'id', 'device_id', 'device_name', 'ip_address', 'user_agent',
            'logged_in_at', 'last_used_at', 'is_active', 'is_banned', 'banned_at', 'ban_reason'
        ]
        read_only_fields = ['logged_in_at', 'last_used_at']


class StudentDeviceListSerializer(serializers.ModelSerializer):
    """Serializer for listing student with their devices"""
    devices = UserDeviceSerializer(many=True, read_only=True)
    active_devices_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'name', 'max_allowed_devices',
            'active_devices_count', 'is_banned', 'banned_at', 'ban_reason', 'devices'
        ]
    
    def get_active_devices_count(self, obj):
        return obj.devices.filter(is_active=True).count()


class UpdateMaxDevicesSerializer(serializers.Serializer):
    """Serializer for updating max allowed devices for a student"""
    max_allowed_devices = serializers.IntegerField(min_value=1, max_value=10)


class RemoveDeviceSerializer(serializers.Serializer):
    """Serializer for removing a specific device"""
    device_id = serializers.IntegerField()


# ============== Deleted User Archive Serializers ==============

class DeletedUserArchiveSerializer(serializers.Serializer):
    """Serializer for viewing deleted user archives"""
    id = serializers.IntegerField(read_only=True)
    original_user_id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    user_type = serializers.CharField(read_only=True)
    parent_phone = serializers.CharField(read_only=True)
    government = serializers.CharField(read_only=True)
    was_banned = serializers.BooleanField(read_only=True)
    ban_reason = serializers.CharField(read_only=True)
    original_created_at = serializers.DateTimeField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True)
    is_restored = serializers.BooleanField(read_only=True)
    deleted_by = serializers.IntegerField(source='deleted_by.id', read_only=True)
    deleted_by_username = serializers.CharField(source='deleted_by.username', read_only=True)
    deleted_by_name = serializers.CharField(source='deleted_by.name', read_only=True)
    deletion_reason = serializers.CharField(read_only=True)
    user_data_snapshot = serializers.JSONField(read_only=True)


class RestoreUserSerializer(serializers.Serializer):
    """Serializer for restoring a deleted user"""
    archive_id = serializers.IntegerField(help_text="ID of the deleted user archive to restore")
    password = serializers.CharField(required=False, allow_blank=True)
