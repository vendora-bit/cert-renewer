# Good first issues to open after the v2.0.0 release

Create these as GitHub issues with the `good first issue` label after the
release is public. They are deliberately documentation- and test-first tasks.

1. **Add a Caddy recipe** — contribute an `examples/caddy/` deployment that
   consumes `current/fullchain.pem` and `current/privkey.pem`; verify it with a
   local Compose smoke test.
2. **Document Cloudflare token scoping** — add a concise least-privilege guide
   for single-zone and multi-zone tokens, including a review checklist.
3. **Add a `status.json` schema example** — document successful, degraded and
   failed entries without real hostnames, tokens or certificate data.
4. **Expand the Proxmox recipe test** — provide a shell test that validates file
   permissions and detects an unsafe symlink before a proxy reload.

