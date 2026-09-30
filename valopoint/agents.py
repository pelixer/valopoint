"""Agent -> role mapping. Stats are standardized within role so that duelists are
not favoured over controllers/sentinels just because their job produces more kills."""
from __future__ import annotations

ROLES = {
    "duelist": ["jett", "raze", "reyna", "phoenix", "yoru", "neon", "iso", "waylay"],
    "initiator": ["sova", "breach", "skye", "kayo", "kay/o", "fade", "gekko", "tejo"],
    "controller": ["brimstone", "viper", "omen", "astra", "harbor", "clove"],
    "sentinel": ["killjoy", "cypher", "sage", "chamber", "deadlock", "vyse", "veto"],
}
AGENT_ROLE = {a: r for r, lst in ROLES.items() for a in lst}


def role_of(agent: str) -> str:
    return AGENT_ROLE.get((agent or "").strip().lower(), "flex")
