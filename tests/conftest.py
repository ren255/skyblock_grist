import os

# `app.config` instantiates `Settings()` at import time, so the required
# environment variables must be present before any test imports `app.main`.
# `setdefault` keeps a real `.env` or an explicit override in charge.
os.environ.setdefault("GRIST_API_KEY", "test-api-key")
os.environ.setdefault("GRIST_DOC_ID", "test-doc-id")
