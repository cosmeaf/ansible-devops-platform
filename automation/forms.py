"""Forms for editing workspace files."""

from pathlib import Path

from django import forms

from . import workspace
from .workspace import PLAYBOOK_SUFFIXES, NotAPlaybook, UnsafePath, playbook_path, validate
from .workspace import validate_syntax as validate_yaml


class PlaybookForm(forms.Form):
    """A playbook: a file name and its YAML.

    The name is only editable while creating. Renaming through the editor
    would quietly leave the old file behind, so it is a separate action the
    editor does not pretend to offer.
    """

    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "linux/update.yml"}),
        help_text="Path under playbooks/. Must end in .yml or .yaml.",
    )
    # strip=False: leading indentation is meaningful in YAML, and the final
    # newline of a file is not the form's to remove.
    content = forms.CharField(widget=forms.Textarea, required=False, strip=False)

    def __init__(self, *args, editing: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.editing = editing
        if editing:
            self.fields["name"].disabled = True
            self.fields["name"].initial = editing

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        try:
            playbook_path(name)
        except NotAPlaybook:
            raise forms.ValidationError(
                f"Use one of {' or '.join(PLAYBOOK_SUFFIXES)} — Ansible reads YAML."
            ) from None
        except UnsafePath as error:
            raise forms.ValidationError(str(error)) from None
        return name

    def clean_content(self):
        """Refuse to save a file Ansible could not load."""
        content = self.cleaned_data.get("content", "")
        if problems := validate(content):
            raise forms.ValidationError(problems)
        return content


class WorkspacePathField(forms.CharField):
    """A path inside the workspace, validated the way the workspace does."""

    def clean(self, value):
        value = (super().clean(value) or "").strip().strip("/")
        try:
            workspace.resolve(value)
        except workspace.UnsafePath as error:
            raise forms.ValidationError(str(error)) from None
        return value


class FileForm(forms.Form):
    """A workspace file: where it lives, and what is in it."""

    name = WorkspacePathField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "playbooks/linux/update.yml"}
        ),
        help_text="Path inside the workspace.",
    )
    content = forms.CharField(widget=forms.Textarea, required=False, strip=False)

    def __init__(self, *args, path: str = "", parent: str = "", naming: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.parent = parent
        self.naming = naming
        if not naming:
            del self.fields["name"]
        elif parent and not self.is_bound:
            self.fields["name"].initial = f"{parent}/"

    def clean_name(self):
        name = self.cleaned_data.get("name", "")
        if not name:
            raise forms.ValidationError("A path is required.")
        if workspace.resolve(name).exists():
            raise forms.ValidationError("Something already exists at that path.")
        if Path(name).suffix not in workspace.EDITABLE_SUFFIXES:
            allowed = ", ".join(sorted(s for s in workspace.EDITABLE_SUFFIXES if s))
            raise forms.ValidationError(f"Use one of these extensions: {allowed}.")
        return name

    def clean_content(self):
        """Validate as much as the file's location justifies.

        A playbook is a list of plays and is checked as one. Any other YAML —
        group_vars, host_vars, an inventory — only has to parse: rejecting a
        mapping for not being a list of plays would be wrong.
        """
        content = self.cleaned_data.get("content", "")
        target = self.cleaned_data.get("name") or self.path
        if not target.endswith((".yml", ".yaml")):
            return content

        under_playbooks = target.startswith(workspace.PLAYBOOK_DIR + "/")
        problems = validate(content) if under_playbooks else validate_yaml(content)
        if problems:
            raise forms.ValidationError(problems)
        return content


class NewFolderForm(forms.Form):
    name = WorkspacePathField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "input", "placeholder": "roles/nginx/tasks"}),
        help_text="Path inside the workspace.",
    )

    def __init__(self, *args, parent: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        if parent and not self.is_bound:
            self.fields["name"].initial = f"{parent}/"

    def clean_name(self):
        name = self.cleaned_data["name"]
        if workspace.resolve(name).exists():
            raise forms.ValidationError("Something already exists at that path.")
        return name


class RenameForm(forms.Form):
    name = WorkspacePathField(
        max_length=200,
        label="New path",
        widget=forms.TextInput(attrs={"class": "input"}),
        help_text="Moving between folders is a rename, as it is in a shell.",
    )

    def __init__(self, *args, path: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path

    def clean_name(self):
        name = self.cleaned_data["name"]
        if name == self.path:
            raise forms.ValidationError("That is the path it already has.")
        return name
