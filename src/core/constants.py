"""Carnatic music constants: svaras, octaves, gamakas, talas."""

from enum import Enum


class Svara(str, Enum):
    SA = "Sa"
    RI1 = "Ri1"
    RI2 = "Ri2"
    GA1 = "Ga1"
    GA2 = "Ga2"
    MA1 = "Ma1"
    MA2 = "Ma2"
    PA = "Pa"
    DA1 = "Da1"
    DA2 = "Da2"
    NI1 = "Ni1"
    NI2 = "Ni2"


class Octave(str, Enum):
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"


class GamakaType(str, Enum):
    KAMPITA = "kampita"      # oscillation
    JARU = "jaru"            # slide
    NOKKU = "nokku"          # stress
    ODUKKAL = "odukkal"      # deflection
    SPHURITA = "sphurita"    # repeated stress
    PRATYAHATA = "pratyahata"  # bounce


class Kala(str, Enum):
    VILAMBA = "vilamba"      # slow
    MADHYAMA = "madhyama"   # medium
    DRUTA = "druta"          # fast


class Section(str, Enum):
    PALLAVI = "pallavi"
    ANUPALLAVI = "anupallavi"
    CHARANAM = "charanam"
    CHITTASWARAM = "chittaswaram"


# Chromatic semitone positions (Sa = 0)
SVARA_SEMITONES: dict[str, int] = {
    "Sa": 0, "Ri1": 1, "Ri2": 2, "Ga1": 2, "Ga2": 3,
    "Ma1": 5, "Ma2": 6, "Pa": 7, "Da1": 8, "Da2": 9,
    "Ni1": 9, "Ni2": 10,
}

# Note: Ri2 == Ga1 (enharmonic), Da2 == Ni1 (enharmonic) in Carnatic system

# All 16 svara positions in order
ALL_SVARAS = ["Sa", "Ri1", "Ri2", "Ga1", "Ga2", "Ma1", "Ma2", "Pa", "Da1", "Da2", "Ni1", "Ni2"]

# Base tonic frequency (C4 area, typical for Carnatic)
DEFAULT_TONIC_HZ = 261.63  # Middle C (adjustable per performer)

# Tala definitions
TALA_DEFINITIONS = {
    "adi": {"name": "Adi", "beats": 8, "jathi": "chatusra", "structure": ["laghu", "drutam", "drutam"]},
    "rupaka": {"name": "Rupaka", "beats": 3, "jathi": "chatusra", "structure": ["drutam", "laghu"]},
    "misra_chapu": {"name": "Misra Chapu", "beats": 7, "jathi": "misra", "structure": ["3", "2", "2"]},
    "khanda_chapu": {"name": "Khanda Chapu", "beats": 5, "jathi": "khanda", "structure": ["2", "1", "2"]},
    "triputa": {"name": "Triputa", "beats": 7, "jathi": "tisra", "structure": ["laghu", "drutam", "drutam"]},
    "ata": {"name": "Ata", "beats": 10, "jathi": "chatusra", "structure": ["laghu", "laghu", "drutam", "drutam"]},
    "dhruva": {"name": "Dhruva", "beats": 11, "jathi": "chatusra", "structure": ["laghu", "drutam", "laghu", "laghu"]},
}

# Tempo ranges (beats per minute)
KALA_BPM = {
    Kala.VILAMBA: 60,
    Kala.MADHYAMA: 100,
    Kala.DRUTA: 160,
}
