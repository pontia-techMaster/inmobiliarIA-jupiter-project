.PHONY: install check-sso state-init up destroy preview outputs login-remote

# Force the AWS SDK credential chain to use the `inmo` profile for every
# target in this Makefile. Belt-and-suspenders with `aws:profile: inmo`
# in the Pulumi configs — the env var is what pulumi-aws honors most
# reliably with SSO profiles. Override at your own risk.
export AWS_PROFILE = inmo

# ──────────────────────────────────────────────────────────────────────────────
# Pulumi shell-out conventions
#
# All stacks share a single venv at ./.venv (each Pulumi.yaml points at it
# via `runtime.options.virtualenv: ../.venv`). Foundation stacks use the
# self-hosted S3 backend created by `_bootstrap`. The bootstrap stack itself
# uses the LOCAL backend because the bucket doesn't exist yet.
#
# Variables:
#   STACK   stack directory name (e.g. platform, api-gateway, frontend)
#
# Examples:
#   make install                         # one-time: create venv, install deps
#   make state-init                      # create state bucket + lock table (LOCAL backend)
#   make login-remote                    # switch CLI to the S3 backend
#   make up STACK=platform               # pulumi up on a stack
#   make outputs STACK=platform          # pulumi stack output --json
# ──────────────────────────────────────────────────────────────────────────────

install:
	uv sync

# Pre-flight: every cloud target depends on this. Fails fast with a helpful
# message if the inmo SSO token is expired, so pulumi can never silently
# fall back to other creds.
check-sso:
	@aws --profile inmo sts get-caller-identity --query Account --output text >/dev/null 2>&1 || \
		(echo "❌ inmo SSO token expired or missing. Run: aws sso login --profile inmo" && exit 1)
	@echo "✅ inmo SSO session OK ($$(aws --profile inmo sts get-caller-identity --query Account --output text))"

state-init: check-sso
	@cd _bootstrap && \
	pulumi login --local && \
	(pulumi stack select dev 2>/dev/null || pulumi stack init dev) && \
	PULUMI_CONFIG_PASSPHRASE="$${PULUMI_CONFIG_PASSPHRASE:-}" pulumi up --stack dev --yes

login-remote:
	@account=$$(aws --profile inmo sts get-caller-identity --query Account --output text 2>/dev/null) ; \
	if [ -z "$$account" ]; then \
		echo "Could not get account ID via 'aws --profile inmo'. Configure the profile first."; exit 1; \
	fi ; \
	region=$$(grep -E '^\s*aws:region:' _bootstrap/Pulumi.dev.yaml | awk '{print $$2}') ; \
	region=$${region:-eu-west-1} ; \
	bucket="inmo-dev-pulumi-state-$$account" ; \
	echo "Logging in to s3://$$bucket?region=$$region" ; \
	pulumi login "s3://$$bucket?region=$$region"

up: check-sso
	@test -n "$(STACK)" || (echo "usage: make up STACK=<dir>"; exit 1)
	cd $(STACK) && pulumi up --stack dev

preview: check-sso
	@test -n "$(STACK)" || (echo "usage: make preview STACK=<dir>"; exit 1)
	cd $(STACK) && pulumi preview --stack dev

destroy: check-sso
	@test -n "$(STACK)" || (echo "usage: make destroy STACK=<dir>"; exit 1)
	cd $(STACK) && pulumi destroy --stack dev

outputs:
	@test -n "$(STACK)" || (echo "usage: make outputs STACK=<dir>"; exit 1)
	cd $(STACK) && pulumi stack output --json --stack dev
