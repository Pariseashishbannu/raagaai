"""Scrape and collect svara sequences from open Carnatic music datasets.

Sources:
  1. Saraga Carnatic Dataset — svara phrase annotations from JSON metadata
  2. karnatik.com — composition notation pages (web scrape)
  3. Local raga data — generate synthetic sequences from arohanam/avarohanam patterns
"""

import json
import logging
import random
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB_DEPS = True
except ImportError:
    HAS_WEB_DEPS = False

logger = logging.getLogger(__name__)

# Canonical svara names used in our tokenizer
CANONICAL_SVARAS = {
    "Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2",
    "Pa", "Da1", "Da2", "Ni1", "Ni2",
}

# Map common notation variants to our canonical form
SVARA_ALIASES: dict[str, str] = {
    "S": "Sa", "s": "Sa", "sa": "Sa", "SA": "Sa",
    "R": "Ri2", "r": "Ri1", "R1": "Ri1", "R2": "Ri2", "R3": "Ga1",
    "ri": "Ri1", "Ri": "Ri2",
    "G": "Ga2", "g": "Ga1", "G1": "Ga1", "G2": "Ga2", "G3": "Ga2",
    "ga": "Ga1", "Ga": "Ga2",
    "M": "Ma1", "m": "Ma1", "M1": "Ma1", "M2": "Ma2",
    "ma": "Ma1", "Ma": "Ma1",
    "P": "Pa", "p": "Pa", "pa": "Pa", "PA": "Pa",
    "D": "Da2", "d": "Da1", "D1": "Da1", "D2": "Da2", "D3": "Ni1",
    "da": "Da1", "Da": "Da2",
    "N": "Ni2", "n": "Ni1", "N1": "Ni1", "N2": "Ni2", "N3": "Ni2",
    "ni": "Ni1", "Ni": "Ni2",
}

# Raga name → raga_id mapping for common ragas found on karnatik.com
COMMON_RAGA_IDS: dict[str, str] = {
    "shankarabharanam": "shankarabharanam",
    "sankarabharanam": "shankarabharanam",
    "kalyani": "kalyani",
    "kharaharapriya": "kharaharapriya",
    "harikambhoji": "harikambhoji",
    "mayamalavagowla": "mayamalavagowla",
    "mayamalavagaula": "mayamalavagowla",
    "todi": "hanumatodi",
    "hanumatodi": "hanumatodi",
    "kambhoji": "kambhoji",
    "bhairavi": "bhairavi",
    "begada": "begada",
    "mohanam": "mohanam",
    "hindolam": "hindolam",
    "abhogi": "abhogi",
    "bilahari": "bilahari",
    "sahana": "sahana",
    "anandabhairavi": "anandabhairavi",
    "kedaragowla": "kedaragowla",
    "saveri": "saveri",
    "arabhi": "arabhi",
    "devagandhari": "devagandhari",
    "sri": "sri",
    "bowli": "bowli",
    "madhyamavati": "madhyamavati",
    "hamsadhwani": "hamsadhwani",
    "revati": "revati",
    "suddha saveri": "sudha_saveri",
    "natabhairavi": "natabhairavi",
}


def normalize_svara(token: str) -> str | None:
    """Convert a svara notation token to canonical form."""
    token = token.strip()
    if token in CANONICAL_SVARAS:
        return token
    if token in SVARA_ALIASES:
        return SVARA_ALIASES[token]
    return None


def parse_notation_string(notation: str) -> list[str]:
    """Parse a notation string like 'S R G M P D N S' into canonical svaras."""
    # Split on whitespace, commas, pipes, hyphens
    raw_tokens = re.split(r"[\s,|;\-]+", notation.strip())
    svaras = []
    for tok in raw_tokens:
        if not tok:
            continue
        svara = normalize_svara(tok)
        if svara:
            svaras.append(svara)
    return svaras


