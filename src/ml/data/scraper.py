"""Scrape and collect svara sequences from open Carnatic music datasets.

Sources:
  1. Saraga Carnatic Dataset — svara phrase annotations from JSON metadata
  2. karnatik.com — composition notation pages (web scrape)
  3. shivkumar.org — Carnatic krithi notation pages (web scrape)
  4. CompMusic Dunya API — pitch contours + raga labels (needs free API token)
  5. Local raga data — generate synthetic sequences from arohanam/avarohanam patterns
"""

import json
import logging
import math
import random
import re
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

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


PITCH_CLASS_TO_SVARA = {
    0: "Sa", 1: "Ri1", 2: "Ri2", 3: "Ga2", 4: "Ga2", 5: "Ma1",
    6: "Ma2", 7: "Pa", 8: "Da1", 9: "Da2", 10: "Ni1", 11: "Ni2",
}


def _polite_get(session, url: str, timeout: int = 15):
    """GET with a real UA header. Caller handles errors."""
    headers = {"User-Agent": "RaagaAI-DataCollector/0.1 (research; contact via repo)"}
    return session.get(url, timeout=timeout, headers=headers)


def _robots_allows(base: str, path: str = "/") -> bool:
    """Check robots.txt for the User-Agent. Fail-open on network error."""
    try:
        rp = robotparser.RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        rp.read()
        return rp.can_fetch("RaagaAI-DataCollector", urljoin(base, path))
    except Exception:
        return True


