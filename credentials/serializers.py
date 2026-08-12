"""DRF serializers for credentials.

The stored secret is write-only and is never present on any response. There is
no serializer field that can return it — that is the mechanism, not a
convention.
"""

from rest_framework import serializers

from .models import Credential


class CredentialSerializer(serializers.ModelSerializer):
    #: Accepted on write, never rendered on read.
    secret = serializers.CharField(write_only=True, required=False, allow_blank=False)
    has_secret = serializers.BooleanField(read_only=True)

    class Meta:
        model = Credential
        fields = [
            "uuid",
            "name",
            "description",
            "type",
            "username",
            "secret",
            "has_secret",
            "last_used_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "last_used_at", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("secret"):
            raise serializers.ValidationError({"secret": "A new credential needs a secret."})
        return attrs

    def create(self, validated_data):
        secret = validated_data.pop("secret")
        credential = Credential(**validated_data)
        credential.set_secret(secret)
        credential.save()
        return credential

    def update(self, instance, validated_data):
        secret = validated_data.pop("secret", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if secret:
            instance.set_secret(secret)
        instance.save()
        return instance
