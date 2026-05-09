"""Template-based sahityam (lyrics) generator for Telugu songs."""

import random
from dataclasses import dataclass


@dataclass
class AlignedSahityam:
    full_text: str
    lines: list[str]
    mapping: list[tuple[str, str]]  # (svara, akshara) pairs
    detected_meter: str


@dataclass
class SahityamResult:
    text: str
    lines: list[str]
    akshara_svara_map: list[tuple[str, str]]
    chandas_meter: str


@dataclass
class SongResult:
    """Result from generate_song() — structured lyrics with title."""
    title: str
    full_text: str
    sections: dict[str, str]  # section_name -> lyrics text
    svara_sequence: list[str]


# Song titles per theme
SONG_TITLES = {
    "devotional": [
        "దివ్య కృపా", "శ్రీ మహిమ", "భక్తి గీతం", "దేవ స్తుతి",
        "శరణాగతి", "ఆనంద లహరి", "పరమ జ్యోతి", "అమృత వర్షం",
    ],
    "romantic": [
        "ప్రేమ రాగం", "మధుర స్వరం", "నీ తలపులో", "హృదయ గీతం",
        "వెన్నెల రాత్రి", "ప్రణయ సంగీతం", "మనసు పాట", "చందమామ",
        "ఆకాశం నాది", "నీ కోసం", "ప్రేమ కావ్యం", "మల్లెపూల వాన",
    ],
    "nature": [
        "ప్రకృతి గానం", "హరిత స్వప్నం", "వనమాల", "సూర్యోదయం",
        "మేఘ సందేశం", "నది పాట", "పూల తోట", "గాలి పాట",
    ],
    "celebration": [
        "ఆనంద నృత్యం", "సంబరాల వేళ", "జయ జయ గీతం", "ఉత్సవ వేళ",
        "సంతోష గానం", "విజయ గీతం", "పండుగ పాట", "మంగళ గీతం",
    ],
    "melancholy": [
        "విరహ గీతం", "ఏకాంత రాగం", "కన్నీటి పాట", "మౌన రాగం",
        "వేదన స్వరం", "దూరం అయినా", "గుర్తుందా నీకు", "మరపురాని రోజులు",
    ],
}

