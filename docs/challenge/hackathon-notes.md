# AIM Healthcare Hackathon Vienna 2026 - notes for Track 3 (EHDS)

Source: https://docs.healthcare-hackathon.eu (whole book via print.html + teams.html), captured 2026-10-29 with Firecrawl, screened clean. Tracks 1 and 2 left out on purpose.

## Our team

**Team Oguz & Arda**: Oguz Nacar and Arda Sarikaya. Two people. The registration list also showed Lei Pei and Vera Pils, but they are not in the team (Arda, 2026-10-29). The list typed into the submission form is what counts.

## Deadlines and schedule

| When | What |
|---|---|
| Thu 29 Oct 18:30 | Hacking starts |
| Thu 22:00 | IBM building closes; we keep building from outside until the pitch (Arda's call). Take laptops. |
| Fri 30 Oct 09:00 | Doors open, mentor rounds |
| Fri 13:00 | Clinical panel |
| **Fri 15:00** | **Submission deadline, one per team** |
| Fri 16:00 | Top 3 per track pitch on stage |
| Fri 18:00 | Results and awards |

Venue: IBM Austria, Obere Donaustraße 95, 1020 Vienna. Badge back in the box at the 11th-floor reception when leaving Thursday. Thursday: be inside before 18:00. The venue closing is a building rule, not a work stop: we continue building after 22:00 and through to the presentation.

## Submission (Google Form)

Form: https://docs.google.com/forms/d/e/1FAIpQLScZXc_XL3Nwd4crtbbtTG-ZS4p7QuvmVhXo_5mXsWG2ytUcRw/viewform

1. Team name + all member names.
2. Track (3).
3. **Video, max 2 minutes**, showing the demo. Say what works and what does not.
4. **Public repository** link with run instructions. README must explain the technical architecture: components built, how they work together, which models or services are used.
5. **Metric results** on the 10 requests, measured as the track README describes (decisions 10/10, numbers 6/6, leaks 0, consistency 10/10 over 3 runs, slowest under 60 s).

Our repo goes public when we submit. Synthetic data only; cloud AI services are allowed, own accounts and keys.

## Jury (reviews all submissions Friday, picks top 3 per track)

| Name | Where | Relevance for Track 3 |
|---|---|---|
| Georg Dorffner | MedUni Vienna, Institute for AI | AI quality criterion |
| Jürgen Grafeneder (video) | MedUni Vienna, Emergency Medicine, AKH | clinical approach |
| Immo Regener (remote from 16:00) | PwC Deutschland, cloud provider risk and compliance | **privacy, SPE, download block, compliance story** |
| Martina Edlinger | Wolf Theiss, corporate, M&A and life sciences | **legal: article citations, Art. 54 reasoning** |
| Silvia Hecher | A1 Telekom Austria, healthcare business development | would an access body use this |
| Kerstin Zimmermann | Federal Ministry for Innovation, Mobility and Infrastructure | public-sector usability |
| Katja Österreicher | Vinzenz Gruppe, product owner Hallo Gesundheit | applicant and staff UX |

Two of seven are law/compliance people. The decision reasoning and the SPE enforcement will be read by experts.

Mentors (Friday morning floor): Georg Melzer-Venturi (eutema, EU projects), Marilies Dolezal (Evangelisches Krankenhaus Wien, operations), Katja Österreicher.

## Tools and credits every participant gets

| Tool | What | How | Status for us |
|---|---|---|---|
| **Exoscale (A1 Digital)** | Credit for a 2-node Kubernetes cluster for up to 2 weeks; covers compute, Object Storage and a database. A5000 GPU instances on request via Discord #gpu-access | https://portal.exoscale.com/register?coupon=healthcare-hackathon-vie-2026 | **Arda claimed the credits and created the console account (2026-10-29).** Available for a hosted demo or DB. |
| Devin Max (Cognition) | 200 USD plan per person | Claim at https://trydevin.ai with the Luma ticket email; Miki Huber at the entrance activates after check-in | not claimed as far as noted |
| Lovable | 100 credits per person, code `COMM-CLINICAL-8JAN`, redeem on an event day, expires the day after; currency restriction at checkout | https://lovable.dev | not claimed as far as noted |
| IBM Bob | 100 Bobcoins per person on the hackathon Enterprise instance (`ibm-hackathon-...`), standalone app from https://bob.ibm.com/download, needs an IBMid; more coins via ivan.birkmaier@ibm.com. Recommendation, not a requirement. Exporting the Bob task session report into the repo helps the jury assess the work | invite by email | not claimed as far as noted |
| n8n cloud licences | mentioned, no details in the book | - | - |
| Espressif boards | 25 to build with | on site | irrelevant for Track 3 |

GPU note: the per-group tutorial carries the SSH key and API credentials; never post them in any channel.

## Prizes

Per track three winners; the track partner puts up the prize fund. Extra prizes: Devin tokens, Garmin Venu 4, 15 Espressif boards, 250 EUR Hetzner credit, an AI Factory Austria coworking ticket, Neo4j Aura credits (300/200/100 USD for the three best Neo4j projects).

## Channels

- Discord (all announcements, #help-desk, #gpu-access): https://discord.gg/NyhXXc8dq
- Livestream (Zoom): https://eu01web.zoom.us/j/64648197875?pwd=3BLaSzWrWNkdjSwsvaS2BIy4ckClu4.1
- Shared media folder (add, never delete): https://drive.google.com/drive/folders/1IMw-_d7NQQnbzzhRnbbw1QH-c6JavlG9
- Organisers: info@healthcare-hackathon.eu; emergencies Sebastian Hochreiter +43 660 5080571, Kyrillus Mehanni +43 676 6433022
- Catering by StV Postgraduale of the ÖH Med Wien; dietary needs to the check-in desk.

## What the docs add beyond the track README

- Nothing technical about Track 3 beyond the clone command. The track README is the whole spec.
- "Say what works and what does not" appears twice (book and track README): honesty in the video is expected, not optional.
- The Bob session report and a public repo are jury-visible artefacts. If we use any AI tooling, a short "how we built it" section in the README is cheap and matches the "if you use AI, does it help" criterion.