class SaragaScraper:
    """Extract svara phrase annotations from Saraga Carnatic dataset metadata."""

    def scrape(self, saraga_dir: str) -> list[dict]:
        """Parse Saraga dataset JSON annotations for svara phrases.

        Args:
            saraga_dir: Path to extracted Saraga dataset root.

        Returns:
            List of {raga_id, section, svaras} dicts.
        """
        saraga_path = Path(saraga_dir)
        if not saraga_path.exists():
            logger.warning("Saraga directory not found: %s", saraga_dir)
            return []

        sequences = []
        # Saraga stores metadata in various JSON files per recording
        for json_file in saraga_path.rglob("*.json"):
            try:
                sequences.extend(self._parse_saraga_file(json_file))
            except Exception:
                logger.debug("Skipping %s", json_file, exc_info=True)

        logger.info("Extracted %d sequences from Saraga dataset", len(sequences))
        return sequences

    def _parse_saraga_file(self, json_file: Path) -> list[dict]:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        sequences = []

        # Handle svaraNotation or svara_phrases fields
        svara_data = None
        if isinstance(data, dict):
            svara_data = data.get("svaraNotation") or data.get("svara_phrases")
            raga_name = data.get("raaga", data.get("raga", ""))
        elif isinstance(data, list):
            # Some files are lists of phrases
            svara_data = data
            raga_name = json_file.parent.name

        if not svara_data:
            return []

        raga_id = COMMON_RAGA_IDS.get(raga_name.lower().strip(), raga_name.lower().strip())

        if isinstance(svara_data, list):
            for item in svara_data:
                if isinstance(item, str):
                    svaras = parse_notation_string(item)
                elif isinstance(item, dict):
                    notation = item.get("notation", item.get("svaras", ""))
                    svaras = parse_notation_string(str(notation))
                else:
                    continue

                if len(svaras) >= 4:
                    sequences.append({
                        "raga_id": raga_id,
                        "section": "pallavi",
                        "svaras": svaras,
                    })

        return sequences


