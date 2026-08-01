# Mailcow: conservative host-managed hand-off

Mailcow already has its own certificate expectations and update mechanisms.
Keep cert-renewer outside the Mailcow stack and make a backup before integrating.

1. Configure cert-renewer to install to a host-only path such as
   `/srv/certificates/mail.example.com`.
2. After a successful renewal, use a reviewed host-side helper to copy
   `current/fullchain.pem` and `current/privkey.pem` to the paths documented
   by the Mailcow version you run.
3. Set file ownership/permissions expected by Mailcow, validate the new files,
   then use Mailcow's documented restart or reload action.

Do not mount Mailcow's Docker socket into cert-renewer. Test the complete
handoff on a non-production hostname first; Mailcow layouts change between
releases, so this repository intentionally does not claim a universal path.

