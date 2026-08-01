# Contributing

Thanks for improving cert-renewer. Small, focused pull requests are easiest to review.

## Development

```bash
git clone https://github.com/vendora-bit/cert-renewer.git
cd cert-renewer
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check src tests
mypy --ignore-missing-imports src
```

Use Python 3.11 or newer. Keep configuration validation strict, avoid logging
tokens or certificate private-key material, and include a regression test for
every behavioural change.

## Pull requests

1. Open an issue first for changes that affect configuration, deployment or security.
2. Keep the change scoped; update `README.md`, examples and `CHANGELOG.md` when users see it.
3. Run the test suite and `shellcheck` on changed shell files.
4. By submitting a contribution, you license it under Apache-2.0.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting.

