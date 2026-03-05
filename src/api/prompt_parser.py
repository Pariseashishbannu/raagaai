"""Simple keyword-based parser for natural language song prompts."""


class PromptParser:
    RAGA_KEYWORDS = {
        "mohanam": "mohanam",
        "shankarabharanam": "shankarabharanam",
        "kalyani": "kalyani",
        "kambhoji": "kambhoji",
        "bhairavi": "bhairavi",
        "todi": "todi",
        "kharaharapriya": "kharaharapriya",
        "harikambhoji": "harikambhoji",
        "begada": "begada",
        "abhogi": "abhogi",
        "hindolam": "hindolam",
        "hamsadhwani": "hamsadhwani",
        "bilahari": "bilahari",
        "sahana": "sahana",
        "anandabhairavi": "anandabhairavi",
        "charukesi": "charukesi",
        "natabhairavi": "natabhairavi",
        "mayamalavagowla": "mayamalavagowla",
        "sankarabharanam": "shankarabharanam",
    }

    THEME_KEYWORDS = {
        "romantic": "romantic",
        "love": "romantic",
        "prema": "romantic",
        "romance": "romantic",
        "devotional": "devotional",
        "bhakti": "devotional",
        "god": "devotional",
        "divine": "devotional",
        "spiritual": "devotional",
        "prayer": "devotional",
        "temple": "devotional",
        "nature": "nature",
        "rain": "nature",
        "river": "nature",
        "forest": "nature",
        "flower": "nature",
        "celebration": "celebration",
        "happy": "celebration",
        "joy": "celebration",
        "festival": "celebration",
        "dance": "celebration",
        "sad": "melancholy",
        "melancholy": "melancholy",
        "longing": "melancholy",
        "separation": "melancholy",
        "miss": "melancholy",
    }

    TEMPO_KEYWORDS = {
        "slow": "vilamba",
        "gentle": "vilamba",
        "soft": "vilamba",
        "calm": "vilamba",
        "peaceful": "vilamba",
        "fast": "druta",
        "upbeat": "druta",
        "energetic": "druta",
        "quick": "druta",
        "lively": "druta",
    }

    def parse(self, prompt: str) -> dict:
        """Extract raga, theme, tempo from a natural language prompt."""
        lower = prompt.lower()
        result = {
            "raga_id": "mohanam",
            "tala_id": "adi",
            "kala": "madhyama",
            "theme": "romantic",
        }

        for keyword, raga_id in self.RAGA_KEYWORDS.items():
            if keyword in lower:
                result["raga_id"] = raga_id
                break

        for keyword, theme in self.THEME_KEYWORDS.items():
            if keyword in lower:
                result["theme"] = theme
                break

        for keyword, kala in self.TEMPO_KEYWORDS.items():
            if keyword in lower:
                result["kala"] = kala
                break

        return result
