#!/usr/bin/env python3
"""Deterministic resume-fit score (0-100) with breakdown and caps. rubric_version = 1."""
from __future__ import annotations
import json, re, sys, unicodedata

RUBRIC_VERSION = 1
SYN_GROUPS = [
    {"kubernetes", "k8s", "eks", "gke", "aks", "openshift"}, {"terraform", "tf", "opentofu"},
    {"infrastructure as code", "iac"}, {"amazon web services", "aws"}, {"google cloud platform", "gcp", "google cloud"},
    {"microsoft azure", "azure"}, {"postgresql", "postgres", "psql"}, {"javascript", "js"}, {"typescript", "ts"},
    {"python", "py"}, {"go", "golang"}, {"machine learning", "ml"}, {"artificial intelligence", "ai"},
    {"large language model", "large language models", "llm", "llms"}, {"generative ai", "genai", "gen ai"},
    {"retrieval augmented generation", "rag"}, {"natural language processing", "nlp"},
    {"continuous integration", "ci cd", "cicd", "ci/cd"}, {"llm inference", "inference serving", "model serving"},
    {"docker", "containers", "containerization"}, {"mlops", "ml ops"},
]
LADDER = [("intern", 0), ("junior", 1), ("associate", 1), ("entry", 1), (" ii", 2), (" 2", 2), ("mid", 2), ("senior", 3), ("sr", 3),
          ("lead", 4), ("staff", 4), ("principal", 5), ("distinguished", 6), ("architect", 4), ("manager", 4),
          ("director", 6), ("head of", 6), ("vp", 7), ("vice president", 7), ("chief", 7)]
LEVEL_NAMES = {"intern": 0, "junior": 1, "mid": 2, "senior": 3, "staff": 4, "lead": 4, "principal": 5, "director": 6, "vp": 7}

def canon(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower().replace("+", "p").replace("#", "sharp")
    return " ".join(re.sub(r"[^a-z0-9/]+", " ", s).replace("/", " ").split())

_SYN: dict[str, set[str]] = {}
for _g in SYN_GROUPS:
    _c = {canon(x) for x in _g}
    for _m in _c:
        _SYN.setdefault(_m, set()).update(_c)

def variants(term: str) -> set[str]:
    return _SYN.get(canon(term), {canon(term)})

def resume_terms(master_md: str) -> set[str]:
    words, grams = canon(master_md).split(), set()
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            grams.add(" ".join(words[i:i + n]))
    return grams

def covered(term: str, grams: set[str]) -> float:
    vs = variants(term)
    if vs & grams:
        return 1.0
    for t in vs:
        parts = t.split()
        if len(parts) > 1 and all(p in grams for p in parts):
            return 0.6
    return 0.0

def seniority_level(title: str) -> int:
    t = " " + canon(title) + " "
    best = 2
    matched = False
    for key, lvl in LADDER:
        k = key.strip()
        if k and (" " + k + " ") in t:
            if not matched or lvl > best:
                best = lvl
            matched = True
    return best

def _ratio_seniority(job_title: str, resume_level: str) -> float:
    d = seniority_level(job_title) - LEVEL_NAMES.get(resume_level, 3)
    return {0: 1.0, 1: 0.75, -1: 0.85}.get(d, 0.45 if abs(d) == 2 else 0.15)

def score(master_md: str, job: dict, cfg: dict, age_days: float | None) -> dict:
    w = dict(cfg.get("weights") or {})
    grams = resume_terms(master_md)
    must = [m for m in (job.get("must_have") or []) if m]
    nice = [n for n in (job.get("nice_to_have") or []) if n]
    must_cov = sum(covered(m, grams) for m in must) / len(must) if must else 0.75
    nice_cov = sum(covered(n, grams) for n in nice) / len(nice) if nice else 0.5
    missing = [m for m in must if covered(m, grams) == 0.0]
    loc = job.get("location_key") or "unknown"
    if job.get("remote") == "remote" or loc.startswith("remote") or loc in (cfg.get("home_metro") or []):
        loc_ratio = 1.0
    elif loc in (cfg.get("ok_metros") or []):
        loc_ratio = 0.7
    elif loc == "unknown":
        loc_ratio = 0.5
    else:
        loc_ratio = 0.0
    tags = {t.lower() for t in (job.get("domain_tags") or [])}
    targets = {t.lower() for t in (cfg.get("target_domains") or [])}
    dom_ratio = 1.0 if tags & targets else (0.5 if not tags else 0.25)
    if age_days is None:
        rec_ratio = 0.5
    else:
        rec_ratio = 1.0 if age_days <= 7 else 0.8 if age_days <= 21 else 0.5 if age_days <= 45 else 0.2
    target = cfg.get("target_base") or 0
    cm = job.get("comp_max")
    if cm is None or not target:
        comp_ratio = 0.6
    else:
        comp_ratio = 1.0 if cm >= target else 0.7 if cm >= 0.9 * target else 0.35 if cm >= 0.8 * target else 0.0
    ratios = {"must_have": must_cov, "skills": nice_cov, "seniority": _ratio_seniority(job.get("title", ""), cfg.get("resume_seniority", "senior")),
              "location": loc_ratio, "domain": dom_ratio, "recency": rec_ratio, "comp": comp_ratio}
    comps = {k: {"weight": w.get(k, 0), "ratio": round(v, 4), "points": round(w.get(k, 0) * v, 2)} for k, v in ratios.items()}
    total = sum(c["points"] for c in comps.values())
    caps, notes = [], []
    if job.get("clearance_required") and not cfg.get("holds_clearance") and not job.get("clearance_eligible_ok"):
        caps.append("clearance_not_held"); total = min(total, 25)
    if (job.get("citizenship_required") and not cfg.get("work_authorized_us", True)) or \
       (job.get("sponsorship_unavailable") and cfg.get("needs_sponsorship")):
        caps.append("citizenship_or_sponsorship"); total = min(total, 20)
    if must and must_cov < 0.5:
        caps.append("must_have_floor"); total = min(total, 45)
    if missing:
        notes.append("missing must-have: " + ", ".join(missing[:5]))
    if cm is None:
        notes.append("no compensation range posted")
    return {"total": int(round(total)), "components": comps, "caps": caps, "notes": notes,
            "must_have_coverage": round(must_cov, 4), "missing_must_haves": missing, "rubric_version": RUBRIC_VERSION}

def main(argv=None):
    import argparse, pathlib
    ap = argparse.ArgumentParser(description="fit score")
    ap.add_argument("--master", required=True); ap.add_argument("--job", required=True)
    ap.add_argument("--config-json", required=True); ap.add_argument("--age-days", type=float)
    a = ap.parse_args(argv)
    print(json.dumps(score(pathlib.Path(a.master).read_text(), json.loads(pathlib.Path(a.job).read_text()),
                           json.loads(pathlib.Path(a.config_json).read_text()), a.age_days)))

if __name__ == "__main__":
    main()
