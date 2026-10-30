# Knowledge base - AIM Healthcare Hackathon Vienna 2026, Track 3 (EHDS)

Local, structured copies of everything the challenge depends on, so nothing is refetched mid-build.
Challenge repo clone: `../../challenge/` (upstream: https://github.com/AIM-Austria/TRACK-3-ehds, single commit `ba0ff54`).

| File | What | Source | Captured |
|---|---|---|---|
| `ehds-articles/art-NN.md` | Verbatim text of Regulation (EU) 2025/327 Chapter IV articles the brief cites, plus Art. 61 | eur-lex ELI page, firecrawl_scrape | 2026-10-29 |
| `ehds-articles/art-55.md`, `art-105.md` | Verbatim Art. 55 (HDAB designation, 55(6) deadline 26 March 2027) and Art. 105 (application dates: Chapter IV from 26 March 2029) for the research files | eur-lex ELI page, built-in browser | 2026-10-30 |
| `hackathon-notes.md` | Everything from docs.healthcare-hackathon.eu that matters for Track 3 and for us as a team | docs site print page + teams page, firecrawl_scrape | 2026-10-29 |

Full page captures stay out of the repo (house rule: quotes and manifest only). Capture manifest at the bottom.

## Articles and why each one matters

All in Chapter IV "Secondary use". Section 1 = general conditions, Section 2 = governance, Section 3 = access.

| Art. | Title | Used for |
|---|---|---|
| 53 | Purposes for which electronic health data can be processed for secondary use | Every APPROVE cites it. Allowed purposes: (a) public health, (b) policymaking by public bodies, (c) official statistics, (d) education/teaching, (e) scientific research incl. (e)(ii) training/testing algorithms and AI, (f) improving delivery of care. **53(2): purposes (a), (b), (c) are reserved for public sector bodies** - a private applicant claiming them fails. |
| 54 | Prohibited secondary use | Every REJECT. (a) decisions detrimental to persons, (b) job offers, insurance premiums, credit, discrimination, (c) advertising or marketing, (d) harmful products incl. tobacco and **nicotine products**, alcohol, weapons, (e) against national ethics law. R02 = 54(b), R04 = 54(c), R06 = 54(a)+(b), R10 = 54(d). |
| 61 | Duties of health data users | Not cited by the brief. **61(3) is the re-identification ban** that expected.json's R06 reason leans on ("matching with an employee list would re-identify people"). 61(2): no sharing out of the SPE with third parties. 61(4): outputs must be anonymous. |
| 66 | Data minimisation and purpose limitation | 66(2): give anonymised data when that achieves the purpose. 66(3): pseudonymised only when the applicant has sufficiently demonstrated anonymised data cannot. This is the SPE-vs-statistics switch: R05 passes it, R09 fails it. |
| 67 | Health data access applications | What an application must contain, incl. 67(2)(e): the justification why pseudonymised rather than anonymised. The brief allows citing it as an extra. |
| 68 | Data permit | Criteria the access body checks, 68(1)(c) = sufficient justification for pseudonymised data. **68(3) second subparagraph is the legal basis for the R09 downgrade**: when permit requirements are not met but Art. 69 requirements are, the body may answer with anonymised statistics instead, if the applicant agrees. 68(9): a refusal must come with a justification. 68(10): what a permit must list. |
| 69 | Health data request | The statistics route. 69(1): response only in anonymised statistical format, applicant never touches the data. 69(2): required contents of a request. Every APPROVE_STATISTICAL cites it. |
| 71 | Right to opt out | 71(1) opt out at any time, no reason. 71(3): opted-out data is not made available for permits or requests approved after the opt-out. 71(4): national-law exception for public bodies only. The brief allows citing it as an extra; 839 of 20,000 patients are opted out. |
| 73 | Secure processing environment | 73(1)(a)-(f): access restricted to named persons, minimise copy/removal risk, unique user IDs, access logs kept at least a year. **73(2) second subparagraph: the body reviews every download request so only non-personal data (incl. anonymised statistics) leaves the SPE** - this is the download block the demo must show. |

## Decision rules in the brief, mapped to the law

| Brief rule | Decision | Articles | Law behind it |
|---|---|---|---|
| 1. Prohibited purpose | REJECT | 54 | 54(a)-(e) |
| 2. Health data request | APPROVE_STATISTICAL | 53, 69 | 53(1) purpose + 69(1) format |
| 3. Access application that shows why statistics are not enough (R05) | APPROVE_SPE | 53, 66, 68, 73 | 66(3) + 68(1)(c) justified, permit under 68, access only via 73 |
| 4. Any other access application (R09) | APPROVE_STATISTICAL | 53, 66, 69 | 66(2) anonymised suffices, downgrade route 68(3) 2nd subpara, answered under 69 |

Metric tolerance: adding Art. 67 or 71 to a correct answer is accepted; any other extra article counts as wrong.

## Hard rules for the build (do not drift)

1. **Articles list = exactly the brief's set, plus at most 67 or 71.** The "Correct decisions" metric compares our articles with `expected.json` and tolerates only Art. 67 or 71 as extras. Art. 61 (re-identification, R06) and Art. 68(3) (downgrade route, R09) are legally right but **go in the reason text only, never in the articles array**, or the request counts as a wrong decision.
2. Decide in the brief's order: 54 first, then request vs application, then 66 justification.
3. Opted-out patients are excluded from every count and every denominator, and never copied into an SPE.
4. Every group the request names appears in the output, empty ones as `<10`.
5. The reason text is what the two legal jurors read. Quote the article paragraph that applies (54(b), 54(c), 54(d), 66(2), 66(3), 68(3), 73(2)); the KB has the exact wording.

## Things the brief leaves implicit (from the article text)

- 53(2): a private company whose stated purpose is "official statistics" or "policymaking" does not qualify; those purposes belong to public bodies. The jury's hidden requests may test this.
- 54(a) needs the decision to have legal, social or economic effect on the person. Internal research that never acts on individuals is not 54(a).
- 68(9): every REJECT must carry a justification to the applicant. The brief's "show the decision and the reason" mirrors this.
- 73(1)(e): access logs for at least one year. Cheap to add to the SPE and good for the "would an access body use this" criterion.
- 71(3) phrasing: the exclusion applies to permits and requests approved after the opt-out. In our synthetic data every request is new, so every opted-out patient is excluded everywhere, as the brief says.

## Capture manifest (2026-10-29, Firecrawl)

| URL | Status | Credits | Size | Note |
|---|---|---|---|---|
| https://eur-lex.europa.eu/eli/reg/2025/327/oj/eng | 200 | 1 | 439,167 chars | whole regulation; article slices via `slice_articles.py` (headings use a non-breaking space) |
| https://docs.healthcare-hackathon.eu/teams.html | 200 | 1 | 4,074 chars | team roster only |
| https://docs.healthcare-hackathon.eu/print.html | 200 | 1 | 17,005 chars | whole docs book |

All three screened by injection-screener before anything read them: clean.