# Telugu lyric templates by theme — expanded with more variety
TEMPLATES = {
    "devotional": {
        "pallavi": [
            "శ్రీ రామ జయ రామ జయ జయ రామ",
            "గోవిందా హరి గోవిందా",
            "నారాయణ శ్రీమన్ నారాయణ",
            "శంకరా శివ శంకరా",
            "దేవా శ్రీ మహా దేవా",
            "వేంకటేశ్వరా శ్రీనివాసా",
            "గణపతి బాప్పా మోరయా",
            "సరస్వతీ నమోస్తుతే",
        ],
        "anupallavi": [
            "పాహి మాం శ్రీ పతే",
            "కరుణా సాగరా దేవా",
            "మంగళం జయ మంగళం",
            "నన్ను బ్రోవు ప్రభో",
            "అనుగ్రహింపు దయతో",
            "నీ దయ లేనిదే గతి లేదు",
            "శ్రీ పాదములే శరణము నాకు",
            "భక్తవత్సలా కరుణించు",
        ],
        "charanam": [
            "భక్తి తో నిన్ను కొలిచేద మనసారా నేను",
            "పరమాత్మా నీవే గతి యని నమ్మితి నేను",
            "సకల లోక నాథా కరుణ జూడు మాపై",
            "శరణు శరణు నీకే శరణం దేవ దేవా",
            "నీ పాద సేవ నే చేతునయ్యా దేవా",
            "ఆపద మొక్కులను తీర్చు స్వామీ దేవా",
            "నీ నామ స్మరణే నాకు ఆనందమయ్యా",
            "దీనులను బ్రోచే దేవుడవు నీవే కదా",
        ],
        "chorus": [
            "జయ జయ జయ హో దేవా నీకు జయమగుగాక",
            "నమో నమో దేవా శరణం శరణం",
            "హరి ఓం నమః శివాయ ఓం నమః",
        ],
    },
    "romantic": {
        "pallavi": [
            "మధుర స్వరములు విన వచ్చెను",
            "చందమామ రావే జాబిల్లి రావే",
            "ఆనందమే జీవితము",
            "నీ కళ్ళలో నేను కనిపించానా",
            "ఈ గాలిలో నీ పరిమళం తెలిసెను",
            "మనసు పాడే పాట నీదే కదా",
            "ప్రేమ అనే మాట నీతో తెలిసెను",
            "నీ చిరునవ్వే నా లోకం",
        ],
        "anupallavi": [
            "మనసున మల్లెల మాలలు",
            "హృదయం పాడే రాగం ఇది",
            "పూలవానలో తడిసి నేను",
            "నీ తోడు ఉంటే చాలు నాకు",
            "కలలో కూడా నిన్నే చూస్తా",
            "ఈ క్షణం ఆగిపోతే బాగుండు",
            "నీ మాటలే నా ఊపిరి",
            "వెన్నెల రాత్రుల్లో నీ ఊహలే",
        ],
        "charanam": [
            "వెన్నెల రాత్రిలో నీ తలపులు వచ్చెను",
            "కలలో కనిపించే అందమైన ఊహలు",
            "సంగీతమే ప్రాణం నాకు ఈ రాగమే",
            "నీ అడుగుల చప్పుడు వినిపించెను నాకు",
            "ఎన్ని జన్మలైనా నీతోనే ఉంటాను",
            "నీ ప్రేమలో తడిసి ముద్దవుతాను నేను",
            "రోజులు గడిచినా మారదు ఈ ప్రేమ",
            "దూరమైనా నీ గుర్తు మరువలేను",
        ],
        "chorus": [
            "నిన్నే ప్రేమిస్తున్నా ఈ జన్మలో నీకోసమే",
            "ఈ ప్రేమ రాగం ఆగదులే ఎన్నటికీ",
            "నీతో నడిచే ప్రతి అడుగూ అందమే",
        ],
    },
    "nature": {
        "pallavi": [
            "వనమాలి వనమాలి హరి",
            "ప్రకృతి సౌందర్యం ఎంతో మనోహరం",
            "పూల తోటలో పక్షుల పాటలు",
            "కొండల్లో పారే ఝరి పాట విను",
            "ఆకాశం నిండా చుక్కల వెలుగు",
            "సముద్రపు అలలే సంగీతం పాడే",
        ],
        "anupallavi": [
            "నదులు కొండలు అడవులు",
            "పచ్చని చేలలో గాలి వీచెను",
            "మేఘాలు కదిలేను ఆకాశమంతా",
            "చెట్ల నీడలో సేద తీరేను",
            "పసిడి వెలుగులో పంట పొలాలు",
            "వానచినుకులతో భూమి పులకించెను",
        ],
        "charanam": [
            "సూర్యోదయం వెలుగులో లోకం మేల్కొనెను",
            "చిరుగాలి తెమ్మెర చల్లని సాయంత్రం",
            "హరిత వర్ణాల మధ్య శాంతి దొరికెను",
            "పక్షుల కిలకిలలతో ఉదయం మొదలాయెను",
            "చంద్రుడి వెన్నెలలో రాత్రి అందమాయెను",
            "వసంత కాలంలో పూలన్నీ విరిసెను",
        ],
        "chorus": [
            "ఈ భూమి అందమే మన సంపద కదా",
            "ప్రకృతి ఒడిలో ప్రశాంతత దొరికెను",
            "పచ్చని లోకంలో ఆనందమే ఆనందం",
        ],
    },
    "celebration": {
        "pallavi": [
            "ఆనందమే ఆనందమే ఈ వేళ",
            "సంబరాల వేళ వచ్చెను చూడండి",
            "పండుగ పండుగ ఈ రోజు మనకు",
            "జరుపుకుందాం ఈ శుభ వేళ",
            "సంతోషంతో పాడుదాం రండి",
        ],
        "anupallavi": [
            "ఆడి పాడి సంతోషించండి",
            "జీవితమే ఒక పండుగ కదా",
            "కలిసి మెలిసి ఉందాం మనమంతా",
            "ఈ క్షణమే మన సొంతం",
        ],
        "charanam": [
            "రంగులు చల్లుకుని నవ్వుల పండగ చేద్దాం",
            "పాటలతో ఆటలతో రోజంతా సరదాగా",
            "మిత్రులతో కలిసి ఈ వేళ గడుపుదాం",
            "సంగీతం నృత్యం సాహిత్యం మన సంస్కృతి",
            "ప్రతి రోజూ పండుగలా జీవించాలి మనం",
        ],
        "chorus": [
            "ఆనందం ఆనందం ఆనందమే మనకు ఇవాళ",
            "జయ జయ జయహో విజయం మనదే",
            "పాడుదాం ఆడుదాం సంతోషంగా",
        ],
    },
    "melancholy": {
        "pallavi": [
            "ఎందుకో ఈ మౌనం నాలో",
            "దూరమైపోయావు ఎందుకో నీవు",
            "కన్నీటి చుక్కల్లో కరిగే నా మనసు",
            "ఒంటరిగా ఈ రాత్రి గడుపుతున్నా",
            "గుర్తొస్తున్నాయి ఆ రోజులన్నీ",
        ],
        "anupallavi": [
            "మాటలు రాని బాధ ఇది",
            "ఎవరికి చెప్పను ఈ వేదన",
            "కాలం గడిచినా మానని గాయం",
            "నీ జ్ఞాపకాల్లో బ్రతుకుతున్నా",
        ],
        "charanam": [
            "ఆ నవ్వులు ఆ మాటలు ఇప్పుడు ఎక్కడ",
            "ఒకప్పుడు పూల వనం ఇప్పుడు ఎడారి",
            "గడిచిన రోజులు తిరిగి రావని తెలుసు",
            "కన్నీళ్ళే నా తోడు ఈ చీకటి రాత్రిలో",
            "మరిచిపోలేని క్షణాలు మనసులో మిగిలాయి",
        ],
        "chorus": [
            "ఈ బాధ ఎప్పటికైనా తగ్గుతుందా",
            "ఒంటరి రాత్రిలో వెతుకుతున్నా నిన్ను",
            "కన్నీళ్ళే నా భాష ఇప్పుడు",
        ],
    },
}

