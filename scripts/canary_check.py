#!/usr/bin/env python3
"""Scan generated text (cover letter, answers) for canary words / injected instructions copied from a job description."""
from __future__ import annotations
import json, re, sys
import jd_extract

COMMON_VOCAB = set("""
ability about above accept access across action active actively adapt added additional address advanced agile align already also although
always among analysis analyze analytics application applications applied apply approach architect architecture around artificial assist
automation available aws azure backend balance based become before believe benefits better between beyond bring build building business
candidate candidates capabilities career certification challenge change client clients cloud code coding collaborate collaboration
collaborative communicate communication community company compensation complex compliance computer computing concepts confident
consider consistently container containers continuous contribute contribution create creating critical cross culture current customer
customers data database databases deliver delivering delivery demonstrated deploy deployment design designing develop developer developers
developing development devops different digital directly discuss distributed diverse docker documentation drive driving during dynamic
education effective efficient employees employer enable enabling end engineer engineering engineers ensure enterprise environment
environments equal excellent excited experience expertise familiar familiarity features federal feedback flexible focus following
framework frameworks function functional future generative github global google government growth hands health highly hiring
hybrid impact implement implementation improve improvement include includes including industry information infrastructure initiatives
innovation innovative inside insights integrate integration interest internal interview javascript kubernetes language languages large
leader leaders leadership leading learning level leverage lifecycle linux location looking machine maintain manage management manager
managing market mentor methods metrics microservices minimum mission model models modern monitoring multiple native natural network
numbers offer office open operating operations opportunities opportunity optimize organization others outcomes overall ownership
partner partners people performance pipeline pipelines platform platforms please policies position positions postgres practices
preferred principles problem problems process processes product production products professional program programming project
projects provide providing python quality questions reach real related relevant reliability remote report reporting requirements
required research resources respond responsibilities responsible results resume review salary scalable scale science scripting
security senior service services should significant skills software solutions solve solving source specific stack stakeholders
standards startup statement status storage strategy strong structure success successful support supporting system systems take
talent teams technical technologies technology testing through throughout together tools training transform travel understand
understanding united university update using values variety various vision website welcome willing within without working workplace
written years yourself
qualifications observability resilience stakeholder stakeholders mentorship onboarding responsibilities requirements benefits
compensation overview summary preferred department location employment engineering excellence operational strategic technical
proficiency familiarity accountable collaboration innovative initiative organized detailed motivated proactive
""".split())

def _tokens(s: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z\-]{5,}", s or "")}

def _is_header_line(line: str) -> bool:
    """True for a standalone section-header line (e.g. 'QUALIFICATIONS', 'ABOUT THE ROLE')
    with no lowercase letters at all."""
    s = line.strip().lstrip("#").strip()
    return bool(s) and not re.search(r"[a-z]", s)

def _caps_in_jd(jd_text: str) -> set[str]:
    """ALL-CAPS 6+ char tokens that look like a canary/injection artifact rather than an
    ordinary word that merely happens to sit in a shouty section heading.

    - A token embedded in ordinary (non-header) prose is always collected (minus
      COMMON_VOCAB) — this is the common canary-in-a-sentence case.
    - A token found ONLY on caps-only header lines and nowhere else in the JD is still
      collected: a canary word hidden entirely inside a shouty line (its own line, or a
      header like "REQUIRED SKILLS FROBSCOTTLE") must not evade detection just because
      that line has no lowercase letters.
    - A token on a header line is skipped only when it is COMMON_VOCAB, or it *also*
      appears elsewhere in the JD on an ordinary body line (the heading is just reusing
      normal vocabulary, e.g. a "QUALIFICATIONS" heading plus a "the qualifications for
      this role..." body sentence).
    """
    lines = (jd_text or "").splitlines()
    body_tokens = _tokens("\n".join(ln for ln in lines if not _is_header_line(ln)))
    out = set()
    for line in lines:
        header = _is_header_line(line)
        for t in re.findall(r"\b[A-Z][A-Z\-]{5,}\b", line):
            tl = t.lower()
            if tl in COMMON_VOCAB:
                continue
            if header and tl in body_tokens:
                continue
            out.add(tl)
    return out

def check(generated: str, jd_text: str, master_md: str, profile_md: str = "") -> dict:
    gen, jd = _tokens(generated), _tokens(jd_text)
    known = _tokens(master_md) | _tokens(profile_md) | COMMON_VOCAB
    caps_in_jd = _caps_in_jd(jd_text)
    # Sentence-level injection flagging uses instruction phrases only — an ALL-CAPS run
    # (canary word or shouty header) must never by itself mark a whole sentence/bullet as
    # an injected instruction; that's what caps_in_jd/suspects already handles per-token.
    inj_sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", jd_text or "") if s.strip() and jd_extract.INJECT_PHRASES.search(s)]
    inj_tokens = set().union(*[_tokens(s) for s in inj_sentences]) if inj_sentences else set()
    suspects = sorted(t for t in (gen & jd) - known if t in caps_in_jd or t in inj_tokens)
    injected = [s.strip() for s in inj_sentences][:5]
    return {"suspects": suspects, "injected_phrases": injected, "ok": not suspects and not any(t in gen for t in inj_tokens - known)}

def main(argv=None):
    import argparse, pathlib
    ap = argparse.ArgumentParser(description="canary/injection check")
    ap.add_argument("--generated", required=True); ap.add_argument("--jd", required=True); ap.add_argument("--master", required=True); ap.add_argument("--profile")
    a = ap.parse_args(argv)
    r = check(pathlib.Path(a.generated).read_text(), pathlib.Path(a.jd).read_text(), pathlib.Path(a.master).read_text(),
              pathlib.Path(a.profile).read_text() if a.profile else "")
    print(json.dumps(r)); sys.exit(0 if r["ok"] else 3)

if __name__ == "__main__":
    main()
