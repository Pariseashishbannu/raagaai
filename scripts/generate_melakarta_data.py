"""Generate all 72 melakarta raga data using the Katapayadi formula."""

import json
import os

# 6 Ri-Ga combinations (chakra-based)
RI_GA_COMBOS = [
    ("Ri1", "Ga1"),   # Shuddha Ri, Shuddha Ga
    ("Ri1", "Ga2"),   # Shuddha Ri, Sadharana Ga
    ("Ri1", "Ga2"),   # Shuddha Ri, Antara Ga (Ga2 used since Ga3 not in our 12-svara system)
    ("Ri2", "Ga2"),   # Chatushruti Ri, Sadharana Ga
    ("Ri2", "Ga2"),   # Chatushruti Ri, Antara Ga
    ("Ri2", "Ga2"),   # Shatshruti Ri, Antara Ga
]

DA_NI_COMBOS = [
    ("Da1", "Ni1"),
    ("Da1", "Ni2"),
    ("Da1", "Ni2"),
    ("Da2", "Ni2"),
    ("Da2", "Ni2"),
    ("Da2", "Ni2"),
]

MELAKARTA_NAMES = [
    "Kanakangi", "Ratnangi", "Ganamurthi", "Vanaspathi", "Manavathi", "Tanarupi",
    "Senavathi", "Hanumatodi", "Dhenuka", "Natakapriya", "Kokilapriya", "Rupavathi",
    "Gayakapriya", "Vakulabharanam", "Mayamalavagowla", "Chakravakam", "Suryakantam", "Hatakambari",
    "Jhankaradhwani", "Natabhairavi", "Keeravani", "Kharaharapriya", "Gourimanohari", "Varunapriya",
    "Mararanjani", "Charukesi", "Sarasangi", "Harikambhoji", "Shankarabharanam", "Naganandini",
    "Yagapriya", "Ragavardhini", "Gangeyabhushini", "Vagadheeswari", "Shulini", "Chalanata",
    "Salagam", "Jalarnavam", "Jhalavarali", "Navaneetam", "Pavani", "Raghupriya",
    "Gavambhodhi", "Bhavapriya", "Shubhapantuvarali", "Shadvidhamargini", "Suvarnangi", "Divyamani",
    "Dhavalambari", "Namanarayani", "Kamavardhini", "Ramapriya", "Gamanashrama", "Vishwambari",
    "Shamalangi", "Shanmukhapriya", "Simhendramadhyamam", "Hemavathi", "Dharmavathi", "Neethimathi",
    "Kantamani", "Rishabhapriya", "Latangi", "Vachaspathi", "Mechakalyani", "Chitrambari",
    "Sucharitra", "Jyothiswarupini", "Dhathuvardhini", "Nasikabhushini", "Kosalam", "Rasikapriya",
]

RASA_TAGS_BY_NUMBER = {
    8: ["karuna"],         # Hanumatodi
    15: ["bhakti"],        # Mayamalavagowla
    20: ["karuna", "shanta"],  # Natabhairavi
    22: ["shringara"],     # Kharaharapriya
    28: ["shringara", "karuna"],  # Harikambhoji
    29: ["veera", "shanta"],  # Shankarabharanam
    56: ["veera"],         # Shanmukhapriya
    65: ["shringara", "bhakti"],  # Mechakalyani (Kalyani)
}


def generate_melakarta(number: int) -> dict:
    idx = number - 1
    ma = "Ma1" if idx < 36 else "Ma2"
    effective_idx = idx if idx < 36 else idx - 36

    ri_ga_idx = effective_idx // 6
    da_ni_idx = effective_idx % 6

    ri, ga = RI_GA_COMBOS[ri_ga_idx]
    da, ni = DA_NI_COMBOS[da_ni_idx]

    arohanam = ["Sa", ri, ga, ma, "Pa", da, ni, "Sa"]
    avarohanam = list(reversed(arohanam))

    name = MELAKARTA_NAMES[idx]
    raga_id = name.lower().replace(" ", "")

    return {
        "id": raga_id,
        "name_english": name,
        "name_telugu": "",
        "melakarta_number": number,
        "arohanam": arohanam,
        "avarohanam": avarohanam,
        "varja_svaras": [],
        "characteristic_phrases": [arohanam[:4], avarohanam[:4]],
        "gamaka_rules": {},
        "janya_of": None,
        "rasa_tags": RASA_TAGS_BY_NUMBER.get(number, []),
    }


def main():
    ragas = {}
    for i in range(1, 73):
        raga = generate_melakarta(i)
        ragas[raga["id"]] = raga

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data", "ragas")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "melakarta.json"), "w", encoding="utf-8") as f:
        json.dump(ragas, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(ragas)} melakarta ragas -> data/ragas/melakarta.json")


if __name__ == "__main__":
    main()
