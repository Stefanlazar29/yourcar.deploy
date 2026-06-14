#!/usr/bin/env python3
"""
Backup SQLite (PRAGMA wal_checkpoint + .backup) + opțional upload S3 / compatibil DO Spaces.
Opțional VACUUM săptămânal (setează VACUUM_WEEKLY_ON_DAY=0..6 sau RUN_VACUUM_NOW=1).

Variabile: SQLITE_PATH, AUTH_AUDIT_PATH, S3_BACKUP_BUCKET, S3_BACKUP_PREFIX,
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, AWS_ENDPOINT_URL (Spaces).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_one(src: str, dest: str) -> bool:
    if not os.path.isfile(src):
        print(f"[backup] skip (missing): {src}", file=sys.stderr)
        return False
    try:
        wal = src + "-wal"
        shm = src + "-shm"
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.Error:
            pass
        try:
            b = sqlite3.connect(dest)
            try:
                con.backup(b)
            finally:
                b.close()
        finally:
            con.close()
        print(f"[backup] ok → {dest} ({os.path.getsize(dest)} bytes)")
        return True
    except Exception as e:
        print(f"[backup] error {src}: {e}", file=sys.stderr)
        return False


def _upload_s3(local_path: str, key: str) -> None:
    import boto3  # noqa: WPS433

    bucket = (os.getenv("S3_BACKUP_BUCKET") or "").strip()
    if not bucket:
        return
    prefix = (os.getenv("S3_BACKUP_PREFIX") or "mulberry/sqlite/").strip().strip("/")
    region = (os.getenv("AWS_DEFAULT_REGION") or "eu-central-1").strip()
    endpoint = (os.getenv("AWS_ENDPOINT_URL") or "").strip() or None
    kwargs = {}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    client = boto3.client("s3", region_name=region, **kwargs)
    full_key = f"{prefix}/{key}" if prefix else key
    extra = {}
    sse = (os.getenv("S3_SSE") or "").strip()
    if sse == "AES256":
        extra["ServerSideEncryption"] = "AES256"
    if extra:
        client.upload_file(local_path, bucket, full_key, ExtraArgs=extra)
    else:
        client.upload_file(local_path, bucket, full_key)
    print(f"[backup] s3://{bucket}/{full_key}")


def _maybe_vacuum(path: str) -> None:
    if not os.path.isfile(path):
        return
    run_now = (os.getenv("RUN_VACUUM_NOW") or "").strip().lower() in ("1", "true", "yes")
    day_env = (os.getenv("VACUUM_WEEKLY_ON_DAY") or "").strip()
    if day_env.lower() in ("-1", "none", "off"):
        return
    if not run_now and day_env == "":
        return
    if not run_now and day_env != "":
        try:
            want = int(day_env)
        except ValueError:
            want = -1
        if want >= 0 and datetime.now(timezone.utc).weekday() != want:
            return
    try:
        con = sqlite3.connect(path)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            con.execute("VACUUM;")
            con.commit()
        finally:
            con.close()
        print(f"[vacuum] ok {path}")
    except Exception as e:
        print(f"[vacuum] skip {path}: {e}", file=sys.stderr)


def main() -> int:
    data_dir = "/data"
    backup_dir = os.path.join(data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = _ts()

    main_db = os.getenv("SQLITE_PATH", "/data/mulberry.db")
    audit_db = os.getenv("AUTH_AUDIT_PATH", "/data/auth_audit.db")

    f1 = os.path.join(backup_dir, f"mulberry-{ts}.db")
    f2 = os.path.join(backup_dir, f"auth_audit-{ts}.db")

    _backup_one(main_db, f1)
    _backup_one(audit_db, f2)

    try:
        if os.path.isfile(f1):
            _upload_s3(f1, f"mulberry-{ts}.db")
        if os.path.isfile(f2):
            _upload_s3(f2, f"auth_audit-{ts}.db")
    except Exception as e:
        print(f"[backup] S3 upload error: {e}", file=sys.stderr)

    # Păstrează ultimele N copii locale (opțional)
    keep = int(os.getenv("BACKUP_KEEP_LOCAL") or "48")
    if keep > 0:
        files = sorted(
            [os.path.join(backup_dir, x) for x in os.listdir(backup_dir) if x.endswith(".db")],
            key=os.path.getmtime,
        )
        while len(files) > keep:
            old = files.pop(0)
            try:
                os.remove(old)
                print(f"[backup] removed old {old}")
            except OSError:
                break

    _maybe_vacuum(main_db)
    _maybe_vacuum(audit_db)

    if (os.getenv("RUN_VACUUM_NOW") or "").strip().lower() in ("1", "true", "yes"):
        os.environ.pop("RUN_VACUUM_NOW", None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
