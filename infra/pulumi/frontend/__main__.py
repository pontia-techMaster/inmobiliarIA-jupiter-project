"""S3 + CloudFront for the React frontend.

`pulumi up` runs `npm install && npm run build` with VITE_API_URL set to
the api-gateway endpoint, then uploads the resulting dist/ to S3 and
invalidates the CloudFront cache.

For a faster inner loop, run `make fe-build` locally and `pulumi up`
will see the dist/ has changed and re-upload.
"""

from __future__ import annotations

import hashlib
import mimetypes
import subprocess
import sys
from pathlib import Path

import pulumi
import pulumi_aws as aws
import pulumi_command as command

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import default_tags, name  # noqa: E402
from _shared.refs import ApiGatewayRef  # noqa: E402

api = ApiGatewayRef()
repo_root = Path(__file__).resolve().parents[3]
fe_dir = repo_root / "services" / "frontend"
dist_dir = fe_dir / "dist"

# S3 bucket names are globally unique. Same prefix-with-account-id pattern
# we use for the Pulumi state bucket.
account_id = aws.get_caller_identity().account_id


def _build_frontend(api_endpoint: str) -> None:
    subprocess.run(["npm", "install", "--silent"], cwd=fe_dir, check=True)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=fe_dir,
        check=True,
        env={
            **__import__("os").environ,
            "VITE_API_URL": api_endpoint,
            # tracer doesn't exist in cloud yet — point at the same APIGW
            # so the "Ver traza →" link 404s cleanly instead of going to
            # a dead localhost URL.
            "VITE_TRACER_URL": api_endpoint,
        },
    )


# ── S3 bucket (private; CloudFront fronts it via OAC) ────────────────────────
fe_bucket = aws.s3.BucketV2(
    "fe-bucket",
    bucket=name(f"frontend-{account_id}"),
    force_destroy=True,
    tags=default_tags(),
)

aws.s3.BucketPublicAccessBlock(
    "fe-bucket-public-access",
    bucket=fe_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

# ── CloudFront in front of the bucket ─────────────────────────────────────────
oac = aws.cloudfront.OriginAccessControl(
    "fe-oac",
    name=name("frontend-oac"),
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

distribution = aws.cloudfront.Distribution(
    "fe-distribution",
    enabled=True,
    is_ipv6_enabled=True,
    default_root_object="index.html",
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            origin_id="fe-bucket-origin",
            domain_name=fe_bucket.bucket_regional_domain_name,
            origin_access_control_id=oac.id,
        )
    ],
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        cached_methods=["GET", "HEAD"],
        target_origin_id="fe-bucket-origin",
        viewer_protocol_policy="redirect-to-https",
        # AWS-managed CachingOptimized policy
        cache_policy_id="658327ea-f89d-4fab-a63d-7e88639e58f6",
        compress=True,
    ),
    custom_error_responses=[
        # SPA: route 404/403 back to index.html so client-side routing works
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403,
            response_code=200,
            response_page_path="/index.html",
        ),
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=404,
            response_code=200,
            response_page_path="/index.html",
        ),
    ],
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True,
    ),
    price_class="PriceClass_100",
    tags=default_tags(),
)

# ── Bucket policy allowing CloudFront (OAC) read access ───────────────────────
aws.s3.BucketPolicy(
    "fe-bucket-policy",
    bucket=fe_bucket.id,
    policy=pulumi.Output.all(fe_bucket.arn, distribution.arn).apply(
        lambda args: pulumi.Output.json_dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudfront.amazonaws.com"},
                        "Action": "s3:GetObject",
                        "Resource": f"{args[0]}/*",
                        "Condition": {
                            "StringEquals": {"AWS:SourceArn": args[1]},
                        },
                    }
                ],
            }
        )
    ),
)


# ── Build + sync ──────────────────────────────────────────────────────────────
def _sync_dist(args: tuple[str, str]) -> str:
    """Build, upload each file, return a hash of dist/ contents.

    The returned hash becomes the trigger for the CloudFront invalidation
    below — so we only invalidate when the assets actually change.
    """
    api_endpoint, bucket_name = args
    _build_frontend(api_endpoint)
    if not dist_dir.exists():
        raise RuntimeError(f"build did not produce {dist_dir}")
    hasher = hashlib.sha256()
    for path in sorted(dist_dir.rglob("*")):
        if not path.is_file():
            continue
        key = path.relative_to(dist_dir).as_posix()
        ctype, _ = mimetypes.guess_type(path.name)
        aws.s3.BucketObjectv2(
            f"fe-obj-{key}",
            bucket=bucket_name,
            key=key,
            source=pulumi.FileAsset(str(path)),
            content_type=ctype or "application/octet-stream",
            opts=pulumi.ResourceOptions(parent=fe_bucket),
        )
        hasher.update(key.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


dist_hash = pulumi.Output.all(api.endpoint, fe_bucket.bucket).apply(_sync_dist)


# ── CloudFront invalidation (re-runs whenever dist/ changes) ─────────────────
# Without this CloudFront keeps serving the old index.html and assets forever,
# so users never see new deploys until the cache TTL expires.
invalidation_cmd = pulumi.Output.format(
    "aws cloudfront create-invalidation --distribution-id {} --paths '/*' --no-cli-pager",
    distribution.id,
)
command.local.Command(
    "fe-invalidation",
    create=invalidation_cmd,
    update=invalidation_cmd,
    triggers=[dist_hash],
    opts=pulumi.ResourceOptions(depends_on=[fe_bucket]),
)

pulumi.export("bucket_name", fe_bucket.bucket)
pulumi.export("cloudfront_domain", distribution.domain_name)
pulumi.export("url", distribution.domain_name.apply(lambda d: f"https://{d}"))
