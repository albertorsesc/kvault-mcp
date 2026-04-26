# Security Policy

## Supported versions

kvault-mcp is pre-1.0. Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.x     | Yes       |

## Reporting a vulnerability

**Do not** open a public GitHub issue for security reports.

Report vulnerabilities privately via GitHub's [Security Advisories](https://github.com/albertorsesc/kvault-mcp/security/advisories/new) form. Include:

- A clear description of the issue and its impact
- A minimal reproduction (preferred: a failing `pytest` case)
- Your assessment of severity (CVSS optional)
- Whether you wish to be credited in the fix announcement

Response timeline:

- **Acknowledgement**: within 72 hours
- **Triage + severity**: within 7 days
- **Fix + release**: target 30 days for high severity; best-effort for others
- **Public disclosure**: after the fix ships, coordinated with the reporter

## Threat model

kvault-mcp runs a trusted plugin set selected by the vault operator. Its in-scope security properties are:

- **State confinement.** Plugins use `kernel.state_path(category, name)` and cannot escape the vault directory (`..`, absolute paths, symlink traversal are rejected).
- **No plugin-to-plugin trust escalation.** Plugins coordinate only via the service registry and event bus; they cannot directly access each other's state.
- **Input-facing sanitization.** FTS5 query input and SQL identifiers are sanitized before being concatenated into statements.
- **Secret redaction.** `kvault.config.show` redacts keys matching sensitive-name heuristics (`*_key`, `*_token`, `*_secret`, `password`) before returning config to MCP clients.

Out of scope (by design):

- **Untrusted plugin sandboxing.** The operator is expected to audit installed plugins. `pip install random-kvault-plugin` runs arbitrary code on `kernel.start()`, as with any Python entry-point system.
- **Network security.** Plugins that make outbound calls (e.g., `embedding/ollama`) are responsible for their own TLS and authentication.
- **Multi-tenant isolation.** One kernel serves one vault. Multi-tenant deployment is not supported.

## Disclosure

When a fix ships, the `CHANGELOG.md` entry names the vulnerability, the fix, and the reporter (with permission). A GitHub Security Advisory is published the same day.
