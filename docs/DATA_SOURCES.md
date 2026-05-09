# Training Data Sources

The model trains on `data/training/svara_sequences.jsonl`, built by `scripts/build_dataset.py`. Each line is `{"raga_id": str, "section": str, "svaras": list[str]}`.

Below are every source the builder supports today, ranked by signal quality.

## 1. Saraga Carnatic 1.5 — best quality, recommended

Hand-annotated recordings from CompMusic / Music Technology Group (UPF Barcelona). Includes pitch tracks, tonic, raga/tala labels, and svara phrase annotations.

**License:** CC-BY-NC-SA 4.0 (research / non-commercial only).

### Download

1. Create a free Zenodo account: <https://zenodo.org/>
2. Request access on the Saraga 1.5 Carnatic page: <https://zenodo.org/records/4301737>
3. Download `saraga1.5_carnatic.zip` (~30 GB).
4. Extract:
   ```bash
   unzip saraga1.5_carnatic.zip -d data/saraga/
   ```

### Use

```bash
python -m scripts.build_dataset --saraga-dir data/saraga/saraga1.5_carnatic
```

This walks every `.json` file under that root looking for `svaraNotation` or `svara_phrases` fields and adds them to the dataset.

## 2. CompMusic Dunya API — pitch contours + raga labels

REST API serving the same underlying CompMusic recordings, but as derived signal features (pitch contour, tonic) rather than raw audio. Lower bandwidth than Saraga but you get fewer phrase-level annotations.

### Get a token

1. Register at <https://dunya.compmusic.upf.edu/user/register/>
2. Visit <https://dunya.compmusic.upf.edu/user/profile/> and copy your API token.

### Use

```bash
export DUNYA_TOKEN="paste-your-token-here"
python -m scripts.build_dataset --dunya-recordings 200
```

Or pass it inline:

```bash
python -m scripts.build_dataset --dunya-token "..." --dunya-recordings 200
```

The fetcher pulls each recording's metadata, tonic Hz, and pitch contour, then converts cents-from-tonic to the nearest 12-TET svara.

## 3. karnatik.com — krithi notation

Open Carnatic notation site with hundreds of compositions. Already supported.

```bash
python -m scripts.build_dataset --scrape-karnatik --max-web-pages 200
```

Polite by default — 2 s delay between requests.

## 4. shivkumar.org — krithi notation

Personal site with a deep catalog of krithi notations. Polite scraper that checks `robots.txt` first.

```bash
python -m scripts.build_dataset --scrape-shivkumar --max-web-pages 200
```

## 5. Synthetic from local raga definitions — always on

Generates plausible svara walks from `data/ragas/*.json` arohanam/avarohanam patterns. No network needed. Tunable:

```bash
python -m scripts.build_dataset --synthetic-per-raga 500
```

## What we deliberately do NOT scrape

- **YouTube / streaming audio** — copyrighted, and converting raw audio to svara sequences requires its own pitch-extraction pipeline (use Saraga + Dunya instead, which already provide labeled pitch data).
- **MAESTRO** — Western piano data. Pollutes the Carnatic phrase distribution. The `scripts/maestro_to_svara.py` converter exists but is not recommended.
- **Sites requiring login (sangeethapriya.org etc.)** — credentials shouldn't live in a scraper.

## Build everything

```bash
export DUNYA_TOKEN="..."
python -m scripts.build_dataset \
    --saraga-dir data/saraga/saraga1.5_carnatic \
    --scrape-karnatik --scrape-shivkumar --max-web-pages 300 \
    --dunya-recordings 300 \
    --synthetic-per-raga 300
```

Then retrain:

```bash
make train-model
# or: python -m scripts.train_model --epochs 100 --batch-size 64
```