class ShivkumarScraper:
    """Scrape Carnatic krithi notations from shivkumar.org/music/."""

    BASE_URL = "https://www.shivkumar.org/music/"
    DELAY = 2.0

    def scrape(self, max_pages: int = 100) -> list[dict]:
        if not HAS_WEB_DEPS:
            logger.warning("requests/beautifulsoup4 missing — skipping shivkumar.org")
            return []
        if not _robots_allows(self.BASE_URL):
            logger.warning("robots.txt disallows scraping shivkumar.org — skipping")
            return []

        sequences: list[dict] = []
        try:
            session = requests.Session()
            urls = self._discover_pages(session, max_pages)
            logger.info("Found %d candidate pages on shivkumar.org", len(urls))
            for url in urls[:max_pages]:
                try:
                    sequences.extend(self._parse_page(session, url))
                    time.sleep(self.DELAY)
                except Exception:
                    logger.debug("Failed page %s", url, exc_info=True)
        except Exception:
            logger.warning("shivkumar.org scrape failed", exc_info=True)

        logger.info("Scraped %d sequences from shivkumar.org", len(sequences))
        return sequences

    SKIP_EXT = (".mp3", ".pdf", ".doc", ".docx", ".ram", ".jpg", ".jpeg",
                ".png", ".gif", ".zip", ".mid", ".midi")

    def _discover_pages(self, session, limit: int) -> list[str]:
        """2-level crawl: start at /music/, follow sub-index pages, collect krithi pages."""
        host = urlparse(self.BASE_URL).netloc
        seen_indices: set[str] = set()
        notation_pages: list[str] = []
        notation_seen: set[str] = set()
        to_visit: list[str] = [self.BASE_URL]
        cap = limit * 3

        for _ in range(2):  # 2 levels deep
            next_visit: list[str] = []
            for url in to_visit:
                if url in seen_indices:
                    continue
                seen_indices.add(url)
                try:
                    resp = _polite_get(session, url)
                    resp.raise_for_status()
                except Exception:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = urljoin(url, link["href"])
                    href, _ = urldefrag(href)
                    low = href.lower()
                    if urlparse(href).netloc != host:
                        continue
                    if low.endswith(self.SKIP_EXT):
                        continue
                    if not low.endswith((".htm", ".html")):
                        continue
                    if "/music/" not in low:
                        continue
                    if "index.htm" in low or "index.html" in low:
                        if href not in seen_indices:
                            next_visit.append(href)
                    elif href not in notation_seen:
                        notation_seen.add(href)
                        notation_pages.append(href)
                        if len(notation_pages) >= cap:
                            return notation_pages
                time.sleep(self.DELAY)
            to_visit = next_visit
        return notation_pages

    def _parse_page(self, session, url: str) -> list[dict]:
        resp = _polite_get(session, url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text("\n")

        # Match Raga, Ragam, Raaga, Raagam (with or without trailing 'm', single or double 'a')
        raga_match = re.search(
            r"[Rr]aa?gam?\s*[:\-]\s*([A-Za-z][A-Za-z\s]{2,30})", text
        )
        raga_name = raga_match.group(1).strip().lower() if raga_match else ""
        # Strip trailing punctuation/braces and stray words
        raga_name = re.split(r"[\s{(\[]", raga_name, maxsplit=1)[0].strip()

        # Fallback: shivkumar URLs often encode raga as the last hyphen-segment of the filename,
        # e.g. adigi-sukhamu-madhyamavathi.htm → "madhyamavathi"
        if not raga_name:
            stem = Path(urlparse(url).path).stem
            parts = [p for p in re.split(r"[-_]", stem) if p]
            if parts:
                raga_name = parts[-1].lower()

        raga_id = COMMON_RAGA_IDS.get(raga_name, raga_name if raga_name else "")
        if not raga_id:
            return []

        section_map = {
            "pallavi": "pallavi", "anupallavi": "anupallavi",
            "charanam": "charanam", "charana": "charanam",
            "chittaswaram": "chittaswaram", "chitta swaram": "chittaswaram",
        }
        current_section = "pallavi"
        sequences: list[dict] = []
        for line in text.split("\n"):
            low = line.strip().lower()
            for key, sec in section_map.items():
                if key in low and len(low) < 30:
                    current_section = sec
                    break
            svaras = parse_notation_string(line)
            if len(svaras) >= 4:
                sequences.append({
                    "raga_id": raga_id,
                    "section": current_section,
                    "svaras": svaras,
                })
        return sequences


class DunyaFetcher:
    """Fetch pitch contours + raga labels from CompMusic Dunya Carnatic collection.

    Requires a free API token from https://dunya.compmusic.upf.edu/user/profile/.
    Pass it via the DUNYA_TOKEN env var or the constructor.
    """

    BASE = "https://dunya.compmusic.upf.edu/api/carnatic"
    DELAY = 1.0

    def __init__(self, token: str):
        self.token = token

    def fetch(self, max_recordings: int = 100, segment_len: int = 32) -> list[dict]:
        if not HAS_WEB_DEPS:
            logger.warning("requests not installed — skipping Dunya")
            return []
        if not self.token:
            logger.warning("No Dunya token — skipping")
            return []

        session = requests.Session()
        session.headers.update({
            "Authorization": f"Token {self.token}",
            "User-Agent": "RaagaAI-DataCollector/0.1",
        })

        sequences: list[dict] = []
        try:
            recordings = self._list_recordings(session, max_recordings)
            logger.info("Dunya: %d recordings", len(recordings))
            for rec in recordings:
                try:
                    seqs = self._process_recording(session, rec, segment_len)
                    sequences.extend(seqs)
                    time.sleep(self.DELAY)
                except Exception:
                    logger.debug("Dunya recording %s failed", rec.get("mbid"), exc_info=True)
        except Exception:
            logger.warning("Dunya fetch failed", exc_info=True)

        logger.info("Dunya: %d svara sequences extracted", len(sequences))
        return sequences

    def _list_recordings(self, session, limit: int) -> list[dict]:
        url = f"{self.BASE}/recording"
        out: list[dict] = []
        while url and len(out) < limit:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            out.extend(data.get("results", []))
            url = data.get("next")
            time.sleep(self.DELAY)
        return out[:limit]

    def _process_recording(self, session, rec: dict, segment_len: int) -> list[dict]:
        mbid = rec.get("mbid")
        if not mbid:
            return []
        meta_resp = session.get(f"{self.BASE}/recording/{mbid}", timeout=30)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        raagas = meta.get("raaga", []) or meta.get("raagas", [])
        if not raagas:
            return []
        raga_name = (raagas[0].get("name") or "").lower().strip()
        raga_id = COMMON_RAGA_IDS.get(raga_name, raga_name.replace(" ", "_"))
        if not raga_id:
            return []

        tonic_resp = session.get(f"{self.BASE}/recording/{mbid}/tonic", timeout=30)
        if tonic_resp.status_code != 200:
            return []
        tonic_hz = float(tonic_resp.json())

        pitch_resp = session.get(f"{self.BASE}/recording/{mbid}/pitch", timeout=60)
        if pitch_resp.status_code != 200:
            return []
        pitch_data = pitch_resp.json()
        pitches = [p[1] for p in pitch_data if isinstance(p, list) and len(p) >= 2]

        svaras = self._pitches_to_svaras(pitches, tonic_hz)
        if len(svaras) < segment_len:
            return []

        return [
            {"raga_id": raga_id, "section": "pallavi", "svaras": svaras[i:i + segment_len]}
            for i in range(0, len(svaras) - segment_len + 1, segment_len)
        ]

    @staticmethod
    def _pitches_to_svaras(pitches: list[float], tonic_hz: float) -> list[str]:
        if tonic_hz <= 0:
            return []
        out: list[str] = []
        last_svara: str | None = None
        for hz in pitches:
            if hz <= 0:
                continue
            cents = 1200.0 * math.log2(hz / tonic_hz)
            pc = int(round(cents / 100.0)) % 12
            svara = PITCH_CLASS_TO_SVARA[pc]
            if svara != last_svara:
                out.append(svara)
                last_svara = svara
        return out


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


try:
    import yt_dlp  # type: ignore
    import librosa  # type: ignore
    import numpy as np  # type: ignore
    HAS_YT_DEPS = True
except ImportError:
    HAS_YT_DEPS = False


# Raga name patterns to search for in video titles / descriptions
_RAGA_TITLE_PATTERNS: list[tuple[str, str]] = [
    (r"\bshankar[a]?bharanam\b", "shankarabharanam"),
    (r"\bkalyani\b", "kalyani"),
    (r"\bkharaharapriya\b", "kharaharapriya"),
    (r"\bharikhambhoji\b|\bharikambhoji\b", "harikambhoji"),
    (r"\bmayamalavagowla\b|\bmayamalavagaula\b", "mayamalavagowla"),
    (r"\bhanumatodi\b|\btodi\b", "hanumatodi"),
    (r"\bkambhoji\b", "kambhoji"),
    (r"\bbhairavi\b", "bhairavi"),
    (r"\bmohanam\b", "mohanam"),
    (r"\bhindolam\b", "hindolam"),
    (r"\babhogi\b", "abhogi"),
    (r"\bbilahari\b", "bilahari"),
    (r"\bsahana\b", "sahana"),
    (r"\banandabhairavi\b", "anandabhairavi"),
    (r"\bkedaragowla\b", "kedaragowla"),
    (r"\bsaveri\b", "saveri"),
    (r"\barabhi\b", "arabhi"),
    (r"\bdevagandhari\b", "devagandhari"),
    (r"\bmadhyamavati\b|\bmadhyamavathi\b", "madhyamavati"),
    (r"\bhamsadhwani\b|\bhamsadhvani\b", "hamsadhwani"),
    (r"\bnatabhairavi\b", "natabhairavi"),
    (r"\bbegada\b", "begada"),
    (r"\bsri\b", "sri"),
    (r"\brevati\b", "revati"),
]


def _detect_raga_from_text(text: str) -> str | None:
    """Best-effort raga detection from a video title or description."""
    text_lower = text.lower()
    for pattern, raga_id in _RAGA_TITLE_PATTERNS:
        if re.search(pattern, text_lower):
            return raga_id
    # Fall back to COMMON_RAGA_IDS word match
    for name, raga_id in COMMON_RAGA_IDS.items():
        if name in text_lower:
            return raga_id
    return None


def _estimate_tonic_hz(pitches_hz: list[float]) -> float:
    """Estimate tonic (Sa) from a pitch contour using histogram of pitch classes.

    Strategy: the tonic is typically the most sustained note in a Carnatic piece.
    We find the pitch class with the highest total duration and then pick the Hz
    value at the median of all frames assigned to that class.
    """
    voiced = [p for p in pitches_hz if p > 60]
    if len(voiced) < 50:
        return 0.0

    import numpy as np  # noqa: PLC0415

    hz_arr = np.array(voiced, dtype=np.float64)
    # Map each Hz to a pitch class (0-11) relative to 440 Hz reference
    semitones = 12.0 * np.log2(hz_arr / 440.0)
    pitch_classes = np.round(semitones).astype(int) % 12

    # Find pitch class with most occurrences
    counts = np.bincount(pitch_classes % 12, minlength=12)
    dominant_pc = int(counts.argmax())

    # Collect all Hz values in that pitch class and return their median
    mask = pitch_classes % 12 == dominant_pc
    return float(np.median(hz_arr[mask]))


class YouTubeScraper:
    """Extract Carnatic svara sequences from Creative Commons licensed YouTube videos.

    Pipeline:
      1. Search YouTube for Carnatic classical music (configurable queries)
      2. Skip any video whose license field is not Creative Commons
      3. Download the audio track only (no video) via yt-dlp
      4. Extract pitch contour with librosa.pyin (probabilistic YIN)
      5. Estimate the tonic frequency (Sa) from the pitch histogram
      6. Convert pitch contour to canonical svara sequences in 30-second windows
      7. Detect the raga from the video title / description

    Only Creative Commons licensed content is processed — this is enforced by
    inspecting the 'license' field returned by yt-dlp, not just assumed.

    Requirements (installed automatically in the notebook):
        yt-dlp >= 2024.1.1
        librosa >= 0.10
        numpy

    Important:
        Downloading copyrighted YouTube content violates YouTube's Terms of Service
        and copyright law. This scraper is restricted to Creative Commons licensed
        videos (filter: license contains 'Creative Commons').
        Do NOT modify cc_only=True to False for bulk copyrighted content.
    """

    DELAY = 4.0  # seconds between downloads — be respectful

    # Queries tuned for Carnatic classical music (NOT Telugu film songs)
    DEFAULT_QUERIES: list[str] = [
        "carnatic classical music raga concert",
        "veena carnatic classical concert",
        "carnatic vocal concert full",
        "carnatic flute concert",
        "carnatic violin concert",
        "pallavi anupallavi carnatic",
        "carnatic instrumental classical",
        "karnatic music concert live",
    ]

    def __init__(self, output_dir: str = "/tmp/raagaai_yt"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def scrape(
        self,
        max_videos: int = 30,
        segment_secs: int = 30,
        queries: list[str] | None = None,
    ) -> list[dict]:
        """Scrape CC-licensed Carnatic YouTube videos and return svara sequences.

        Args:
            max_videos: Maximum number of videos to download and process.
            segment_secs: Seconds per extracted segment (shorter = more sequences).
            queries: Override default search queries.

        Returns:
            List of {raga_id, section, svaras} dicts.
        """
        if not HAS_YT_DEPS:
            logger.warning(
                "yt-dlp / librosa not installed — skipping YouTube scraper. "
                "Run: pip install yt-dlp librosa"
            )
            return []

        queries = queries or self.DEFAULT_QUERIES
        sequences: list[dict] = []
        seen_ids: set[str] = set()

        for query in queries:
            if len(seen_ids) >= max_videos:
                break
            try:
                video_metas = self._search(query, limit=max_videos - len(seen_ids))
            except Exception:
                logger.debug("YouTube search failed for %r", query, exc_info=True)
                continue

            for meta in video_metas:
                if len(seen_ids) >= max_videos:
                    break
                vid_id = meta.get("id") or meta.get("webpage_url", "")
                if vid_id in seen_ids:
                    continue

                # ── CC licence gate — no CC = skip immediately ────────────
                license_str = (meta.get("license") or "").lower()
                if "creative commons" not in license_str:
                    logger.debug("Skipping %s — not CC licensed (%r)", vid_id, license_str)
                    continue

                seen_ids.add(vid_id)
                title = meta.get("title", "")
                description = meta.get("description", "") or ""
                raga_id = _detect_raga_from_text(title + " " + description)

                try:
                    audio_path = self._download_audio(meta["webpage_url"], vid_id)
                    seqs = self._audio_to_sequences(audio_path, raga_id, segment_secs)
                    sequences.extend(seqs)
                    logger.info(
                        "YouTube: %s  raga=%s  seqs=%d", title[:60], raga_id, len(seqs)
                    )
                    time.sleep(self.DELAY)
                except Exception:
                    logger.debug("Failed video %s", vid_id, exc_info=True)

        logger.info("YouTube scraper: %d sequences from %d videos", len(sequences), len(seen_ids))
        return sequences

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _search(self, query: str, limit: int) -> list[dict]:
        """Return video metadata list for a YouTube search query."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,   # metadata only, no download
            "skip_download": True,
        }
        url = f"ytsearch{min(limit * 3, 50)}:{query}"  # over-fetch to allow CC filtering
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = info.get("entries") or []
        # Fetch full metadata (needed for license field) for each entry
        full_metas = []
        for entry in entries[:limit * 3]:
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                        "skip_download": True}) as ydl:
                    full = ydl.extract_info(entry["url"], download=False)
                full_metas.append(full)
            except Exception:
                continue
        return full_metas

    def _download_audio(self, url: str, vid_id: str) -> Path:
        """Download audio-only track. Returns path to WAV file."""
        out_template = str(self.output_dir / f"{vid_id}.%(ext)s")
        wav_path = self.output_dir / f"{vid_id}.wav"

        if wav_path.exists():
            return wav_path   # reuse if already downloaded

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not wav_path.exists():
            # yt-dlp may emit a different extension; find it
            candidates = list(self.output_dir.glob(f"{vid_id}.*"))
            if candidates:
                return candidates[0]
            raise FileNotFoundError(f"No audio file found for {vid_id}")
        return wav_path

    def _audio_to_sequences(
        self, audio_path: Path, raga_id: str | None, segment_secs: int
    ) -> list[dict]:
        """Extract pitch contour from audio and convert to svara sequences."""
        import numpy as _np  # noqa: PLC0415

        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Probabilistic YIN pitch tracker — more accurate than basic YIN
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=2048,
        )
        # Replace NaN (unvoiced) with 0
        pitches_hz = _np.where(_np.isnan(f0), 0.0, f0).tolist()

        tonic_hz = _estimate_tonic_hz(pitches_hz)
        if tonic_hz <= 0:
            return []

        hop = librosa.time_to_frames(segment_secs, sr=sr, hop_length=512)
        sequences: list[dict] = []
        section_cycle = ["pallavi", "anupallavi", "charanam", "chittaswaram"]

        for i, start in enumerate(range(0, len(pitches_hz) - hop, hop)):
            segment = pitches_hz[start: start + hop]
            svaras = DunyaFetcher._pitches_to_svaras(segment, tonic_hz)
            if len(svaras) < 8:
                continue
            sequences.append({
                "raga_id": raga_id or "unknown",
                "section": section_cycle[i % len(section_cycle)],
                "svaras": svaras,
            })

        return sequences


class SoundCloudScraper:
    """Extract Carnatic svara sequences from freely-licensed SoundCloud tracks.

    Uses yt-dlp (which supports the ``scsearch:`` prefix for SoundCloud) for
    track discovery and download, and librosa for pitch-to-svara conversion.
    The same FFmpeg / librosa stack as YouTubeScraper is reused.

    Licence policy:
        SoundCloud tracks have a ``license`` field.  This scraper skips any
        track whose licence is ``"all-rights-reserved"`` (fully copyrighted).
        CC-BY, CC-BY-NC, CC-BY-SA, CC-BY-ND, CC0, and publicdomain tracks are
        all accepted — they are freely usable for research / ML training.

    Requirements: yt-dlp, librosa, ffmpeg  (installed by the notebook deps cell).
    """

    DELAY = 3.0
    _BLOCKED_LICENSES = {"all-rights-reserved"}

    DEFAULT_QUERIES: list[str] = [
        "carnatic classical music raga",
        "veena carnatic concert",
        "carnatic vocal concert",
        "karnatic music instrumental",
        "carnatic flute raga",
        "carnatic violin concert",
        "pallavi carnatic classical",
    ]

    def __init__(self, output_dir: str = "/tmp/raagaai_sc"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def scrape(
        self,
        max_tracks: int = 50,
        segment_secs: int = 30,
        queries: list[str] | None = None,
    ) -> list[dict]:
        """Search SoundCloud, download freely-licensed Carnatic tracks, return svara sequences.

        Args:
            max_tracks:   Maximum number of tracks to download and process.
            segment_secs: Each track is split into fixed-length windows of this size.
            queries:      Custom search queries; defaults to DEFAULT_QUERIES.

        Returns:
            List of {raga_id, section, svaras} dicts.
        """
        if not HAS_YT_DEPS:
            logger.warning(
                "yt-dlp / librosa not installed — skipping SoundCloud scraper."
            )
            return []

        queries = queries or self.DEFAULT_QUERIES
        sequences: list[dict] = []
        seen_ids: set[str] = set()

        for query in queries:
            if len(seen_ids) >= max_tracks:
                break
            try:
                metas = self._search(query, limit=max_tracks - len(seen_ids))
            except Exception:
                logger.debug("SC search failed for %r", query, exc_info=True)
                continue

            for meta in metas:
                if len(seen_ids) >= max_tracks:
                    break

                track_id = str(meta.get("id") or meta.get("webpage_url", "unknown"))
                if track_id in seen_ids:
                    continue

                # Licence gate — skip fully copyrighted tracks
                license_str = (meta.get("license") or "all-rights-reserved").lower().strip()
                if license_str in self._BLOCKED_LICENSES:
                    logger.debug("Skipping SC track (ARR licence): %s", track_id)
                    continue

                seen_ids.add(track_id)
                title = meta.get("title", "")
                description = meta.get("description", "") or ""
                raga_id = _detect_raga_from_text(title + " " + description)

                try:
                    audio_path = self._download_audio(
                        meta["webpage_url"], f"sc_{track_id}"
                    )
                    seqs = self._audio_to_sequences(audio_path, raga_id, segment_secs)
                    sequences.extend(seqs)
                    logger.info(
                        "SC: %-60s  licence=%-18s  raga=%-20s  seqs=%d",
                        title[:60], license_str, raga_id, len(seqs),
                    )
                    time.sleep(self.DELAY)
                except Exception:
                    logger.debug("SC failed track %s", track_id, exc_info=True)

        logger.info(
            "SoundCloud: %d sequences from %d tracks", len(sequences), len(seen_ids)
        )
        return sequences

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _search(self, query: str, limit: int) -> list[dict]:
        """Return full track metadata for a SoundCloud search query."""
        flat_opts = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
        }
        sc_url = f"scsearch{min(limit * 3, 50)}:{query}"
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            info = ydl.extract_info(sc_url, download=False)

        entries = info.get("entries") or []
        full_metas: list[dict] = []
        fetch_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        for entry in entries[: limit * 3]:
            try:
                page_url = entry.get("url") or entry.get("webpage_url", "")
                with yt_dlp.YoutubeDL(fetch_opts) as ydl:
                    full_metas.append(ydl.extract_info(page_url, download=False))
            except Exception:
                continue
        return full_metas

    def _download_audio(self, url: str, track_id: str) -> Path:
        """Download audio-only and convert to WAV. Returns the WAV path."""
        wav_path = self.output_dir / f"{track_id}.wav"
        if wav_path.exists():
            return wav_path

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": str(self.output_dir / f"{track_id}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not wav_path.exists():
            candidates = list(self.output_dir.glob(f"{track_id}.*"))
            if candidates:
                return candidates[0]
            raise FileNotFoundError(f"No audio file produced for track {track_id}")
        return wav_path

    def _audio_to_sequences(
        self, audio_path: Path, raga_id: str | None, segment_secs: int
    ) -> list[dict]:
        """Pitch-extract audio and return windowed svara sequences."""
        import numpy as _np  # noqa: PLC0415

        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        f0, _, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=2048,
        )
        pitches_hz = _np.where(_np.isnan(f0), 0.0, f0).tolist()

        tonic_hz = _estimate_tonic_hz(pitches_hz)
        if tonic_hz <= 0:
            return []

        hop = librosa.time_to_frames(segment_secs, sr=sr, hop_length=512)
        section_cycle = ["pallavi", "anupallavi", "charanam", "chittaswaram"]
        sequences: list[dict] = []

        for i, start in enumerate(range(0, len(pitches_hz) - hop, hop)):
            svaras = DunyaFetcher._pitches_to_svaras(
                pitches_hz[start: start + hop], tonic_hz
            )
            if len(svaras) < 8:
                continue
            sequences.append({
                "raga_id": raga_id or "unknown",
                "section": section_cycle[i % len(section_cycle)],
                "svaras": svaras,
            })
        return sequences


def augment_sequences(sequences: list[dict]) -> list[dict]:
    """Raga-preserving augmentation.

    Chromatic transposition is intentionally NOT used: shifting svara indices in
    [Sa, Ri1, Ri2, Ga1, Ga2, Ma1, Ma2, Pa, Da1, Da2, Ni1, Ni2] takes a sequence
    out of its raga (e.g. shankarabharanam +1 maps Sa→Ri1, but Ri1 isn't in
    shankarabharanam) — the result would carry a wrong raga label.

    Augmentations applied (each preserves the original raga_id):
      1. Sub-phrase repetition — repeat a random 4-svara window in place.
      2. Sub-window sampling — extract two random contiguous slices.
    """
    augmented = list(sequences)

    for seq in sequences:
        svaras = seq["svaras"]
        raga_id = seq["raga_id"]
        section = seq["section"]

        # 1. Sub-phrase repetition
        if len(svaras) >= 8:
            start = random.randint(0, len(svaras) - 4)
            phrase = svaras[start:start + 4]
            repeated = svaras[:start] + phrase + phrase + svaras[start + 4:]
            augmented.append({
                "raga_id": raga_id,
                "section": section,
                "svaras": repeated[:64],
            })

        # 2. Sub-window sampling — two random contiguous slices
        if len(svaras) >= 16:
            for _ in range(2):
                window_len = random.randint(16, min(48, len(svaras)))
                if window_len >= len(svaras):
                    continue  # would just duplicate the original
                start = random.randint(0, len(svaras) - window_len)
                augmented.append({
                    "raga_id": raga_id,
                    "section": section,
                    "svaras": svaras[start:start + window_len],
                })

    return augmented
