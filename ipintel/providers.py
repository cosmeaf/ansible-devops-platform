"""IP intelligence provider abstraction.

The platform must stay usable with no external subscription, so the default
provider resolves everything locally from the address itself. Commercial or
self-hosted lookups plug in behind the same interface without any caller
change — see docs/adr/0009-ipintel-provider-abstraction.md.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class IPLookupResult:
    """Normalised provider output, independent of any vendor payload shape."""

    ip: str
    is_private: bool
    country: str = ""
    city: str = ""
    asn: str = ""
    network: str = ""
    proxy_signal: bool = False
    vpn_signal: bool = False
    provider: str = ""
    metadata: dict = field(default_factory=dict)


#: RFC 1918 (IPv4) and RFC 4193 (IPv6 unique local) ranges. Python's
#: ``ip_address.is_private`` is deliberately broader than this — it also covers
#: loopback, link-local and the documentation blocks — so a genuine
#: "site-local address space" check needs the ranges spelled out.
_SITE_LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def is_site_local(address) -> bool:
    """Return ``True`` for RFC 1918 / RFC 4193 address space."""
    return any(
        address in network for network in _SITE_LOCAL_NETWORKS if network.version == address.version
    )


class IPIntelProvider(Protocol):
    """Interface every intelligence source must satisfy."""

    name: str

    def lookup(self, ip: str) -> IPLookupResult: ...


class LocalProvider:
    """Offline classifier: scope derived from the address itself.

    ``is_private`` here means **not globally routable**, which is the question
    the platform actually cares about when deciding whether an address could
    have reached us from the public internet. That is broader than RFC 1918:
    loopback, link-local, reserved, multicast and the RFC 5737 documentation
    ranges are all non-global and are reported as private.

    Returns no geolocation, because inventing one would be worse than
    admitting we do not know.
    """

    name = "local"

    def lookup(self, ip: str) -> IPLookupResult:
        address = ipaddress.ip_address(ip)
        is_private = not address.is_global
        return IPLookupResult(
            ip=str(address),
            is_private=is_private,
            network="" if is_private else str(address),
            provider=self.name,
            metadata={
                "version": address.version,
                "loopback": address.is_loopback,
                "link_local": address.is_link_local,
                "site_local": is_site_local(address),
            },
        )


def get_provider() -> IPIntelProvider:
    """Return the configured provider.

    Only the local provider ships today; the lookup stays behind this function
    so adding a provider never means touching call sites.
    """
    return LocalProvider()
