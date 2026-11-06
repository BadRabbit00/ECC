# SSRF, files, uploads

## Outgoing requests (S-SSRF)
- S-SSRF-1: a URL that a user can influence (webhook target, "import from URL", avatar URL, OAuth `redirect_uri`, image proxy) is fetched only after validation:
  - scheme `https` only (or an explicit allowlist);
  - host on an allowlist where possible; otherwise resolve DNS **once**, reject private, loopback, link-local, metadata, and multicast ranges (`127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`, `fe80::/10`, `100.64/10`), and connect to the resolved IP (no second lookup → no DNS rebinding);
  - redirects off, or each hop re-validated;
  - timeouts, response size cap, no forwarding of internal headers or credentials.
- S-SSRF-2: requests to a fixed URL from config are not SSRF; do not report them.
- S-SSRF-3: outgoing requests from the API go through one client module with the policy (timeouts, retries, allowlist).

## Uploads (S-FILE)
- S-FILE-1: size limit enforced while streaming (not after reading into memory); count limit per request.
- S-FILE-2: type checked by content (magic bytes / a decoder), not by the `Content-Type` header or extension alone; allowlist of types.
- S-FILE-3: the stored name is generated (UUID); the user's filename is metadata only, never part of a path. No `os.path.join(UPLOAD_DIR, filename)` with user input.
- S-FILE-4: files go to S3 (or a volume outside the web root), private; served through signed URLs with short expiry after an authorisation check, with `Content-Disposition: attachment` for anything not meant to render.
- S-FILE-5: images re-encoded or at least decoded with limits (pixel count) before use; SVG treated as active content (sanitise or serve as attachment).
- S-FILE-6: archives extracted with checks for path traversal (`..`, absolute paths, symlinks) and total uncompressed size (zip bombs).
- S-FILE-7: downloads by ID check that the actor may read that object (S-ACCESS-2); no path or key from the query string.
