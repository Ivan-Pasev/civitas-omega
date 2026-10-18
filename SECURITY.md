# Security Policy

**CIVITAS Ω is not a production-hardened data acquisition service.**

Report suspected vulnerabilities privately to the repository owner (or through GitHub's private vulnerability reporting if enabled). Do not open public issues containing credentials, exploit chains, personal datasets or unreleased provider details.

High-risk surfaces include server-side request forgery (including DNS rebinding), redirects, poisoned catalog listings, provider-rights drift, prompt injection, invalid cache reuse after revocation, fabricated provenance and unreviewed claims of measurement independence.

No hosted MCP server, open network port or external autonomous deployment is authorized by this source tree. Production security requires independently validated egress controls and a provider-specific rights review.
