#!/usr/bin/env python3
"""
Process the SBIR.gov bulk awards CSV into Grantentic training subsets and a
v1 language-pattern analysis.

Inputs:
  training_data/raw/sbir_all_awards_with_abstracts   (CSV from sbir.gov)

Outputs:
  training_data/processed/nsf_phase_i_2015_2024.json
  training_data/processed/nasa_phase_i_2015_2024.json
  training_data/processed/dod_phase_i_2015_2024.json
  training_data/patterns/language_patterns.json

Per-record schema (extends scripts/extract_nsf_phase_i.py from prior work):
  company_name, award_title, award_year, award_amount, topic_code, abstract,
  award_date, agency, branch, research_area_keywords

The language-pattern taxonomy is v1 — flagged in the JSON as requiring human
review. Knowledge-vs-product keyword lists come from Tom's spec.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "training_data" / "raw" / "sbir_all_awards_with_abstracts"
PROCESSED = ROOT / "training_data" / "processed"
PATTERNS = ROOT / "training_data" / "patterns"

YEAR_MIN, YEAR_MAX = 2015, 2024

AGENCY_FILES = {
    "NSF": PROCESSED / "nsf_phase_i_2015_2024.json",
    "NASA": PROCESSED / "nasa_phase_i_2015_2024.json",
    "DOD": PROCESSED / "dod_phase_i_2015_2024.json",
}

KNOWLEDGE_SIGNALS = [
    "we hypothesize",
    "we will characterize",
    "we will validate",
    "we will demonstrate",
    "novel framework",
    "technical unknown",
    "we will determine",
    "proof of concept",
    "fundamental understanding",
    "we will model",
    "we will measure",
]

PRODUCT_SIGNALS = [
    "we will build",
    "we will develop",
    "we will deliver",
    "we will commercialize",
    "our product",
    "our platform",
    "our solution",
    "our system will",
]

# csv.field_size_limit defaults are too small for some abstracts on Windows.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "while", "with", "without",
    "of", "for", "to", "in", "on", "at", "by", "from", "as", "is", "are",
    "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "we", "our", "us", "i", "you", "your", "they", "their",
    "will", "have", "has", "had", "can", "could", "should", "would", "may",
    "might", "must", "shall", "do", "does", "did", "not", "no", "than",
    "then", "so", "such", "into", "over", "under", "more", "most", "less",
    "least", "very", "much", "many", "much", "few", "all", "any", "some",
    "each", "every", "other", "another", "also", "however", "thus", "which",
    "who", "whom", "whose", "what", "where", "when", "why", "how",
    "between", "among", "during", "after", "before", "above", "below",
    "out", "up", "down", "off", "about", "through", "per", "via",
    "well", "new", "based",
}


def normalize_agency(raw_agency: str, branch: str) -> str | None:
    a = (raw_agency or "").strip().upper()
    b = (branch or "").strip().upper()
    if a in {"NSF", "NATIONAL SCIENCE FOUNDATION"}:
        return "NSF"
    if a in {"NASA", "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION"}:
        return "NASA"
    if a in {"DOD", "DEPARTMENT OF DEFENSE"} or "DEFENSE" in a:
        return "DOD"
    if "DEFENSE" in b or b in {"DOD"}:
        return "DOD"
    return None


def parse_year(value: str) -> int | None:
    try:
        y = int(str(value).strip())
        return y if 1900 < y < 2100 else None
    except (ValueError, TypeError):
        return None


def detect_field(headers: list[str], *candidates: str) -> str | None:
    norm = {re.sub(r"[^a-z0-9]+", "", h.lower()): h for h in headers}
    for c in candidates:
        key = re.sub(r"[^a-z0-9]+", "", c.lower())
        if key in norm:
            return norm[key]
    return None


def iter_records(csv_path: Path) -> Iterator[dict]:
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        f_company = detect_field(headers, "Company", "Company Name", "Firm")
        f_title = detect_field(headers, "Award Title", "Title")
        f_year = detect_field(headers, "Award Year", "Year")
        f_amount = detect_field(headers, "Award Amount", "Amount")
        f_topic = detect_field(headers, "Topic Code", "Topic")
        f_abstract = detect_field(headers, "Abstract")
        f_date = detect_field(headers, "Award Date", "Proposal Award Date")
        f_agency = detect_field(headers, "Agency")
        f_branch = detect_field(headers, "Branch")
        f_phase = detect_field(headers, "Phase")
        f_keywords = detect_field(
            headers, "Research Area Keywords", "Research Keywords",
            "Keywords", "Research Area"
        )
        if not (f_agency and f_phase and f_abstract):
            raise SystemExit(
                f"CSV missing required columns. Headers seen: {headers}"
            )
        for row in reader:
            yield {
                "company_name": (row.get(f_company) or "").strip(),
                "award_title": (row.get(f_title) or "").strip(),
                "award_year": (row.get(f_year) or "").strip(),
                "award_amount": (row.get(f_amount) or "").strip(),
                "topic_code": (row.get(f_topic) or "").strip(),
                "abstract": (row.get(f_abstract) or "").strip(),
                "award_date": (row.get(f_date) or "").strip(),
                "agency": (row.get(f_agency) or "").strip(),
                "branch": (row.get(f_branch) or "").strip() if f_branch else "",
                "phase": (row.get(f_phase) or "").strip(),
                "research_area_keywords": (
                    (row.get(f_keywords) or "").strip() if f_keywords else ""
                ),
            }


def filter_and_split(csv_path: Path) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {k: [] for k in AGENCY_FILES}
    seen = 0
    kept = 0
    for rec in iter_records(csv_path):
        seen += 1
        if seen % 50000 == 0:
            print(f"  ...scanned {seen:,} rows; kept {kept:,}", flush=True)
        phase = rec["phase"].lower().replace("-", " ").strip()
        if phase not in {"phase i", "phase 1"}:
            continue
        agency = normalize_agency(rec["agency"], rec["branch"])
        if agency is None:
            continue
        year = parse_year(rec["award_year"])
        if year is None or not (YEAR_MIN <= year <= YEAR_MAX):
            continue
        out = {
            "company_name": rec["company_name"],
            "award_title": rec["award_title"],
            "award_year": rec["award_year"],
            "award_amount": rec["award_amount"],
            "topic_code": rec["topic_code"],
            "abstract": rec["abstract"],
            "award_date": rec["award_date"],
            "agency": agency,
            "branch": rec["branch"],
            "research_area_keywords": rec["research_area_keywords"],
        }
        buckets[agency].append(out)
        kept += 1
    print(f"  total rows scanned: {seen:,}; total kept: {kept:,}", flush=True)
    return buckets


def write_subsets(buckets: dict[str, list[dict]]) -> dict[str, dict]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    for agency, records in buckets.items():
        path = AGENCY_FILES[agency]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        short = [
            {
                "company_name": r["company_name"],
                "award_year": r["award_year"],
                "abstract_length": len(r["abstract"]),
            }
            for r in records
            if len(r["abstract"]) < 100
        ]
        summary[agency] = {
            "count": len(records),
            "short_abstract_count": len(short),
            "short_abstract_examples": short[:10],
            "output_file": str(path.relative_to(ROOT).as_posix()),
        }
        print(
            f"  wrote {len(records):,} {agency} records "
            f"({len(short):,} flagged short) -> {path}",
            flush=True,
        )
    return summary


_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-']+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def ngrams(tokens: list[str], n: int) -> Iterator[tuple[str, ...]]:
    for i in range(len(tokens) - n + 1):
        yield tuple(tokens[i:i + n])


def is_meaningful_phrase(gram: tuple[str, ...]) -> bool:
    if not gram:
        return False
    if all(t in STOPWORDS for t in gram):
        return False
    if gram[0] in STOPWORDS and gram[-1] in STOPWORDS:
        return False
    if any(len(t) < 2 for t in gram):
        return False
    return True


def first_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    parts = _SENT_SPLIT_RE.split(text, maxsplit=1)
    return parts[0].strip()


def opening_signature(sentence: str) -> str:
    toks = tokenize(sentence)[:6]
    return " ".join(toks) if toks else ""


def count_signal_hits(text_lower: str, signals: list[str]) -> dict[str, int]:
    return {s: text_lower.count(s) for s in signals if text_lower.count(s) > 0}


def technical_framing_by_agency(
    abstracts_by_agency: dict[str, list[str]]
) -> dict[str, dict]:
    """Top trigrams per agency, after stopword filtering, as a proxy for
    agency-specific technical framing."""
    out: dict[str, dict] = {}
    for agency, texts in abstracts_by_agency.items():
        c: Counter = Counter()
        for t in texts:
            toks = tokenize(t)
            for g in ngrams(toks, 3):
                if is_meaningful_phrase(g):
                    c[" ".join(g)] += 1
        out[agency] = {
            "top_trigrams": [
                {"phrase": p, "count": n} for p, n in c.most_common(50)
            ],
        }
    return out


def language_pattern_analysis(buckets: dict[str, list[dict]]) -> dict:
    abstracts_by_agency = {
        agency: [r["abstract"] for r in recs if r["abstract"]]
        for agency, recs in buckets.items()
    }
    all_abstracts: list[str] = []
    for texts in abstracts_by_agency.values():
        all_abstracts.extend(texts)

    print(
        f"  analyzing {len(all_abstracts):,} abstracts across "
        f"{len(abstracts_by_agency)} agencies",
        flush=True,
    )

    phrase_counts: Counter = Counter()
    opening_counts: Counter = Counter()
    knowledge_hits: Counter = Counter()
    product_hits: Counter = Counter()
    knowledge_doc_hits = 0
    product_doc_hits = 0

    for i, abstract in enumerate(all_abstracts):
        if i % 5000 == 0 and i:
            print(f"    ...processed {i:,} abstracts", flush=True)
        toks = tokenize(abstract)
        for n in (2, 3, 4):
            for g in ngrams(toks, n):
                if is_meaningful_phrase(g):
                    phrase_counts[" ".join(g)] += 1
        opening = opening_signature(first_sentence(abstract))
        if opening:
            opening_counts[opening] += 1
        low = abstract.lower()
        any_k = False
        any_p = False
        for s in KNOWLEDGE_SIGNALS:
            n = low.count(s)
            if n:
                knowledge_hits[s] += n
                any_k = True
        for s in PRODUCT_SIGNALS:
            n = low.count(s)
            if n:
                product_hits[s] += n
                any_p = True
        if any_k:
            knowledge_doc_hits += 1
        if any_p:
            product_doc_hits += 1

    return {
        "_meta": {
            "version": "v1",
            "status": "REQUIRES_HUMAN_REVIEW",
            "note": (
                "Initial taxonomy. Knowledge/product keyword lists are Tom's "
                "v1 spec — refine after first review. N-gram top-50 is raw "
                "frequency with stopword filtering only; expect noise."
            ),
            "year_range": [YEAR_MIN, YEAR_MAX],
            "phase": "Phase I",
            "agencies": list(buckets.keys()),
            "total_abstracts": len(all_abstracts),
        },
        "top_50_phrases": [
            {"phrase": p, "count": n}
            for p, n in phrase_counts.most_common(50)
        ],
        "top_opening_sentence_structures": [
            {"opening_first_six_tokens": p, "count": n}
            for p, n in opening_counts.most_common(30)
        ],
        "knowledge_vs_product_signals": {
            "knowledge_signals_v1": KNOWLEDGE_SIGNALS,
            "product_signals_v1": PRODUCT_SIGNALS,
            "knowledge_signal_total_hits": dict(knowledge_hits),
            "product_signal_total_hits": dict(product_hits),
            "abstracts_with_any_knowledge_signal": knowledge_doc_hits,
            "abstracts_with_any_product_signal": product_doc_hits,
            "abstracts_with_neither": (
                len(all_abstracts) - knowledge_doc_hits - product_doc_hits
                + sum(
                    1 for a in all_abstracts
                    if any(s in a.lower() for s in KNOWLEDGE_SIGNALS)
                    and any(s in a.lower() for s in PRODUCT_SIGNALS)
                )
            ),
        },
        "technical_framing_by_agency": technical_framing_by_agency(
            abstracts_by_agency
        ),
    }


def main() -> int:
    if not RAW.exists():
        print(
            f"ERROR: raw CSV not found at {RAW}\n"
            f"Download manually from https://www.sbir.gov/awards "
            f"(link 'with award abstracts') and save to that path.",
            file=sys.stderr,
        )
        return 1

    print(f"[1/3] Reading {RAW} and splitting by agency/phase/year...", flush=True)
    buckets = filter_and_split(RAW)

    print("[2/3] Writing per-agency JSON subsets...", flush=True)
    summary = write_subsets(buckets)

    print("[3/3] Running language-pattern analysis (v1)...", flush=True)
    PATTERNS.mkdir(parents=True, exist_ok=True)
    patterns = language_pattern_analysis(buckets)
    patterns_path = PATTERNS / "language_patterns.json"
    with open(patterns_path, "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)
    print(f"  wrote {patterns_path}", flush=True)

    print("\n=== SUMMARY ===", flush=True)
    for agency, info in summary.items():
        print(
            f"  {agency}: {info['count']:,} Phase I awards "
            f"({YEAR_MIN}-{YEAR_MAX}); {info['short_abstract_count']:,} "
            f"flagged short (<100 chars) -> {info['output_file']}",
            flush=True,
        )
    print(f"  Patterns: {patterns_path.relative_to(ROOT).as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
