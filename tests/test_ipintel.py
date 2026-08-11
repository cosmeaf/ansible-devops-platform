"""IP intelligence model and provider abstraction."""

import pytest
from django.db import IntegrityError

from ipintel.models import IPIntelligence
from ipintel.providers import IPLookupResult, LocalProvider, get_provider


@pytest.mark.django_db
def test_ip_record_is_unique_per_address():
    IPIntelligence.objects.create(ip="192.0.2.10")

    with pytest.raises(IntegrityError):
        IPIntelligence.objects.create(ip="192.0.2.10")


@pytest.mark.django_db
def test_ip_record_defaults_are_conservative():
    record = IPIntelligence.objects.create(ip="192.0.2.11")

    assert record.is_private is False
    assert record.trusted is False
    assert record.proxy_signal is False
    assert record.vpn_signal is False


@pytest.mark.django_db
def test_ip_record_str_reports_scope():
    assert str(IPIntelligence.objects.create(ip="10.0.0.5", is_private=True)) == (
        "10.0.0.5 (private)"
    )
    assert str(IPIntelligence.objects.create(ip="8.8.8.8")) == "8.8.8.8 (public)"


@pytest.mark.parametrize(
    "ip", ["10.0.0.1", "192.168.1.1", "172.16.0.1", "127.0.0.1", "169.254.1.1", "::1"]
)
def test_local_provider_detects_private_addresses(ip):
    assert LocalProvider().lookup(ip).is_private is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"])
def test_local_provider_detects_public_addresses(ip):
    assert LocalProvider().lookup(ip).is_private is False


@pytest.mark.parametrize("ip", ["192.0.2.1", "198.51.100.1", "203.0.113.1", "2001:db8::1"])
def test_documentation_ranges_count_as_non_public(ip):
    """RFC 5737/3849 blocks are not globally routable, so they are not public.

    Pinned deliberately: `is_private` answers "could this have reached us from
    the internet?", which is broader than RFC 1918.
    """
    assert LocalProvider().lookup(ip).is_private is True


@pytest.mark.parametrize("ip", ["10.0.0.1", "172.16.5.4", "192.168.1.1", "fd00::1"])
def test_site_local_ranges_are_identified(ip):
    assert LocalProvider().lookup(ip).metadata["site_local"] is True


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.1.1", "203.0.113.1", "8.8.8.8"])
def test_non_site_local_addresses_are_not_mislabelled(ip):
    """Loopback, link-local and documentation blocks are not RFC 1918 space."""
    assert LocalProvider().lookup(ip).metadata["site_local"] is False


def test_loopback_is_flagged_separately():
    assert LocalProvider().lookup("127.0.0.1").metadata["loopback"] is True
    assert LocalProvider().lookup("169.254.1.1").metadata["link_local"] is True


def test_public_address_records_its_network():
    assert LocalProvider().lookup("8.8.8.8").network == "8.8.8.8"
    assert LocalProvider().lookup("10.0.0.1").network == ""


def test_local_provider_invents_no_geolocation():
    """Fabricated geo data would be worse than admitting we do not know."""
    result = LocalProvider().lookup("8.8.8.8")

    assert result.country == ""
    assert result.city == ""
    assert result.asn == ""


def test_local_provider_rejects_invalid_input():
    with pytest.raises(ValueError):
        LocalProvider().lookup("not-an-ip")


def test_local_provider_reports_ip_version():
    assert LocalProvider().lookup("8.8.8.8").metadata["version"] == 4
    assert LocalProvider().lookup("2001:db8::1").metadata["version"] == 6


def test_default_provider_requires_no_external_service():
    provider = get_provider()

    assert provider.name == "local"
    assert isinstance(provider.lookup("8.8.8.8"), IPLookupResult)