class KarnatikScraper:
    """Scrape svara notation from karnatik.com composition pages."""

    BASE_URL = "https://www.karnatik.com"
    DELAY = 2.0  # Be respectful with rate limiting

    def scrape(self, max_pages: int = 100) -> list[dict]:
        """Scrape notation from karnatik.com composition index.

        Args:
            max_pages: Maximum number of composition pages to scrape.

        Returns:
            List of {raga_id, section, svaras} dicts.
        """
        if not HAS_WEB_DEPS:
            logger.warning("requests/beautifulsoup4 not installed — skipping web scrape")
            return []

        sequences = []
        try:
            comp_urls = self._get_composition_urls(max_pages)
            for url in comp_urls:
                try:
                    result = self._parse_composition_page(url)
                    sequences.extend(result)
                    time.sleep(self.DELAY)
                except Exception:
                    logger.debug("Failed to parse %s", url, exc_info=True)
        except Exception:
            logger.warning("Failed to scrape karnatik.com", exc_info=True)

        logger.info("Scraped %d sequences from karnatik.com", len(sequences))
        return sequences

    def _get_composition_urls(self, max_pages: int) -> list[str]:
        """Get composition page URLs from the index."""
        urls = []
        # karnatik.com has alphabetical index pages
        for letter in "abcdefghijklmnopqrstuvwxyz":
            if len(urls) >= max_pages:
                break
            index_url = f"{self.BASE_URL}/c{letter}.shtml"
            try:
                resp = requests.get(index_url, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if "comp" in href and href.endswith(".shtml"):
                        full_url = href if href.startswith("http") else f"{self.BASE_URL}/{href}"
                        urls.append(full_url)
                        if len(urls) >= max_pages:
                            break
                time.sleep(self.DELAY)
            except Exception:
                logger.debug("Index page %s failed", index_url, exc_info=True)

        return urls

    def _parse_composition_page(self, url: str) -> list[dict]:
        """Parse a single composition page for notation."""
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()

        # Extract raga name
        raga_match = re.search(r"[Rr]aag(?:a|am)[\s:]+([A-Za-z\s]+)", text)
        raga_name = raga_match.group(1).strip().lower() if raga_match else ""
        raga_id = COMMON_RAGA_IDS.get(raga_name, raga_name.replace(" ", "_"))

        if not raga_id:
            return []

        sequences = []

        # Look for notation sections — lines of svara notation
        section_map = {
            "pallavi": "pallavi",
            "anupallavi": "anupallavi",
            "charanam": "charanam",
            "charana": "charanam",
            "chittaswaram": "chittaswaram",
            "chitta swaram": "chittaswaram",
        }

        current_section = "pallavi"
        # Split text into lines and look for notation
        for line in text.split("\n"):
            line_lower = line.strip().lower()

            # Check for section headers
            for key, sec in section_map.items():
                if key in line_lower and len(line_lower) < 30:
                    current_section = sec
                    break

            # Try to parse as notation
            svaras = parse_notation_string(line)
            if len(svaras) >= 4:
                sequences.append({
                    "raga_id": raga_id,
                    "section": current_section,
                    "svaras": svaras,
                })

        return sequences


class LocalRagaSynthesizer:
    """Generate synthetic training sequences from local raga definitions.

    Uses arohanam/avarohanam patterns and characteristic phrases to create
    plausible svara sequences without any network access.
    """

    def __init__(self, raga_data_dir: str = "data/ragas"):
        self.raga_data_dir = Path(raga_data_dir)

    def synthesize(self, sequences_per_raga: int = 100) -> list[dict]:
        """Generate synthetic svara sequences from raga definitions."""
        ragas = self._load_ragas()
        sequences = []

        for raga_id, raga in ragas.items():
            arohanam = raga.get("arohanam", [])
            avarohanam = raga.get("avarohanam", [])
            phrases = raga.get("characteristic_phrases", [])

            if len(arohanam) < 3:
                continue

            allowed = list(set(arohanam) | set(avarohanam))

            for _ in range(sequences_per_raga):
                section = random.choice(["pallavi", "anupallavi", "charanam", "chittaswaram"])
                length = random.randint(16, 64)
                svaras = self._generate_sequence(
                    arohanam, avarohanam, allowed, phrases, length
                )
                sequences.append({
                    "raga_id": raga_id,
                    "section": section,
                    "svaras": svaras,
                })

        logger.info("Synthesized %d sequences from local raga data", len(sequences))
        return sequences

    def _generate_sequence(
        self,
        arohanam: list[str],
        avarohanam: list[str],
        allowed: list[str],
        phrases: list[list[str]],
        length: int,
    ) -> list[str]:
        """Generate a single sequence using structured random walk."""
        svaras: list[str] = []

        # Start with ascending pattern
        seq_pool = arohanam[:-1]  # Drop trailing Sa
        ava_pool = avarohanam[:-1]

        while len(svaras) < length:
            strategy = random.random()

            if strategy < 0.3 and phrases:
                # Insert a characteristic phrase
                phrase = random.choice(phrases)
                svaras.extend(phrase)
            elif strategy < 0.6:
                # Ascending fragment
                start = random.randint(0, max(0, len(seq_pool) - 3))
                end = min(start + random.randint(3, 6), len(seq_pool))
                svaras.extend(seq_pool[start:end])
            elif strategy < 0.85:
                # Descending fragment
                start = random.randint(0, max(0, len(ava_pool) - 3))
                end = min(start + random.randint(3, 6), len(ava_pool))
                svaras.extend(ava_pool[start:end])
            else:
                # Stepwise oscillation around a note
                center = random.choice(allowed)
                center_idx = allowed.index(center)
                for _ in range(random.randint(2, 4)):
                    offset = random.choice([-1, 0, 1])
                    idx = max(0, min(len(allowed) - 1, center_idx + offset))
                    svaras.append(allowed[idx])

        return svaras[:length]

    def _load_ragas(self) -> dict[str, dict]:
        ragas = {}
        for json_file in self.raga_data_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for rid, rdata in data.items():
                    ragas[rid] = rdata
            elif isinstance(data, list):
                for r in data:
                    ragas[r["id"]] = r
        return ragas


def augment_sequences(sequences: list[dict]) -> list[dict]:
    """Augment training data with transpositions and phrase repetitions.

    Transposition: shift all svaras up/down by N positions in the chromatic scale.
    Repetition: repeat characteristic fragments within a sequence.
    """
    from src.core.constants import ALL_SVARAS

    augmented = list(sequences)  # Keep originals

    for seq in sequences:
        svaras = seq["svaras"]

        # Transpose by shifting svara indices
        for shift in [1, 2, -1, -2]:
            transposed = []
            valid = True
            for s in svaras:
                if s in ALL_SVARAS:
                    idx = ALL_SVARAS.index(s)
                    new_idx = (idx + shift) % len(ALL_SVARAS)
                    transposed.append(ALL_SVARAS[new_idx])
                else:
                    valid = False
                    break
            if valid and len(transposed) >= 4:
                augmented.append({
                    "raga_id": seq["raga_id"],
                    "section": seq["section"],
                    "svaras": transposed,
                })

        # Repeat a random sub-phrase
        if len(svaras) >= 8:
            start = random.randint(0, len(svaras) - 4)
            phrase = svaras[start:start + 4]
            repeated = svaras[:start] + phrase + phrase + svaras[start + 4:]
            augmented.append({
                "raga_id": seq["raga_id"],
                "section": seq["section"],
                "svaras": repeated[:64],  # Cap length
            })

    return augmented
