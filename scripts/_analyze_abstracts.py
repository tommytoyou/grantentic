#!/usr/bin/env python3
"""Temporary analysis of NSF Phase I funded abstracts. Not committed."""
import json
import re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'training_data' / 'nsf_phase1_all_awards.json'
data = json.load(open(DATA, encoding='utf-8'))

# Keep substantive abstracts only (some rows are near-empty / truncated).
abstracts = [a['abstract'].strip() for a in data if len(a['abstract'].strip()) >= 200]
print(f"Total records: {len(data)} | substantive abstracts (>=200 chars): {len(abstracts)}\n")


def sentences(text):
    text = re.sub(r'\s+', ' ', text)
    # protect a few common abbreviations before splitting
    text = text.replace('U.S.', 'US').replace('e.g.', 'eg').replace('i.e.', 'ie')
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def words(s):
    return re.findall(r"[A-Za-z][A-Za-z'/-]*", s)


def prefix(s, n):
    return ' '.join(w.lower() for w in words(s)[:n])


# ---------------------------------------------------------------------------
# 1. Opening sentence patterns (first-sentence prefixes)
# ---------------------------------------------------------------------------
first_sents = [sentences(a)[0] for a in abstracts if sentences(a)]
open_pref = Counter(prefix(s, 12) for s in first_sents if len(words(s)) >= 6)
print("=" * 78)
print("1. TOP 20 OPENING SENTENCE PATTERNS (first ~12 words of abstract)")
print("=" * 78)
for i, (p, c) in enumerate(open_pref.most_common(20), 1):
    pct = 100 * c / len(first_sents)
    print(f"{i:>2}. [{c:>5}  {pct:4.1f}%]  {p}")
print()


# ---------------------------------------------------------------------------
# helper: most common n-grams within sentences matching trigger terms
# ---------------------------------------------------------------------------
STOP = set("the a an of to and in for is are with this that be by on as it its will can "
           "from at which these those into such their they we our or has have been more "
           "than other also using use used based new approach project research phase".split())

# NSF-template boilerplate tokens — these dominate the corpus because the
# abstracts are NSF-edited public summaries with a fixed structure. Drop any
# n-gram containing one so the genuine technical/content phrases surface.
BOILER = set("small business innovation research sbir sttr phase project broader impact "
             "impact/commercial commercial potential technology transfer award reflects "
             "nsf nsf's deemed worthy statutory mission foundation foundation's "
             "intellectual merit impacts review criteria evaluation funded proposes "
             "propose proposed company".split())


def ngram_counter(sents, n_lo=3, n_hi=5):
    c = Counter()
    for s in sents:
        toks = [w.lower() for w in words(s)]
        for n in range(n_lo, n_hi + 1):
            for i in range(len(toks) - n + 1):
                gram = toks[i:i + n]
                # skip grams that are mostly stopwords
                if sum(1 for g in gram if g in STOP) > n // 2:
                    continue
                # skip grams containing NSF-template boilerplate
                if any(g in BOILER for g in gram):
                    continue
                c[' '.join(gram)] += 1
    return c


all_sents = [s for a in abstracts for s in sentences(a)]

# ---------------------------------------------------------------------------
# 2. Phrases describing TECHNICAL UNKNOWNS / challenges / risk
# ---------------------------------------------------------------------------
unknown_triggers = re.compile(
    r'\b(challeng|unknown|uncertain|risk|hypothes|feasibilit|barrier|bottleneck|'
    r'limitation|gap|unmet|unsolved|unprecedented|technical question|proof[- ]of[- ]concept)\b',
    re.I)
unknown_sents = [s for s in all_sents if unknown_triggers.search(s)]
print("=" * 78)
print(f"2. TECHNICAL-UNKNOWN LANGUAGE  ({len(unknown_sents)} sentences matched)")
print("   Most common 3-5 word phrases within those sentences:")
print("=" * 78)
for i, (p, c) in enumerate(ngram_counter(unknown_sents).most_common(25), 1):
    print(f"{i:>2}. [{c:>4}]  {p}")
print()

# ---------------------------------------------------------------------------
# 3. Phrases describing PHASE I OBJECTIVES
# ---------------------------------------------------------------------------
obj_triggers = re.compile(
    r'\b(objective|aim|goal|will develop|will demonstrate|will design|will investigate|'
    r'this phase i|the phase i|propose to|seeks to|intends to|deliverable|milestone)\b', re.I)
obj_sents = [s for s in all_sents if obj_triggers.search(s)]
print("=" * 78)
print(f"3. PHASE I OBJECTIVE LANGUAGE  ({len(obj_sents)} sentences matched)")
print("   Most common 3-5 word phrases within those sentences:")
print("=" * 78)
for i, (p, c) in enumerate(ngram_counter(obj_sents).most_common(25), 1):
    print(f"{i:>2}. [{c:>4}]  {p}")
print()

# ---------------------------------------------------------------------------
# 4. Distinctive vocabulary of the funded corpus
#    NOTE: dataset has NO rejected proposals, so a true funded-vs-rejected
#    contrast is impossible. We report the highest-signal content terms as the
#    best available proxy.
# ---------------------------------------------------------------------------
print("=" * 78)
print("4. DISTINCTIVE FUNDED VOCABULARY (proxy — NO rejected corpus available)")
print("=" * 78)
content = Counter()
for a in abstracts:
    seen = set(w.lower() for w in words(a))
    for w in seen:
        if w not in STOP and len(w) > 3:
            content[w] += 1  # document frequency
N = len(abstracts)
# terms appearing in a meaningful share of funded abstracts
common_terms = [(w, c) for w, c in content.most_common(60)]
print(f"Top content terms by document frequency (share of {N} funded abstracts):")
for i, (w, c) in enumerate(common_terms[:40], 1):
    print(f"{i:>2}. {w:<18} {100*c/N:4.1f}%")
