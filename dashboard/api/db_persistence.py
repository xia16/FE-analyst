"""Persist portfolio.db to Google Cloud Storage across Cloud Run deploys.

On startup:  restore() downloads the latest DB from GCS (if it exists),
             overriding the seed-only copy baked into the Docker image.
On mutation: backup() uploads the current DB back to GCS.

Env vars:
    GCS_DB_BUCKET  — bucket name (e.g. "fe-analyst-data")
    GCS_DB_BLOB    — blob path (default "portfolio.db")

If GCS_DB_BUCKET is not set, persistence is disabled (local-only mode).
"""

import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger("db_persistence")

DB_PATH = Path(__file__).parent / "portfolio.db"
_BUCKET_NAME = os.environ.get("GCS_DB_BUCKET", "")
_BLOB_NAME = os.environ.get("GCS_DB_BLOB", "portfolio.db")


def _get_bucket():
    """Lazily init GCS client and return bucket (or None if disabled)."""
    if not _BUCKET_NAME:
        return None
    try:
        from google.cloud import storage
        client = storage.Client()
        return client.bucket(_BUCKET_NAME)
    except Exception as e:
        logger.warning("GCS unavailable: %s", e)
        return None


def restore() -> bool:
    """Download portfolio.db from GCS, replacing the seed copy.

    Returns True if a GCS copy was restored, False if using seed/local.
    """
    bucket = _get_bucket()
    if bucket is None:
        logger.info("GCS persistence disabled — using local DB only")
        return False

    blob = bucket.blob(_BLOB_NAME)
    if not blob.exists():
        logger.info("No GCS backup found — using seed DB, will upload on first write")
        # Upload the seed DB so future deploys have it
        backup()
        return False

    tmp_path = DB_PATH.with_suffix(".db.gcs_download")
    try:
        blob.download_to_filename(str(tmp_path))
        # Atomic replace
        shutil.move(str(tmp_path), str(DB_PATH))
        logger.info("Restored portfolio.db from gs://%s/%s", _BUCKET_NAME, _BLOB_NAME)
        return True
    except Exception as e:
        logger.error("Failed to restore from GCS: %s", e)
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def backup() -> bool:
    """Upload portfolio.db to GCS.

    Returns True on success, False if GCS is disabled or upload fails.
    """
    bucket = _get_bucket()
    if bucket is None:
        return False

    if not DB_PATH.exists():
        logger.warning("No local portfolio.db to backup")
        return False

    try:
        blob = bucket.blob(_BLOB_NAME)
        blob.upload_from_filename(str(DB_PATH))
        logger.info("Backed up portfolio.db to gs://%s/%s", _BUCKET_NAME, _BLOB_NAME)
        return True
    except Exception as e:
        logger.error("Failed to backup to GCS: %s", e)
        return False
