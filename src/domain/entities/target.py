"""Domain entity representing an authorized target for ethical security testing."""
from dataclasses import dataclass
import ipaddress
from typing import Optional, Union


@dataclass(frozen=True)
class Target:
    """Represents an authorized practice target, such as a single IP, CIDR subnet, or domain.

    Attributes:
        value (str): The authorized target representation (e.g., '192.168.1.5',
            '10.10.10.0/24', or 'hackthebox.com').
        description (Optional[str]): Optional human-readable description or lab name.
    """

    value: str
    description: Optional[str] = None

    def contains(self, ip_or_domain: str) -> bool:
        """Determines whether a given IP address or domain falls within this authorized target.

        Uses Python's standard ipaddress module for network range calculations.

        Args:
            ip_or_domain (str): IP address or domain string to validate.

        Returns:
            bool: True if the candidate is within the scope of this target, False otherwise.
        """
        candidate = ip_or_domain.strip().lower()
        target_val = self.value.strip().lower()

        # Direct string equality check
        if candidate == target_val:
            return True

        # Try evaluating as IP networks / addresses
        try:
            candidate_ip = ipaddress.ip_address(candidate)

            # Determine whether target is an IP network (CIDR) or single IP
            target_network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
            try:
                # strict=False allows passing host addresses with CIDR masks like 192.168.1.1/24
                target_network = ipaddress.ip_network(target_val, strict=False)
            except ValueError:
                target_ip = ipaddress.ip_address(target_val)
                target_network = ipaddress.ip_network(target_ip)

            return candidate_ip in target_network
        except ValueError:
            # Candidate or target is not a valid IP; treat as domain evaluation
            pass

        # Domain hierarchy matching: check if candidate is a subdomain of target
        if candidate.endswith(f".{target_val}"):
            return True

        return False
