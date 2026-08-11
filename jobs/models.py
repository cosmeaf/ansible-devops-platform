"""Every execution becomes a Job.

A run that leaves no record is a run nobody can answer questions about later,
so the row is created before Ansible starts and updated as it progresses —
never written only on success.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from commun.models import BaseModel


class JobStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    QUEUED = "QUEUED", "Queued"
    RUNNING = "RUNNING", "Running"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    CANCELED = "CANCELED", "Canceled"
    TIMEOUT = "TIMEOUT", "Timeout"


#: Statuses from which nothing more will happen.
FINISHED = {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELED, JobStatus.TIMEOUT}


class JobKind(models.TextChoices):
    PLAYBOOK = "PLAYBOOK", "Playbook"
    CONNECTION_TEST = "CONNECTION_TEST", "Connection test"


class Job(BaseModel):
    """One execution of Ansible, and what it produced."""

    kind = models.CharField(max_length=20, choices=JobKind.choices, default=JobKind.PLAYBOOK)
    #: Workspace-relative path. Not a foreign key: playbooks are files, and a
    #: job must still name the one it ran after that file is deleted.
    playbook = models.CharField(max_length=200, blank=True)

    environment = models.ForeignKey(
        "infrastructure.Environment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    client = models.ForeignKey(
        "infrastructure.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    group = models.ForeignKey(
        "infrastructure.ServerGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )
    servers = models.ManyToManyField("infrastructure.Server", blank=True, related_name="jobs")
    credential = models.ForeignKey(
        "credentials.Credential",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )

    limit = models.CharField(max_length=200, blank=True)
    tags = models.CharField(max_length=200, blank=True)
    extra_vars = models.JSONField(default=dict, blank=True)
    check_mode = models.BooleanField(
        default=False, help_text="Dry run. Ansible reports what would change, and changes nothing."
    )

    status = models.CharField(
        max_length=16, choices=JobStatus.choices, default=JobStatus.PENDING, db_index=True
    )
    exit_code = models.IntegerField(null=True, blank=True)
    recap = models.JSONField(default=dict, blank=True)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs_requested",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "job"
        verbose_name_plural = "jobs"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["kind", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.get_status_display()})"

    @property
    def label(self) -> str:
        if self.kind == JobKind.CONNECTION_TEST:
            return "Connection test"
        return self.playbook or "playbook"

    @property
    def finished(self) -> bool:
        return self.status in FINISHED

    @property
    def duration(self):
        """How long the run took, or has been taking."""
        if not self.started_at:
            return None
        return (self.finished_at or timezone.now()) - self.started_at

    def mark_running(self) -> None:
        self.status = JobStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_finished(self, *, status, exit_code=None, output="", recap=None, error="") -> None:
        self.status = status
        self.exit_code = exit_code
        self.output = output
        self.recap = recap or {}
        self.error = error
        self.finished_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "exit_code",
                "output",
                "recap",
                "error",
                "finished_at",
                "updated_at",
            ]
        )