# Telugu aksharas (syllables) for filler generation
TELUGU_AKSHARAS = [
    "క", "ఖ", "గ", "ఘ", "చ", "ఛ", "జ", "ఝ",
    "ట", "ఠ", "డ", "ఢ", "ణ", "త", "థ", "ద",
    "ధ", "న", "ప", "ఫ", "బ", "భ", "మ", "య",
    "ర", "ల", "వ", "శ", "ష", "స", "హ",
    "ా", "ి", "ీ", "ు", "ూ", "ె", "ే", "ొ", "ో",
    "ం", "ః",
]

VOWELS = ["అ", "ఆ", "ఇ", "ఈ", "ఉ", "ఊ", "ఎ", "ఏ", "ఒ", "ఓ"]


class SahityamGenerator:
    """Template-based Telugu lyric generator aligned to svara sequences."""

    def generate(
        self,
        svara_sequence: list[str],
        raga_id: str,
        section: str = "pallavi",
        theme: str | None = None,
        language: str = "telugu",
    ) -> SahityamResult:
        theme = theme or "devotional"
        if theme not in TEMPLATES:
            theme = "devotional"

        section_key = section if section in ("pallavi", "anupallavi") else "charanam"
        templates = TEMPLATES[theme][section_key]
        base_text = random.choice(templates)

        # Align syllables to svaras
        aligned = self._align_to_svaras(base_text, svara_sequence)

        return SahityamResult(
            text=aligned.full_text,
            lines=aligned.lines,
            akshara_svara_map=aligned.mapping,
            chandas_meter=aligned.detected_meter,
        )

    def generate_for_composition(
        self,
        sections: list[dict],
        raga_id: str,
        theme: str | None = None,
    ) -> list[SahityamResult]:
        """Generate sahityam for each section of a composition."""
        results = []
        for sec in sections:
            result = self.generate(
                svara_sequence=sec["svaras"],
                raga_id=raga_id,
                section=sec["section"],
                theme=theme,
            )
            results.append(result)
        return results

    def generate_song(
        self,
        svara_sections: dict[str, list[str]],
        raga_id: str,
        theme: str = "romantic",
    ) -> SongResult:
        """Generate a full song with title and per-section Telugu lyrics.

        Args:
            svara_sections: Dict mapping section names to svara lists
                            e.g. {"pallavi": ["S","R","G"], "anupallavi": [...]}
            raga_id: The raga identifier.
            theme: One of the available themes.

        Returns:
            SongResult with title, full text, and per-section lyrics.
        """
        if theme not in TEMPLATES:
            theme = "romantic"

        # Pick a song title
        titles = SONG_TITLES.get(theme, SONG_TITLES["romantic"])
        title = random.choice(titles)

        sections_text: dict[str, str] = {}
        all_svaras: list[str] = []

        for section_name, svaras in svara_sections.items():
            if not svaras:
                continue

            # Map section to template key
            if section_name in ("pallavi", "anupallavi"):
                tpl_key = section_name
            elif section_name == "chittaswaram":
                tpl_key = "charanam"
            else:
                tpl_key = "charanam"

            templates = TEMPLATES[theme].get(tpl_key, TEMPLATES[theme]["charanam"])
            base_text = random.choice(templates)

            # For chorus sections (anupallavi in song mode), try chorus templates
            if section_name == "anupallavi" and "chorus" in TEMPLATES[theme]:
                base_text = random.choice(TEMPLATES[theme]["chorus"])

            aligned = self._align_to_svaras(base_text, svaras)
            sections_text[section_name] = aligned.full_text
            all_svaras.extend(svaras)

        # Build full text
        full_lines = []
        for sec_name, text in sections_text.items():
            label = sec_name.replace("_", " ").title()
            full_lines.append(f"[{label}]")
            full_lines.append(text)
            full_lines.append("")

        return SongResult(
            title=title,
            full_text="\n".join(full_lines).strip(),
            sections=sections_text,
            svara_sequence=all_svaras,
        )

    def _align_to_svaras(
        self, text: str, svara_sequence: list[str]
    ) -> AlignedSahityam:
        """Map aksharas (syllables) to svara positions."""
        # Split text into Unicode characters / syllable groups
        aksharas = self._split_aksharas(text)

        # Pad or trim aksharas to match svara count
        while len(aksharas) < len(svara_sequence):
            aksharas.extend(self._split_aksharas(text))
        aksharas = aksharas[: len(svara_sequence)]

        mapping = list(zip(svara_sequence, aksharas))

        # Group into lines (one per avartanam, ~8 aksharas)
        line_size = 8
        lines = []
        for i in range(0, len(aksharas), line_size):
            lines.append("".join(aksharas[i : i + line_size]))

        return AlignedSahityam(
            full_text=" ".join(lines),
            lines=lines,
            mapping=mapping,
            detected_meter="chatusra",
        )

    def _split_aksharas(self, text: str) -> list[str]:
        """Split Telugu text into aksharas (syllable units)."""
        aksharas = []
        text = text.replace(" ", "")
        i = 0
        while i < len(text):
            # A Telugu akshara is a consonant + optional vowel mark
            char = text[i]
            akshara = char
            i += 1
            # Collect combining marks (vowel signs, anusvara, etc.)
            while i < len(text) and not self._is_main_char(text[i]):
                akshara += text[i]
                i += 1
            aksharas.append(akshara)
        return aksharas

    def _is_main_char(self, c: str) -> bool:
        """Check if character is a main (non-combining) Telugu character."""
        cp = ord(c)
        # Telugu consonants: 0C15-0C39, Vowels: 0C05-0C14
        return (0x0C05 <= cp <= 0x0C39) or (0x0C60 <= cp <= 0x0C61) or c.isascii()
