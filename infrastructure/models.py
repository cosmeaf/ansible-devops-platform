"""Managed infrastructure: environments, servers and server groups.

These are the objects Ansible acts on. They are deliberately modelled to map
cleanly onto a standard Ansible inventory — a Server becomes a host entry, a
ServerGroup becomes an inventory group — so nothing here implies a proprietary
format. See docs/adr/0005-ansible-execution-engine.md.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from commun.models import BaseModel


class Environment(BaseModel):
    """A deployment tier that servers belong to."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    #: Forces every job against this environment to run in check mode. The
    #: guard rail for production before anyone trusts the platform.
    require_check_mode = models.BooleanField(
        default=False,
        help_text="Only allow check-mode (dry run) executions against this environment.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "environment"
        verbose_name_plural = "environments"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class ServerGroup(BaseModel):
    """An Ansible inventory group — ``webservers``, ``databases``, and so on."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "server group"
        verbose_name_plural = "server groups"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    @property
    def member_count(self) -> int:
        return self.servers.count()


class Client(BaseModel):
    """The customer or business unit a server belongs to.

    Multi-tenant inventories are the normal case for anyone managing
    infrastructure for more than one party, and retrofitting an owner onto
    hosts later is painful. It is optional, so a single-tenant install can
    ignore it entirely.
    """

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "client"
        verbose_name_plural = "clients"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class ServerStatus(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    ONLINE = "ONLINE", "Online"
    OFFLINE = "OFFLINE", "Offline"
    ERROR = "ERROR", "Error"


class OperatingSystem(models.TextChoices):
    LINUX = "LINUX", "Linux"
    WINDOWS = "WINDOWS", "Windows"
    AIX = "AIX", "AIX"
    SOLARIS = "SOLARIS", "Solaris"
    HPUX = "HPUX", "HP-UX"
    BSD = "BSD", "BSD"
    MACOS = "MACOS", "macOS"
    NETWORK = "NETWORK", "Network device"
    OTHER = "OTHER", "Other"


class ConnectionMethod(models.TextChoices):
    """How the platform reaches a host.

    SSH and WinRM are what Ansible uses natively. AGENT is reserved for the
    optional Go agent, which observes rather than changes — it will never be
    required to run automation. See docs/adr/0006-go-agent-planned.md.
    """

    SSH = "SSH", "SSH"
    WINRM = "WINRM", "WinRM"
    AGENT = "AGENT", "Agent (planned)"


#: Sensible default port per connection method.
DEFAULT_PORTS = {
    ConnectionMethod.SSH: 22,
    ConnectionMethod.WINRM: 5986,
    ConnectionMethod.AGENT: 8443,
}


class Server(BaseModel):
    """A managed host.

    ``name`` is the Ansible inventory hostname; ``hostname``/``primary_ip``
    become ``ansible_host``. Keeping them separate means the inventory name can
    stay stable while an address changes.
    """

    name = models.CharField(
        max_length=120, unique=True, help_text="Inventory hostname, e.g. web01."
    )
    description = models.TextField(blank=True)

    hostname = models.CharField(
        max_length=253, blank=True, help_text="DNS name, if the host has one."
    )
    primary_ip = models.GenericIPAddressField(
        null=True, blank=True, help_text="Used as ansible_host when set."
    )
    connection_method = models.CharField(
        max_length=16, choices=ConnectionMethod.choices, default=ConnectionMethod.SSH
    )
    ssh_port = models.PositiveIntegerField(
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        verbose_name="port",
        help_text="Connection port. Defaults to 22 (SSH) or 5986 (WinRM).",
    )
    ansible_user = models.CharField(max_length=64, default="ansible")
    operating_system = models.CharField(
        max_length=16, choices=OperatingSystem.choices, default=OperatingSystem.LINUX
    )

    client = models.ForeignKey(
        Client,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="servers",
    )
    credential = models.ForeignKey(
        "credentials.Credential",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="servers",
        help_text="Credential used to connect. The secret is never exposed.",
    )

    environment = models.ForeignKey(
        Environment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="servers",
    )
    groups = models.ManyToManyField(ServerGroup, blank=True, related_name="servers")

    status = models.CharField(
        max_length=16, choices=ServerStatus.choices, default=ServerStatus.UNKNOWN
    )
    last_connection_test = models.DateTimeField(null=True, blank=True)
    last_successful_connection = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="servers_created",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "server"
        verbose_name_plural = "servers"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["environment", "name"]),
            models.Index(fields=["client", "name"]),
            models.Index(fields=["active"]),
            models.Index(fields=["connection_method"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def ansible_host(self) -> str:
        """The address Ansible should connect to.

        Prefers an explicit IP, falls back to DNS, then to the inventory name —
        which is what a plain Ansible inventory would resolve anyway.
        """
        return self.primary_ip or self.hostname or self.name

    def to_inventory_host(self) -> dict:
        """Render this server as standard Ansible host variables.

        Emits only variables Ansible itself understands, so the generated
        inventory stays usable with plain ``ansible-playbook``.
        """
        variables = {
            "ansible_host": self.ansible_host,
            "ansible_port": self.ssh_port,
            "ansible_user": self.ansible_user,
        }
        if self.connection_method == ConnectionMethod.WINRM:
            variables["ansible_connection"] = "winrm"
            variables["ansible_winrm_transport"] = "ntlm"
        elif self.connection_method == ConnectionMethod.SSH:
            variables["ansible_connection"] = "ssh"
        return variables

    def save(self, *args, **kwargs):
        # Keep the port consistent with the connection method unless the
        # operator has deliberately chosen another one.
        if self._state.adding and self.ssh_port == 22:
            self.ssh_port = DEFAULT_PORTS.get(self.connection_method, 22)
        return super().save(*args, **kwargs)
