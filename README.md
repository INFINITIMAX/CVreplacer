# CVreplacer

A local tool that matches Romanian job listings against your CV, ranks them, and tells you what you're missing.

> **Status: early development.** Profile extraction works; harvesting, scoring and the local app are being built.

## Why

Job hunting has three structural problems that search engines don't solve:

1. **Titles lie.** "Junior Developer" that requires 3 years of experience is common, so you read dozens of listings to discard most of them.
2. **Freshness decides, but nobody shows it.** Hundreds apply to an entry-level post; applying in the first 24-48 hours matters far more than a marginally better match. No aggregator tells you "this appeared today and fits you".
3. **You never learn what you lack.** You apply, you're rejected, you don't know why. The information exists across listings — nobody aggregates it.

## How it works

The core idea: **you don't need the job description to filter, you need it to rank.**

```
~89,000 listings in the source index
   ↓  queries generated from your profile          free
~2,000 raw candidates
   ↓  seen · location · dedup · company cap        free, SQLite
~300 candidates
   ↓  fetch description for these only             slow, polite, cached
~300 with full text
   ↓  years required, parsed from the text         free
~150 plausible
   ↓  LLM scoring                                  the only paid step
ranked list with reasons
```

You fetch 300 pages, not 89,000. Nothing expensive runs before everything cheap has.

## Design decisions worth stealing

**Two-layer profile.** `cv` is what a recruiter can verify; `extra` is what's true but absent from your CV. **Scoring only ever reads `cv`** — a score based on something the recruiter cannot see is a lying score. `extra` feeds a separate report: *"you keep missing listings that ask for X, and you do have X — it just isn't on your CV."*

**Evidence is mandatory.** Every coverage claim the model makes must point at a concrete profile element. Coverage without evidence is treated as zero. An inflated score sends you to interviews you fail, which costs more than a missed listing.

**Domain-aware experience matching.** "3+ years experience" and "3 years of Python" are different questions. Years are compared per domain, not against a single global number — otherwise career changers get filtered out wrongly.

**Own your freshness data.** The source's date field is the indexing timestamp, not the posting date — an entire 1,500-listing sample lands inside a 100-second window. So the tool records `first_seen` itself on every run. After a week you have better freshness data than the source.

**Hard cost ceiling.** A `--dry-run` counts what would be sent and estimates the cost before anything is spent, and a configured cap stops a run rather than surprising you on the bill.

## Stack

Python · FastAPI · SQLite · Anthropic Claude API with structured outputs. Runs locally; no cloud, no accounts.

## Commands

```
python -m cvreplacer harvest          collect listings (free)
python -m cvreplacer score --dry-run  count and estimate cost, send nothing
python -m cvreplacer score            the real run
python -m cvreplacer serve            local app
```

## Privacy

Your CV, the extracted profile, the database and the page cache all live in `data/`, which is excluded from git. Nothing personal is committed. The only data that leaves your machine is the listing text and profile sent to the model for scoring.

## Sources

Listings come from [peviitor.ro](https://peviitor.ro), an open-source Romanian job search engine whose API is offered deliberately. Sources that asked not to be used are not used — `jobs.ro` declares `Content-Signal: ai-train=no` and is excluded by design.

## Licence

MIT — see [LICENSE](LICENSE).
