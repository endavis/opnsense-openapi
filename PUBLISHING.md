# Publishing to PyPI

## One-Time Setup

### 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create an account and verify your email
3. Enable 2FA (required for new projects)

### 2. Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Token name: `opnsense-openapi` (or any name)
4. Scope: "Entire account" (for first upload), then you can create project-scoped tokens
5. Copy the token (starts with `pypi-`)

### 3. Store Token Securely

Option A - Environment variable:
```bash
export PYPI_TOKEN="pypi-your-token-here"
```

Option B - Add to shell profile (~/.bashrc or ~/.zshrc):
```bash
export PYPI_TOKEN="pypi-your-token-here"
```

Option C - Use a .env file (don't commit this!):
```bash
echo 'PYPI_TOKEN=pypi-your-token-here' >> .env
source .env
```

### 4. (Optional) Setup TestPyPI

For testing uploads before going to production:

1. Create account at https://test.pypi.org/account/register/
2. Create token at https://test.pypi.org/manage/account/token/
3. Store as `TEST_PYPI_TOKEN`

## Publishing Workflow

### First Release

```bash
# 1. Install dev dependencies
just install

# 2. Run tests
just test

# 3. Build and publish
just publish
```

### Subsequent Releases

```bash
# 1. Bump version
just bump patch  # 0.1.0 -> 0.1.1
just bump minor  # 0.1.0 -> 0.2.0
just bump major  # 0.1.0 -> 1.0.0

# 2. Commit version bump
git add -A && git commit -m "chore: bump version to X.Y.Z"

# 3. Tag release
git tag vX.Y.Z

# 4. Push
git push && git push --tags

# 5. Publish
just publish
```

### Testing with TestPyPI

```bash
# Upload to test server
just publish-test

# Install from test server to verify
pip install --index-url https://test.pypi.org/simple/ opnsense-openapi
```

## Available Commands

| Command | Description |
|---------|-------------|
| `just build` | Build wheel and sdist |
| `just publish` | Build and upload to PyPI |
| `just publish-test` | Build and upload to TestPyPI |
| `just bump patch` | Bump patch version (0.1.0 -> 0.1.1) |
| `just bump minor` | Bump minor version (0.1.0 -> 0.2.0) |
| `just bump major` | Bump major version (0.1.0 -> 1.0.0) |

## Troubleshooting

### "Project not found" error
First upload requires "Entire account" scoped token. After first upload, you can create a project-scoped token.

### "Invalid token" error
Make sure `PYPI_TOKEN` environment variable is set and starts with `pypi-`.

### Package already exists
Version numbers can't be reused. Bump the version and try again.
