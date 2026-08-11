"""Platform settings model, including secret masking."""

import pytest
from django.db import IntegrityError

from settings_platform.models import REDACTED, PlatformSetting


@pytest.mark.django_db
def test_category_and_key_are_unique_together():
    PlatformSetting.objects.create(category="smtp", key="host", value={"v": "mail"})

    with pytest.raises(IntegrityError):
        PlatformSetting.objects.create(category="smtp", key="host", value={"v": "other"})


@pytest.mark.django_db
def test_same_key_is_allowed_in_a_different_category():
    PlatformSetting.objects.create(category="smtp", key="host", value={"v": "mail"})
    PlatformSetting.objects.create(category="ldap", key="host", value={"v": "dc"})

    assert PlatformSetting.objects.count() == 2


@pytest.mark.django_db
def test_str_is_dotted_path():
    setting = PlatformSetting.objects.create(category="smtp", key="port", value={"v": 25})

    assert str(setting) == "smtp.port"


@pytest.mark.django_db
def test_non_secret_value_is_displayed():
    setting = PlatformSetting.objects.create(category="ui", key="theme", value={"v": "dark"})

    assert setting.display_value == {"v": "dark"}


@pytest.mark.django_db
def test_secret_value_is_masked_for_display():
    setting = PlatformSetting.objects.create(
        category="smtp", key="password", value={"v": "s3nsitive"}, is_secret=True
    )

    assert setting.display_value == REDACTED
    # The stored value is intact; only the presentation is masked.
    assert setting.value == {"v": "s3nsitive"}


@pytest.mark.django_db
def test_ordering_is_by_category_then_key():
    PlatformSetting.objects.create(category="smtp", key="port", value={})
    PlatformSetting.objects.create(category="ldap", key="host", value={})
    PlatformSetting.objects.create(category="smtp", key="host", value={})

    assert [str(s) for s in PlatformSetting.objects.all()] == [
        "ldap.host",
        "smtp.host",
        "smtp.port",
    ]
