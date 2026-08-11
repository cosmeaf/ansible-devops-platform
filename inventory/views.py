"""The generated inventory, on the web.

Read-only on purpose: the inventory is derived from the registered servers, so
it is edited by editing them. What this screen owes the user is the ability to
see exactly what Ansible will see, and to take the file away and run it by hand.
"""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import render as render_template
from django.views.decorators.http import require_GET

from infrastructure.models import Client, Environment

from .builder import build, graph, to_yaml


def _selection(request):
    """Read the environment/client filters off the querystring."""
    return {
        "environment": request.GET.get("environment", "").strip() or None,
        "client": request.GET.get("client", "").strip() or None,
        "include_inactive": request.GET.get("inactive") == "1",
    }


@login_required
@permission_required("infrastructure.view_server", raise_exception=True)
@require_GET
def preview(request):
    selection = _selection(request)
    inventory = build(**selection)
    content = to_yaml(inventory)

    if request.GET.get("download") == "1":
        response = HttpResponse(content, content_type="application/yaml")
        response["Content-Disposition"] = f'attachment; filename="{_filename(selection)}"'
        return response

    return render_template(
        request,
        "manage/inventory.html",
        {
            "section": "inventory",
            "yaml": content,
            "graph": graph(inventory),
            "host_count": len(inventory["all"]["hosts"]),
            "group_count": len(inventory["all"].get("children", {})),
            "environments": Environment.objects.filter(active=True),
            "clients": Client.objects.filter(active=True),
            "selected_environment": selection["environment"] or "",
            "selected_client": selection["client"] or "",
            "include_inactive": selection["include_inactive"],
            "query": request.GET.urlencode(),
        },
    )


def _filename(selection) -> str:
    """Name the download after what it contains, not just 'hosts.yml'."""
    scope = selection["environment"] or selection["client"]
    return f"{scope}-hosts.yml" if scope else "hosts.yml"
