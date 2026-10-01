"""FR-16: evaluate every LLM answer. Scores are 0..1.
 - grounding:         share of claims supported by retrieved evidence
 - citation_accuracy: share of [n] citations whose source actually overlaps the sentence citing it
 - relevance:         semantic similarity between question and answer
 - completeness:      how many of the top retrieved sources the answer actually used
"""
import re

import numpy as np

from app.ai import llm
from app.ai.embeddings import embed_query, embed_texts

STOP = set("""a an the of to in on for and or is are be by with as at that this it its from shall must should may can
not any all such which who whom their they them there than then into under over per has have had been was were will
would also other these those where when while about above below between each more most no nor only own same so too very""".split())
CITE_RE = re.compile(r"\[(\d+)\]")


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 2}


def _sentences(answer: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", answer) if len(s.strip()) > 20]


def _overlap(sentence: str, evidence_tokens: set[str]) -> float:
    toks = _tokens(CITE_RE.sub("", sentence))
    return len(toks & evidence_tokens) / len(toks) if toks else 1.0


def _llm_grounding(answer: str, sources: list[str]):
    ctx = "\n\n".join(f"[{i + 1}] {s}" for i, s in enumerate(sources))
    prompt = f"""You are a strict fact-checker. Break the ANSWER into atomic factual claims and check each against SOURCES only.
Return JSON: {{"claims":[{{"claim":"...","supported":true|false}}]}}

SOURCES:
{ctx}

ANSWER:
{answer}"""
    data = llm.generate_json(prompt)
    claims = data.get("claims", [])
    if not claims:
        return None
    sup = sum(1 for c in claims if c.get("supported"))
    return sup / len(claims), len(claims) - sup


def evaluate(question: str, answer: str, hit_texts: list[str]) -> dict:
    n = len(hit_texts)
    cited = sorted({int(m) for m in CITE_RE.findall(answer)})
    valid = [c for c in cited if 1 <= c <= n]
    ev_tokens = set().union(*[_tokens(t) for t in hit_texts]) if hit_texts else set()
    sents = _sentences(answer)

    # citation accuracy: each cited sentence must overlap with the source it cites
    checks = []
    for s in sents:
        for c in CITE_RE.findall(s):
            c = int(c)
            checks.append(1.0 if 1 <= c <= n and _overlap(s, _tokens(hit_texts[c - 1])) >= 0.3 else 0.0)
    citation_accuracy = float(np.mean(checks)) if checks else 0.0

    method, grounding, unsupported = "lexical", None, 0
    if llm.is_available() and hit_texts and answer:
        try:
            res = _llm_grounding(answer, hit_texts)
            if res:
                grounding, unsupported, method = res[0], res[1], "llm_judge"
        except llm.LLMUnavailable:
            pass
    if grounding is None:
        scores = [_overlap(s, ev_tokens) for s in sents] or [0.0]
        unsupported = sum(1 for x in scores if x < 0.6)
        grounding = 1 - unsupported / len(scores)

    qv, av = embed_query(question), embed_texts([answer])[0]
    relevance = float(max(0.0, min(1.0, np.dot(qv, av))))
    completeness = min(1.0, len(valid) / max(1, min(n, 3)))
    return {
        "grounding": round(grounding, 3), "citation_accuracy": round(citation_accuracy, 3),
        "relevance": round(relevance, 3), "completeness": round(completeness, 3),
        "retrieved_evidence": n, "unsupported_claims": int(unsupported), "method": method,
    }
