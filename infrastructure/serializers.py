"""DRF serializers for managed infrastructure."""

from rest_framework import serializers

from credentials.models import Credential

from .models import Client, Environment, Server, ServerGroup


class EnvironmentSerializer(serializers.ModelSerializer):
    server_count = serializers.IntegerField(source="servers.count", read_only=True)

    class Meta:
        model = Environment
        fields = [
            "uuid",
            "name",
            "slug",
            "description",
            "active",
            "require_check_mode",
            "server_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "slug", "created_at", "updated_at"]


class ServerGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ServerGroup
        fields = [
            "uuid",
            "name",
            "slug",
            "description",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "slug", "created_at", "updated_at"]


class ClientSerializer(serializers.ModelSerializer):
    server_count = serializers.IntegerField(source="servers.count", read_only=True)

    class Meta:
        model = Client
        fields = [
            "uuid",
            "name",
            "slug",
            "description",
            "contact_email",
            "active",
            "server_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "slug", "created_at", "updated_at"]


class ServerSerializer(serializers.ModelSerializer):
    environment = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Environment.objects.all(),
        required=False,
        allow_null=True,
    )
    groups = serializers.SlugRelatedField(
        slug_field="slug", queryset=ServerGroup.objects.all(), many=True, required=False
    )
    client = serializers.SlugRelatedField(
        slug_field="slug", queryset=Client.objects.all(), required=False, allow_null=True
    )
    credential = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Credential.objects.all(),
        required=False,
        allow_null=True,
    )
    ansible_host = serializers.CharField(read_only=True)
    inventory_host = serializers.SerializerMethodField()

    class Meta:
        model = Server
        fields = [
            "uuid",
            "name",
            "description",
            "hostname",
            "primary_ip",
            "ssh_port",
            "ansible_user",
            "operating_system",
            "connection_method",
            "client",
            "credential",
            "environment",
            "groups",
            "status",
            "active",
            "ansible_host",
            "inventory_host",
            "last_connection_test",
            "last_successful_connection",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "status",
            "last_connection_test",
            "last_successful_connection",
            "created_at",
            "updated_at",
        ]

    def get_inventory_host(self, obj: Server) -> dict:
        """What this server contributes to a standard Ansible inventory."""
        return obj.to_inventory_host()

    def validate(self, attrs):
        """A host must be addressable.

        Ansible falls back to the inventory name when no address is given, which
        silently works only if DNS happens to resolve it. Require something
        explicit instead of letting that fail at execution time.
        """
        hostname = attrs.get("hostname", getattr(self.instance, "hostname", ""))
        primary_ip = attrs.get("primary_ip", getattr(self.instance, "primary_ip", None))
        if not hostname and not primary_ip:
            raise serializers.ValidationError(
                {
                    "primary_ip": (
                        "Provide an IP address or a hostname so Ansible can reach this host."
                    )
                }
            )
        return attrs
