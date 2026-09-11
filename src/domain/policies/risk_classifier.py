"""Command risk classifier assessing risk levels using an extensible pattern dictionary."""
import re
from typing import Dict, List, Optional

from src.domain.value_objects.risk_level import RiskLevel
from src.domain.policies.policy_rules import DEFAULT_BLACKLIST_RULES


# Extensible default dictionary mapping risk categories to regex patterns
DEFAULT_RISK_PATTERNS: Dict[RiskLevel, List[str]] = {
    # HIGH RISK: Active exploitation, payload execution, vulnerability exploitation, credential attacks
    RiskLevel.HIGH: [
        r"\bmsfconsole\b",
        r"\bmsfvenom\b",
        r"\bmetasploit\b",
        r"\bsqlmap\b",
        r"\bhydra\b",
        r"\bmedusa\b",
        r"\bhashcat\b",
        r"\bjohn(?:\s+.*)?\b",
        r"\bcommix\b",
        r"\bexploit(?:db)?\b",
        r"\bafl-fuzz\b",
        r"\bcrackmapexec\b",
        r"\bresponder\b",
        r"\bevil-winrm\b",
        r"\bimpacket-.*\b",
    ],
    # MEDIUM RISK: Active scanning, service version enumeration, directory brute force, web vulnerability discovery
    RiskLevel.MEDIUM: [
        r"\bnmap\s+.*-(?:sV|sC|sS|sT|sU|A|O)\b",
        r"\bnmap\s+.*-p-(?:\s|$)",
        r"\bnmap\s+.*-p\s*[0-9]+",
        r"\bnmap\s+.*--script",
        r"\bgobuster\b",
        r"\bdirb\b",
        r"\bdirsearch\b",
        r"\bferoxbuster\b",
        r"\bnikto\b",
        r"\bwpscan\b",
        r"\bwhatweb\b",
        r"\btheHarvester\b",
        r"\bmasscan\b",
        r"\bzmap\b",
        r"\bsslscan\b",
        r"\barp-scan\b",
    ],
    # LOW RISK: Passive reconnaissance, non-intrusive DNS / whois lookups, host reachability checks
    RiskLevel.LOW: [
        r"\bwhois\b",
        r"\bdig\b",
        r"\bnslookup\b",
        r"\bhost\b",
        r"\bdnsrecon\b",
        r"\bnmap\s+.*-sn\b",  # Ping sweep / host discovery only, no port inspection
        r"\bping(?:\s+-[a-zA-Z0-9]+)*\s+[0-9a-zA-Z\.\-_]+",
        r"\btraceroute\b",
        r"\btracepath\b",
        r"\bcurl\b",
        r"\bwget\b",
        r"\buname\b",
        r"\bid\b",
        r"\bwhoami\b",
        r"\bls\b",
        r"\bpwd\b",
        r"\bcat\b",
    ],
}


class CommandRiskClassifier:
    """Classifies candidate commands into domain RiskLevel categories
    using an extensible dictionary of compiled regex patterns rather than if/elif chains.

    Attributes:
        _patterns (Dict[RiskLevel, List[re.Pattern]]): Compiled regex patterns by risk level.
    """

    def __init__(self, custom_patterns: Optional[Dict[RiskLevel, List[str]]] = None) -> None:
        """Initializes the risk classifier with default or customized pattern sets.

        Args:
            custom_patterns (Optional[Dict[RiskLevel, List[str]]]): Optional override or extension.
        """
        raw_patterns = custom_patterns or DEFAULT_RISK_PATTERNS
        self._patterns: Dict[RiskLevel, List[re.Pattern]] = {}

        for level, pattern_list in raw_patterns.items():
            self._patterns[level] = [
                re.compile(p, re.IGNORECASE) for p in pattern_list
            ]

    def register_pattern(self, risk_level: RiskLevel, pattern: str) -> None:
        """Dynamically registers an additional pattern to a given risk level without modifying code.

        Args:
            risk_level (RiskLevel): Target risk category.
            pattern (str): Regular expression pattern to add.
        """
        compiled = re.compile(pattern, re.IGNORECASE)
        if risk_level not in self._patterns:
            self._patterns[risk_level] = []
        self._patterns[risk_level].append(compiled)

    def classify(self, command_text: str) -> RiskLevel:
        """Evaluates a raw command string and returns its highest matching RiskLevel.

        Hierarchy:
        1. Check blacklist destructive commands -> BLOCKED
        2. Check HIGH patterns (exploitation, credentials)
        3. Check MEDIUM patterns (active scanning, fuzzing)
        4. Check LOW patterns (passive recon, ping sweep)
        5. Fallback -> LOW

        Args:
            command_text (str): Raw shell command text to evaluate.

        Returns:
            RiskLevel: Assessed risk classification.
        """
        clean_text = command_text.strip()
        if not clean_text:
            return RiskLevel.LOW

        # 1. First verify if it matches destructive blacklist rules
        for rule in DEFAULT_BLACKLIST_RULES:
            if rule.matches(clean_text):
                return RiskLevel.BLOCKED

        # 2. Check risk levels in strictly descending order of severity
        evaluation_order = [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]

        for level in evaluation_order:
            patterns = self._patterns.get(level, [])
            for pattern in patterns:
                if pattern.search(clean_text):
                    return level

        # Default fallback for unclassified non-destructive commands
        return RiskLevel.LOW


# Singleton instance for convenience
default_risk_classifier = CommandRiskClassifier()


def classify_command_risk(command_text: str) -> RiskLevel:
    """Convenience helper classifying a command text using the default classifier instance.

    Args:
        command_text (str): Raw shell command text.

    Returns:
        RiskLevel: Evaluated risk level.
    """
    return default_risk_classifier.classify(command_text)
