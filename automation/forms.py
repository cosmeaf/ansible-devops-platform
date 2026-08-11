"""Forms for editing workspace files."""

from django import forms

from .workspace import PLAYBOOK_SUFFIXES, NotAPlaybook, UnsafePath, playbook_path, validate


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
