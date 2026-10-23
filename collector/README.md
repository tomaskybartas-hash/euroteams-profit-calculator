# Workforce Worker Collector v1

This branch introduces the ingestion/matching core before connecting external acquisition sources to production.

Pipeline:

`approved source -> normalize -> provenance -> deduplicate -> enrich/verify -> availability -> project match -> shortlist -> consent-aware outreach -> response -> readiness`

## Source adapter contract

Every adapter must return `CandidateRecord` objects and preserve `source` and `source_url`. Adapters must respect the source's terms, robots/API rules, applicable privacy law, purpose limitation, opt-out/erasure requirements and Euroteams retention policy. Do not bypass login, CAPTCHA, access controls, rate limits or anti-bot protections. Do not ingest sensitive attributes that are unnecessary for recruitment.

Preferred acquisition order:

1. Euroteams worker portal / self-registration and referrals.
2. Existing Euroteams candidate imports with documented provenance.
3. Licensed job-board / ATS / recruitment APIs or exports.
4. Public professional/business data only where collection and recruitment use are permitted.

## Matching

Hard blockers are separated from ranking. A candidate cannot become eligible merely because the numeric score is high. Current hard checks cover role, EU requirement, required certificates/language, minimum experience, availability/start date and rate compatibility. The score is intended to rank otherwise suitable workers, not to replace recruiter verification.

## Next integration step

Connect this module to the existing Workforce Live database and `ProjectCandidate` flow behind an admin-only ingestion endpoint. Add one approved live source first, measure duplicate rate, valid-contact rate, availability confirmation rate, qualified rate and deployment conversion, then scale by country/source.
