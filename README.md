# CIVITAS Ω — Constitutional Public Evidence Fabric

**Open-source Python reference kernel · local/offline evidence baseline · not production deployed**

CIVITAS Ω explores a governed alternative to generic OSINT aggregators: discover publicly documented data services; qualify exact operations against provider rights and a bounded operator grant; compile research questions into reproducible evidence plans; preserve primary-source provenance; and report contradiction rather than invent consensus.

**Constitutional distinction:** discovery ≠ permission; retrieval ≠ evidence; evidence ≠ scientific truth.

## Current scope

- Git-source-pinned catalog discovery, staging and quarantine.
- SQLite capability registry and deterministic local evidence plans.
- Separate operator permissions and source-bound rights reviews.
- Six fixed read-only provider templates (not live-qualified).
- Synthetic observation comparison, provenance receipts and local validation.
- Python 3.11+ standard-library runtime; reference suite previously reported 77/77 offline tests passing.

**Limitations:** This GitHub repository is being bootstrapped from the validated R3 candidate package. Until the candidate's entire source tree and tests are committed and GitHub CI runs, do not treat this remote repository as an independently verified software release. Anonymous-provider access, legal reuse rights, anti-SSRF host egress, real measurement independence, hosted MCP and CodexStation integration remain OPEN.

## Reproduce after source synchronization

```bash
python3 -m unittest discover -s tests -v
python3 -m civitas.cli --db demo.db ingest --file fixtures/README_SAMPLE.md
python3 -m civitas.cli --db demo.db stats
python3 -m civitas.cli --db demo.db verify
```

The repository's intended structure is `civitas/`, `tests/`, `fixtures/`, `docs/`, plus `AGENTS.md` and publication policies. The local R3 candidate contains these files; this bootstrap commit alone does not.

## Design principles

1. **Source-first:** Git commit, listing identity and documentation provenance never imply permission.
2. **Fail-closed:** unknown rights, scope, rate limit or host network destination block execution.
3. **Evidence diversity:** ten syndicators of one primary measurement are not ten independent sources.
4. **Corrigibility:** revocation, bounded budgets, explicit stops and no implicit authority promotion.
5. **Open claims:** local tests are not live-network tests or scientific validation.

## Upstream and specifications

Seed directory: https://github.com/public-apis/public-apis

OpenAPI: https://spec.openapis.org/oas/v3.1 · PROV-O: https://www.w3.org/TR/prov-o/ · DCAT 3: https://www.w3.org/TR/vocab-dcat-3/

CIVITAS original software is intended to be MIT licensed in the source package. Third-party API and dataset terms remain independent. **The private experimental code belongs in the separate private lab repository**, not this public surface.
