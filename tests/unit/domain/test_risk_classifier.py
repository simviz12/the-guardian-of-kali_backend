"""Unit tests for the extensible command risk classifier."""

import pytest

from src.domain.policies.risk_classifier import (
    CommandRiskClassifier,
    classify_command_risk,
)
from src.domain.value_objects.risk_level import RiskLevel


@pytest.fixture
def classifier() -> CommandRiskClassifier:
    """Provides a default CommandRiskClassifier instance."""
    return CommandRiskClassifier()


# ============================================================================
# LOW Risk Tests: Passive Recon, DNS, Host Discovery
# ============================================================================


@pytest.mark.parametrize(
    "cmd",
    [
        "whois example.com",
        "dig +short A target.thm",
        "nslookup -type=mx 10.10.10.5",
        "host -t ns domain.htb",
        "dnsrecon -d domain.com",
        "nmap -sn 10.10.10.0/24",
        "nmap -sn 192.168.1.1",
        "ping -c 4 10.10.10.1",
        "traceroute 10.10.10.1",
        "tracepath 8.8.8.8",
        "curl -I http://10.10.10.20",
        "whoami",
        "id",
        "pwd",
        "ls -la",
    ],
)
def test_classify_low_risk_commands(classifier: CommandRiskClassifier, cmd: str) -> None:
    """Verifies that passive reconnaissance and benign inspection commands evaluate to LOW."""
    assert classifier.classify(cmd) == RiskLevel.LOW
    assert classify_command_risk(cmd) == RiskLevel.LOW


# ============================================================================
# MEDIUM Risk Tests: Active Scanning, Service Enumeration, Web Fuzzing
# ============================================================================


@pytest.mark.parametrize(
    "cmd",
    [
        "nmap -sV 10.10.10.15",
        "nmap -A -T4 10.10.10.20",
        "nmap -sC -sV -p 80,443,8080 10.10.10.30",
        "nmap -O 10.10.10.5",
        "nmap -p- --min-rate 1000 10.10.10.1",
        "nmap --script vuln 10.10.10.1",
        "gobuster dir -u http://10.10.10.15 -w /usr/share/wordlists/dirb/common.txt",
        "dirb http://10.10.10.20",
        "dirsearch -u http://10.10.10.20",
        "feroxbuster -u http://10.10.10.25",
        "nikto -h http://10.10.10.15",
        "wpscan --url http://target.blog --enumerate u",
        "whatweb 10.10.10.5",
        "theHarvester -d company.com -b google",
        "masscan -p1-65535 10.10.10.0/24 --rate=1000",
        "sslscan 10.10.10.15:443",
    ],
)
def test_classify_medium_risk_commands(classifier: CommandRiskClassifier, cmd: str) -> None:
    """Verifies that active scanning, service enumeration, and web fuzzing evaluate to MEDIUM."""
    assert classifier.classify(cmd) == RiskLevel.MEDIUM


# ============================================================================
# HIGH Risk Tests: Active Exploitation, Credential Attacks, Password Cracking
# ============================================================================


@pytest.mark.parametrize(
    "cmd",
    [
        "msfconsole -q -x 'use exploit/multi/handler'",
        "msfvenom -p linux/x64/shell_reverse_tcp LHOST=10.10.14.2 LPORT=4444 -f elf > shell.elf",
        "sqlmap -u 'http://10.10.10.20/vuln.php?id=1' --batch --dbs",
        "hydra -l admin -P /usr/share/wordlists/rockyou.txt 10.10.10.15 ssh",
        "medusa -h 10.10.10.15 -u admin -P pass.txt -M ftp",
        "hashcat -m 0 -a 0 hashes.txt /usr/share/wordlists/rockyou.txt",
        "john --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt",
        "commix --url='http://10.10.10.20/cmd.php?addr=127.0.0.1'",
        "crackmapexec smb 10.10.10.0/24 -u user -p pass",
        "responder -I eth0 -dwv",
        "evil-winrm -i 10.10.10.50 -u Administrator -p 'Password123!'",
    ],
)
def test_classify_high_risk_commands(classifier: CommandRiskClassifier, cmd: str) -> None:
    """Verifies that active exploitation, password cracking, and credential attacks evaluate to HIGH."""
    assert classifier.classify(cmd) == RiskLevel.HIGH


# ============================================================================
# BLOCKED Risk Tests: Blacklisted Destructive Commands
# ============================================================================


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "iptables -F",
    ],
)
def test_classify_blocked_destructive_commands(classifier: CommandRiskClassifier, cmd: str) -> None:
    """Verifies that destructive blacklist commands evaluate to BLOCKED with absolute precedence."""
    assert classifier.classify(cmd) == RiskLevel.BLOCKED


# ============================================================================
# Extensibility Tests: Dynamically Registering New Patterns
# ============================================================================


def test_dynamic_pattern_registration() -> None:
    """Verifies that custom security tools can be dynamically registered without code modification."""
    custom_classifier = CommandRiskClassifier()

    # Proprietary or newly introduced tool
    proprietary_tool_cmd = "zeroday_scanner --target 10.10.10.5"

    # Default unrecognized tool falls back to LOW
    assert custom_classifier.classify(proprietary_tool_cmd) == RiskLevel.LOW

    # Dynamically register as HIGH risk
    custom_classifier.register_pattern(RiskLevel.HIGH, r"\bzeroday_scanner\b")

    # Re-evaluate
    assert custom_classifier.classify(proprietary_tool_cmd) == RiskLevel.HIGH
