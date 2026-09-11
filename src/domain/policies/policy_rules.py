"""Security policy rules, destructive command blacklist patterns, and target authorization validation."""
from typing import List, Optional

from src.domain.entities.policy_rule import PolicyRule
from src.domain.entities.session import Session
from src.domain.value_objects.policy_action import PolicyAction
from src.domain.value_objects.risk_level import RiskLevel


# ============================================================================
# Blacklist Regular Expression Patterns
# Documented with exact real-world commands blocked and threat rationale.
# ============================================================================

# 1. Mass file deletion patterns
# Blocks: 'rm -rf /', 'rm -r -f /', 'rm -rf /*', 'rm --no-preserve-root', 'rm -rf /etc', 'rm -rf /var'
# Rationale: Indiscriminate recursive mass deletion annihilates the Linux root filesystem or core operating directories.
PATTERN_MASS_DELETION = (
    r"\brm\s+.*(?:-[a-zA-Z0-9]*[rR][a-zA-Z0-9]*\s+.*-[a-zA-Z0-9]*[fF]|-[a-zA-Z0-9]*[fF][a-zA-Z0-9]*\s+.*-[a-zA-Z0-9]*[rR]|-[a-zA-Z0-9]*[rR][a-zA-Z0-9]*[fF]|-[a-zA-Z0-9]*[fF][a-zA-Z0-9]*[rR])"
    r".*(?:\s+/|\s+/\*|\s+\.\.|\s+~\b|\s+/etc|\s+/var|\s+/usr|\s+/bin|\s+/boot)"
    r"|--no-preserve-root"
)

# 2. Disk and filesystem formatting commands
# Blocks: 'mkfs.ext4 /dev/sda1', 'mkfs.xfs /dev/nvme0n1p1', 'mkfs -t vfat /dev/sdb', 'mke2fs /dev/sda'
# Rationale: Recreating filesystems destroys all partitions and stored lab data without confirmation.
PATTERN_DISK_FORMATTING = (
    r"\bmkfs(?:\.[a-zA-Z0-9]+)?\s+|(?:^|\s)mke2fs\s+"
)

# 3. Partition table manipulation and raw block device overwriting
# Blocks: 'fdisk /dev/sda', 'parted /dev/sda mklabel gpt', 'gdisk', 'sfdisk',
#         'dd if=/dev/zero of=/dev/sda', 'dd if=/dev/urandom of=/dev/nvme0n1',
#         and stdout redirection to devices like '> /dev/sda'
# Rationale: Raw partition edits or writing bytes directly into block devices ruins filesystem structures and MBR/GPT tables.
PATTERN_PARTITION_AND_RAW_WRITES = (
    r"\b(?:fdisk|gdisk|parted|sfdisk)\b"
    r"|\bdd\s+.*of=/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|vd[a-z]|loop[0-9])"
    r"|>\s*/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|vd[a-z])"
)

# 4. System shutdown, reboot, and power state termination
# Blocks: 'shutdown -h now', 'shutdown -r 0', 'reboot', 'poweroff', 'init 0', 'init 6', 'halt'
# Rationale: Halting or rebooting the operating system abruptly kills active user and background processes.
PATTERN_SYSTEM_SHUTDOWN = (
    r"\b(?:shutdown\s+-[a-zA-Z0-9]+|shutdown\s+now|reboot(?:\s+-[a-zA-Z0-9]+)?|poweroff|halt|init\s+[06])\b"
)

# 5. Host firewall flushing and tampering
# Blocks: 'iptables -F', 'iptables --flush', 'ip6tables -F', 'ufw disable', 'ufw reset', 'nft flush ruleset'
# Rationale: Flushing or disabling the firewall strips active network defenses, exposing WSL2 or host ports unexpectedly.
PATTERN_HOST_FIREWALL_TAMPERING = (
    r"\biptables\s+(?:-[a-zA-Z0-9]*[Ff]|--flush)"
    r"|\bip6tables\s+(?:-[a-zA-Z0-9]*[Ff]|--flush)"
    r"|\bufw\s+(?:disable|reset)\b"
    r"|\bnft\s+flush\s+ruleset\b"
)


# ============================================================================
# Default Blacklist Policy Rules
# ============================================================================

DEFAULT_BLACKLIST_RULES: List[PolicyRule] = [
    PolicyRule(
        id="block-mass-deletion",
        pattern=PATTERN_MASS_DELETION,
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Blocks recursive mass deletion of root filesystem or critical operating system directories.",
    ),
    PolicyRule(
        id="block-disk-formatting",
        pattern=PATTERN_DISK_FORMATTING,
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Blocks filesystem creation and disk formatting tools (mkfs, mke2fs).",
    ),
    PolicyRule(
        id="block-partition-and-raw-writes",
        pattern=PATTERN_PARTITION_AND_RAW_WRITES,
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Blocks partition modification tools (fdisk, parted) and raw device byte overwrites (dd of=/dev/sd*).",
    ),
    PolicyRule(
        id="block-system-shutdown",
        pattern=PATTERN_SYSTEM_SHUTDOWN,
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Blocks system halt, shutdown, poweroff, and reboot commands.",
    ),
    PolicyRule(
        id="block-firewall-tampering",
        pattern=PATTERN_HOST_FIREWALL_TAMPERING,
        risk_level=RiskLevel.BLOCKED,
        action=PolicyAction.BLOCK,
        description="Blocks flushing or disabling host firewalls (iptables -F, ufw disable, nft flush ruleset).",
    ),
]


# ============================================================================
# Target Authorization Scope Validation
# ============================================================================

def is_target_authorized(target: str, session: Session) -> bool:
    """Validates whether a target IP address, subnet CIDR, or domain name is explicitly
    authorized within the given session's authorized targets list.

    Zero implicit trust: returns False if target is empty or session has no authorized targets.

    Args:
        target (str): The candidate IP address, CIDR range, or domain string.
        session (Session): The active session containing authorized targets.

    Returns:
        bool: True if candidate is authorized, False otherwise.
    """
    if not target or not target.strip():
        return False

    candidate = target.strip()

    if not session.authorized_targets:
        return False

    for authorized in session.authorized_targets:
        if authorized.contains(candidate):
            return True

    return False
