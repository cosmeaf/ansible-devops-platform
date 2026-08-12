from django import forms
from django.contrib import admin

from .models import Credential


class CredentialAdminForm(forms.ModelForm):
    """Write-only secret entry.

    The field is never populated from the stored value, so the admin cannot be
    used to read a secret back — only to replace one.
    """

    secret = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Leave blank to keep the current secret. Entering a value replaces it.",
    )

    class Meta:
        model = Credential
        fields = ("name", "description", "type", "username")

    def save(self, commit=True):
        credential = super().save(commit=False)
        if secret := self.cleaned_data.get("secret"):
            credential.set_secret(secret)
        if commit:
            credential.save()
        return credential

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get("secret"):
            self.add_error("secret", "A new credential needs a secret.")
        return cleaned


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    form = CredentialAdminForm
    list_display = ("name", "type", "username", "has_secret", "last_used_at", "created_by")
    list_filter = ("type",)
    search_fields = ("name", "description", "username")
    readonly_fields = ("uuid", "created_by", "last_used_at", "created_at", "updated_at")
    ordering = ("name",)

    @admin.display(boolean=True, description="secret stored")
    def has_secret(self, obj: Credential) -> bool:
        return obj.has_secret

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
