"""Celery tasks that run Ansible.

The web request only queues; nothing here runs in the request/response cycle.
An Ansible run takes minutes, and a job that dies with the worker must still
leave a row saying so.
"""

import logging

from celery import shared_task

from automation import runner
from infrastructure.models import ServerStatus

from .models import Job, JobStatus

logger = logging.getLogger(__name__)

#: Ansible's vocabulary for how a run ended, in the platform's terms.
_STATUS = {
    runner.SUCCESSFUL: JobStatus.SUCCESS,
    runner.FAILED: JobStatus.FAILED,
    runner.TIMEOUT: JobStatus.TIMEOUT,
    runner.CANCELED: JobStatus.CANCELED,
}


@shared_task(name="jobs.run_job")
def run_job(job_uuid: str) -> str:
    """Execute a queued job and record what happened."""
    job = Job.objects.filter(uuid=job_uuid).first()
    if job is None:
        logger.warning("job %s no longer exists", job_uuid)
        return "missing"
    if job.finished:
        return job.status

    job.mark_running()
    servers = list(job.servers.select_related("credential").all())

    if not servers:
        job.mark_finished(
            status=JobStatus.FAILED,
            error="The job selected no servers, so there was nothing to run against.",
        )
        return job.status

    try:
        result = runner.run_playbook(
            servers,
            playbook=job.playbook,
            credential=job.credential,
            limit=job.limit,
            tags=job.tags,
            extra_vars=job.extra_vars,
            check_mode=job.check_mode,
        )
    except Exception as error:  # noqa: BLE001 - the row must record any failure
        logger.exception("job %s failed to start", job_uuid)
        job.mark_finished(status=JobStatus.FAILED, error=str(error))
        return job.status

    job.mark_finished(
        status=_STATUS.get(result.status, JobStatus.FAILED),
        exit_code=result.rc,
        output=result.stdout,
        recap={name: vars(host) for name, host in result.hosts.items()},
    )
    _record_reachability(servers, result)
    return job.status


# Not named test_*: pytest collects any importable name starting with test_,
# and a Celery task is not a test.
@shared_task(name="jobs.check_connection")
def check_connection(job_uuid: str) -> str:
    """Answer whether the platform can reach a host, using Ansible's own ping.

    ping for SSH, win_ping for WinRM: the same check anyone would run by hand,
    so a result here means the same thing as a result in a terminal.
    """
    from infrastructure.models import ConnectionMethod

    job = Job.objects.filter(uuid=job_uuid).first()
    if job is None:
        return "missing"

    job.mark_running()
    servers = list(job.servers.select_related("credential").all())
    if not servers:
        job.mark_finished(status=JobStatus.FAILED, error="No server to test.")
        return job.status

    windows = all(s.connection_method == ConnectionMethod.WINRM for s in servers)
    module = "ansible.windows.win_ping" if windows else "ping"

    try:
        result = runner.run_module(servers, module=module, credential=job.credential, timeout=30)
    except Exception as error:  # noqa: BLE001
        logger.exception("connection test %s failed to start", job_uuid)
        job.mark_finished(status=JobStatus.FAILED, error=str(error))
        _mark_servers(servers, ServerStatus.ERROR)
        return job.status

    job.mark_finished(
        status=_STATUS.get(result.status, JobStatus.FAILED),
        exit_code=result.rc,
        output=result.stdout,
        recap={name: vars(host) for name, host in result.hosts.items()},
    )
    _record_reachability(servers, result)
    return job.status


def _record_reachability(servers, result) -> None:
    """Update each server's status from what the run actually observed."""
    from django.utils import timezone

    now = timezone.now()
    for server in servers:
        host = result.hosts.get(server.name)
        fields = ["status", "last_connection_test", "updated_at"]
        server.last_connection_test = now

        if host is None:
            # The host never appeared in the recap: Ansible could not act on it.
            server.status = ServerStatus.ERROR
        elif host.unreachable:
            server.status = ServerStatus.OFFLINE
        elif host.failures:
            # It answered, but the check did not succeed — reachable is not the
            # same as usable, and calling that ONLINE would be a lie.
            server.status = ServerStatus.ERROR
        else:
            server.status = ServerStatus.ONLINE
            server.last_successful_connection = now
            fields.append("last_successful_connection")

        server.save(update_fields=fields)


def _mark_servers(servers, status) -> None:
    from django.utils import timezone

    for server in servers:
        server.status = status
        server.last_connection_test = timezone.now()
        server.save(update_fields=["status", "last_connection_test", "updated_at"])
