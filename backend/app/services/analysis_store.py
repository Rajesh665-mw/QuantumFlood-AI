"""
Analysis Store — Request-Scoped Result Isolation & Workspace Management.
========================================================================
Maintains isolated analysis workspaces keyed by collision-resistant analysis IDs.
Eliminates cross-user pipeline state contamination and fixed-filename race conditions.

Features:
  - Collision-resistant, server-generated analysis IDs (ANL-<uuid4>).
  - Thread-safe in-memory cache with bounded LRU eviction (prevents memory leaks).
  - Isolated, atomic disk persistence per analysis (temp-file write + atomic rename).
  - Strict input validation rejecting path traversal, empty IDs, and malformed keys.
"""
import os
import re
import json
import uuid
import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from app.config.settings import (
    DATA_PROCESSED_DIR,
    ANALYSIS_STORE_TTL_HOURS,
    ANALYSIS_STORE_MAX_DISK_MB,
    ANALYSIS_STORE_MAX_MEMORY,
)

logger = logging.getLogger(__name__)

ANALYSES_DIR = DATA_PROCESSED_DIR / "analyses"
try:
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    import tempfile
    ANALYSES_DIR = Path(tempfile.gettempdir()) / "quantumflood" / "analyses"
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

ANALYSIS_ID_REGEX = re.compile(r"^ANL-[A-Za-z0-9_-]{8,64}$")


