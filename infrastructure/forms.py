"""Forms for the Ansible management screens."""

from django import forms

from credentials.models import Credential

from .models import Client, Environment, Server, ServerGroup


class ServerForm(forms.ModelForm):
    class Meta:
        model = Server
        fields = [
            "name",
            "description",
            "hostname",
            "primary_ip",
            "connection_method",
            "ssh_port",
            "ansible_user",
            "operating_system",
            "client",
            "environment",
            "groups",
            "credential",
            "active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "groups": forms.CheckboxSelectMultiple(),
            "name": forms.TextInput(attrs={"placeholder": "web01"}),
            "hostname": forms.TextInput(attrs={"placeholder": "web01.example.com"}),
            "primary_ip": forms.TextInput(attrs={"placeholder": "10.10.10.21"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["credential"].queryset = Credential.objects.all()
        self.fields["client"].queryset = Client.objects.filter(active=True)
        self.fields["environment"].queryset = Environment.objects.filter(active=True)
        for name, field in self.fields.items():
            if name != "groups" and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "input")

    def clean(self):
        """A host must be addressable.

        Ansible would fall back to the inventory name, which works only if DNS
        happens to resolve it — better to fail here than at execution time.
        """
        cleaned = super().clean()
        if not cleaned.get("hostname") and not cleaned.get("primary_ip"):
            self.add_error(
                "primary_ip",
                "Provide an IP address or a hostname so Ansible can reach this host.",
            )
        return cleaned


class ServerGroupForm(forms.ModelForm):
    class Meta:
        model = ServerGroup
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")


class EnvironmentForm(forms.ModelForm):
    class Meta:
        model = Environment
        fields = ["name", "description", "require_check_mode", "active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "input")


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "description", "contact_email", "active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "input")


class CredentialForm(forms.ModelForm):
    """Write-only secret entry.

    The field is never populated from the stored value, so this form cannot be
    used to read a secret back — only to set or replace one.
    """

    secret = forms.CharField(
        widget=forms.PasswordInput(render_value=False, attrs={"class": "input"}),
        required=False,
        help_text="Leave blank to keep the current secret.",
    )

    class Meta:
        model = Credential
        fields = ["name", "description", "type", "username"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "secret":
                field.widget.attrs.setdefault("class", "input")

    def clean_secret(self):
        secret = self.cleaned_data.get("secret")
        if not self.instance.pk and not secret:
            raise forms.ValidationError("A new credential needs a secret.")
        return secret

    def save(self, commit=True):
        credential = super().save(commit=False)
        if secret := self.cleaned_data.get("secret"):
            credential.set_secret(secret)
        if commit:
            credential.save()
        return credential
