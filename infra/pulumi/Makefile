.PHONY: install check-sso state-init up destroy preview outputs login-remote deploy-all prompt-secrets

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

# ──────────────────────────────────────────────────────────────────────────────
# Full deploy in dependency order. Prompts for secret values only if their
# SSM parameter is still the placeholder. Skips parameters already set.
# Re-runnable — Pulumi diffs each stack and no-ops if nothing changed.
# ──────────────────────────────────────────────────────────────────────────────
DEPLOY_ORDER = platform api-gateway process-user-prompt vector-query ranking-and-rendering data-ingestion frontend

deploy-all: check-sso
	@echo "▶ deploying platform (foundation: queues, ECR, log groups, SSM placeholders)"
	@cd platform && pulumi up --stack dev --yes
	@$(MAKE) -s prompt-secrets
	@for stack in api-gateway process-user-prompt vector-query ranking-and-rendering data-ingestion frontend; do \
		echo "" ; \
		echo "▶ deploying $$stack" ; \
		(cd $$stack && pulumi up --stack dev --yes) || (echo "❌ $$stack failed"; exit 1) ; \
	done
	@echo ""
	@echo "✅ All stacks deployed."
	@echo ""
	@echo "Frontend URL:"
	@cd frontend && pulumi stack output url --stack dev 2>/dev/null || echo "  (not available)"
	@echo "API Gateway endpoint:"
	@cd api-gateway && pulumi stack output endpoint --stack dev 2>/dev/null || echo "  (not available)"

# Prompt for any SSM SecureString that's still REPLACE_ME. Hides input.
prompt-secrets:
	@for key in gemini-api-key qdrant-api-key; do \
		current=$$(aws --profile inmo ssm get-parameter --name "inmo-dev-$$key" --with-decryption --query Parameter.Value --output text 2>/dev/null) ; \
		if [ "$$current" = "REPLACE_ME" ] || [ -z "$$current" ]; then \
			printf "Enter value for %s (input hidden): " "inmo-dev-$$key" ; \
			stty -echo ; read value ; stty echo ; echo ; \
			if [ -z "$$value" ]; then \
				echo "  ⏭  empty input, skipping (set later via 'aws ssm put-parameter')" ; \
			else \
				aws --profile inmo ssm put-parameter --name "inmo-dev-$$key" --type SecureString --value "$$value" --overwrite >/dev/null ; \
				echo "  ✓ inmo-dev-$$key set" ; \
			fi ; \
		else \
			echo "  ✓ inmo-dev-$$key already set, skipping" ; \
		fi ; \
	done