class AnalysisStore:
    def __init__(
        self,
        storage_dir: Path = ANALYSES_DIR,
        max_cache: int = ANALYSIS_STORE_MAX_MEMORY,
        ttl_hours: float = ANALYSIS_STORE_TTL_HOURS,
        max_disk_mb: float = ANALYSIS_STORE_MAX_DISK_MB,
    ):
        try:
            self._dir = storage_dir.resolve()
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            import tempfile
            self._dir = (Path(tempfile.gettempdir()) / "quantumflood" / "analyses").resolve()
            self._dir.mkdir(parents=True, exist_ok=True)
        self._max_cache = max_cache
        self._ttl_seconds = max(0.1, float(ttl_hours) * 3600.0)
        self._max_disk_bytes = max(10 * 1024 * 1024, int(max_disk_mb * 1024 * 1024))
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    @staticmethod
    def generate_id() -> str:
        """
        Generates a collision-resistant, cryptographically strong analysis identifier.
        Uses full 128-bit UUID4 hex (32 characters), yielding 36 chars total.
        Acts as an unguessable bearer capability reference.
        """
        return f"ANL-{uuid.uuid4().hex}"

    @staticmethod
    def is_valid_id(analysis_id: Optional[str]) -> bool:
        """
        Validates that the analysis identifier matches permitted syntax and prevents path traversal.
        Strictly whitelist-checked against ANALYSIS_ID_REGEX without special filesystem characters.
        """
        if not analysis_id or not isinstance(analysis_id, str):
            return False
        if "/" in analysis_id or "\\" in analysis_id or ".." in analysis_id or "\x00" in analysis_id:
            return False
        return bool(ANALYSIS_ID_REGEX.match(analysis_id))

    def _file_path(self, analysis_id: str) -> Path:
        """Resolves target JSON file path and enforces strict confinement inside self._dir."""
        safe_name = Path(analysis_id).name
        target = (self._dir / f"{safe_name}.json").resolve()
        try:
            target.relative_to(self._dir)
        except ValueError:
            raise ValueError(f"Path traversal detected for analysis_id: {analysis_id}")
        return target

    def _is_expired(self, path: Path, data: Optional[Dict[str, Any]] = None) -> bool:
        """Checks if an analysis file has exceeded configured TTL."""
        now = datetime.now(timezone.utc).timestamp()
        if data and "updated_at" in data:
            try:
                dt = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
                if (now - dt.timestamp()) > self._ttl_seconds:
                    return True
            except Exception:
                pass
        try:
            mtime = path.stat().st_mtime
            return (now - mtime) > self._ttl_seconds
        except Exception:
            return False

    def get(self, analysis_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Retrieves an analysis bundle by ID, checking memory cache then disk.
        Returns None if ID is invalid, missing, expired, or malformed.
        """
        if not self.is_valid_id(analysis_id):
            return None

        with self._lock:
            # 1. Check memory cache
            if analysis_id in self._cache:
                data = self._cache[analysis_id]
                path = self._file_path(analysis_id)
                if path.exists() and self._is_expired(path, data):
                    self.delete(analysis_id)
                    return None
                self._cache.move_to_end(analysis_id)
                return data

            # 2. Check disk workspace
            path = self._file_path(analysis_id)
            if not path.exists():
                return None

            if self._is_expired(path):
                self.delete(analysis_id)
                return None

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning("Analysis file '%s' has non-dict content. Evicting.", path)
                    return None
                self._cache[analysis_id] = data
                self._enforce_cache_limit()
                return data
            except Exception as e:
                logger.warning("Failed to load analysis '%s' from disk: %s", analysis_id, e)
                return None

    def save(self, analysis_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves or updates an analysis bundle atomically in memory and on disk.
        Uses process/thread-unique temp file to prevent concurrent rename collisions.
        """
        if not self.is_valid_id(analysis_id):
            raise ValueError(f"Invalid analysis identifier: '{analysis_id}'")

        with self._lock:
            data["analysis_id"] = analysis_id
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "created_at" not in data:
                data["created_at"] = data["updated_at"]

            # Update cache
            self._cache[analysis_id] = data
            self._cache.move_to_end(analysis_id)
            self._enforce_cache_limit()

            # Atomic disk write (unique temp file + atomic replace)
            path = self._file_path(analysis_id)
            nonce = uuid.uuid4().hex[:8]
            tmp_path = self._dir / f"{analysis_id}.tmp_{os.getpid()}_{threading.get_ident()}_{nonce}"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except Exception as e:
                logger.warning("Failed to persist analysis '%s' to disk: %s", analysis_id, e)
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass

            return data

    def update_field(self, analysis_id: str, field_name: str, field_value: Any) -> Dict[str, Any]:
        """Updates a specific field in an existing analysis bundle."""
        with self._lock:
            existing = self.get(analysis_id) or {"analysis_id": analysis_id}
            existing[field_name] = field_value
            return self.save(analysis_id, existing)

    def _enforce_cache_limit(self):
        """Evicts oldest entries from in-memory cache if limit is exceeded."""
        while len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)

    def delete(self, analysis_id: str) -> bool:
        """Deletes an analysis bundle from memory and disk."""
        if not self.is_valid_id(analysis_id):
            return False
        with self._lock:
            self._cache.pop(analysis_id, None)
            try:
                path = self._file_path(analysis_id)
                if path.exists():
                    path.unlink()
                    return True
            except Exception as e:
                logger.warning("Error deleting analysis '%s': %s", analysis_id, e)
            return False

    def cleanup_expired_analyses(self, max_age_seconds: Optional[float] = None) -> int:
        """
        Cleans up expired analyses and bounds disk growth.
        - Deletes stale .tmp files older than 30 minutes.
        - Deletes .json files older than max_age_seconds (or self._ttl_seconds).
        - Enforces max_disk_bytes quota by evicting oldest analysis files if needed.
        Returns the count of deleted analysis files.
        """
        effective_ttl = max_age_seconds if max_age_seconds is not None else self._ttl_seconds
        now = datetime.now(timezone.utc).timestamp()
        deleted_count = 0

        with self._lock:
            # 1. Clean stale temporary files
            try:
                for tmp_file in self._dir.glob("*.tmp_*"):
                    try:
                        if (now - tmp_file.stat().st_mtime) > 1800.0:
                            tmp_file.unlink()
                    except Exception:
                        pass
            except Exception:
                pass

            # 2. Inspect active analysis JSON files
            json_files = []
            total_disk_bytes = 0

            try:
                for file_path in self._dir.glob("*.json"):
                    try:
                        stat = file_path.stat()
                        age = now - stat.st_mtime
                        aid = file_path.stem
                        if age > effective_ttl:
                            file_path.unlink()
                            self._cache.pop(aid, None)
                            deleted_count += 1
                        else:
                            json_files.append((stat.st_mtime, stat.st_size, file_path, aid))
                            total_disk_bytes += stat.st_size
                    except Exception as e:
                        logger.warning("Error inspecting analysis file %s: %s", file_path, e)
            except Exception as e:
                logger.warning("Error scanning analysis directory: %s", e)

            # 3. Enforce disk quota bound
            if total_disk_bytes > self._max_disk_bytes:
                # Sort by mtime ascending (oldest first)
                json_files.sort(key=lambda x: x[0])
                for mtime, size, file_path, aid in json_files:
                    if total_disk_bytes <= self._max_disk_bytes:
                        break
                    try:
                        file_path.unlink()
                        self._cache.pop(aid, None)
                        total_disk_bytes -= size
                        deleted_count += 1
                    except Exception:
                        pass

        return deleted_count


# Global singleton instance for analysis store
analysis_store = AnalysisStore()
