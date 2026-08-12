"""The form that launches a playbook."""

from django import forms

from automation.runner import parse_extra_vars
from automation.workspace import list_playbooks
from credentials.models import Credential
from infrastructure.models import Client, Environment, Server, ServerGroup

from .models import Job


class RunPlaybookForm(forms.ModelForm):
    """Choose what to run, where, and whether it is a dry run."""

    playbook = forms.ChoiceField(help_text="From the workspace.")
    extra_vars_text = forms.CharField(
        label="Extra vars",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "app_version: 4.12.0"}),
        required=False,
        strip=False,
        help_text="YAML mapping, as --extra-vars takes.",
    )

    class Meta:
        model = Job
        fields = [
            "playbook",
            "environment",
            "client",
            "group",
            "credential",
            "limit",
            "tags",
            "check_mode",
        ]
        widgets = {
            "limit": forms.TextInput(attrs={"placeholder": "web01,web02"}),
            "tags": forms.TextInput(attrs={"placeholder": "deploy"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["playbook"].choices = [(p.name, p.name) for p in list_playbooks()]
        self.fields["environment"].queryset = Environment.objects.filter(active=True)
        self.fields["client"].queryset = Client.objects.filter(active=True)
        self.fields["group"].queryset = ServerGroup.objects.all()
        self.fields["credential"].queryset = Credential.objects.all()
        self.fields["environment"].empty_label = "Any environment"
        self.fields["client"].empty_label = "Any client"
        self.fields["group"].empty_label = "Any group"
        self.fields["credential"].empty_label = "Each server's own credential"
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "input")

    def clean_extra_vars_text(self):
        try:
            return parse_extra_vars(self.cleaned_data.get("extra_vars_text", ""))
        except ValueError as error:
            raise forms.ValidationError(str(error)) from None

    def clean(self):
        """Refuse a job that would target nothing.

        Running against an empty selection is not a no-op worth recording; it
        is almost always a filter the operator did not mean.
        """
        cleaned = super().clean()
        if not self.errors and not self.selected_servers(cleaned).exists():
            raise forms.ValidationError(
                "No active server matches that environment, client and group."
            )
        return cleaned

    @staticmethod
    def selected_servers(cleaned):
        """The servers the chosen filters resolve to."""
        servers = Server.objects.filter(active=True)
        if environment := cleaned.get("environment"):
            servers = servers.filter(environment=environment)
        if client := cleaned.get("client"):
            servers = servers.filter(client=client)
        if group := cleaned.get("group"):
            servers = servers.filter(groups=group)
        return servers
