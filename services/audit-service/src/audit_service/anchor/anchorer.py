"""Daily anchor generation and S3 / MinIO storage."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from audit_service.db.models import Anchor, AuditLog

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minio-dev")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minio-dev-change-me")
S3_BUCKET = os.getenv("S3_BUCKET", "selene-data")
S3_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def get_s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4"),
    )


async def create_daily_anchor(
    session: AsyncSession,
    day: datetime.date | None = None,
    s3_client: Any = None,
) -> Anchor | None:
    """Compute digest of the latest chain head and store in S3 and anchors table."""
    target_day = day or datetime.datetime.now(datetime.UTC).date()

    # Find the latest audit log row
    stmt = select(AuditLog).order_by(desc(AuditLog.seq)).limit(1)
    res = await session.execute(stmt)
    latest_row = res.scalar_one_or_none()

    if latest_row is None:
        return None

    anchor_key = f"_audit-anchors/{target_day.isoformat()}.json"
    anchor_uri = f"s3://{S3_BUCKET}/{anchor_key}"

    anchor_payload = {
        "day": target_day.isoformat(),
        "last_seq": latest_row.seq,
        "digest": latest_row.row_hash.hex(),
        "anchored_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    payload_bytes = json.dumps(anchor_payload, indent=2).encode("utf-8")

    # Upload to S3 / MinIO
    client = s3_client or get_s3_client()
    try:
        client.put_object(
            Bucket=S3_BUCKET,
            Key=anchor_key,
            Body=payload_bytes,
            ContentType="application/json",
        )
    except (client.exceptions.NoSuchBucket, Exception):  # noqa: BLE001
        # If bucket does not exist, create it (dev convenience)
        try:
            client.create_bucket(Bucket=S3_BUCKET)
            client.put_object(
                Bucket=S3_BUCKET,
                Key=anchor_key,
                Body=payload_bytes,
                ContentType="application/json",
            )
        except Exception as upload_err:
            raise RuntimeError(
                f"Failed to upload anchor to {anchor_uri}: {upload_err}"
            ) from upload_err

    # Record in DB anchors table
    existing = await session.get(Anchor, target_day)
    if existing:
        existing.last_seq = latest_row.seq
        existing.digest = latest_row.row_hash
        existing.anchor_uri = anchor_uri
        existing.created_at = datetime.datetime.now(datetime.UTC)
        anchor = existing
    else:
        anchor = Anchor(
            day=target_day,
            last_seq=latest_row.seq,
            digest=latest_row.row_hash,
            anchor_uri=anchor_uri,
        )
        session.add(anchor)

    await session.commit()
    await session.refresh(anchor)
    return anchor


def get_anchor_from_s3(day: datetime.date, s3_client: Any = None) -> dict[str, Any] | None:
    """Retrieve an anchor payload from S3 / MinIO for a given date."""
    client = s3_client or get_s3_client()
    anchor_key = f"_audit-anchors/{day.isoformat()}.json"
    try:
        resp = client.get_object(Bucket=S3_BUCKET, Key=anchor_key)
        data = resp["Body"].read().decode("utf-8")
        return json.loads(data)  # type: ignore[no-any-return]
    except Exception:  # noqa: BLE001
        return None
