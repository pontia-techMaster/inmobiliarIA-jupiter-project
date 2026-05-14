.PHONY: install check-sso state-init up destroy preview outputs login-remote deploy-all destroy-all prompt-secrets show-cloud-resources fe-invalidate aws-logs seed-html trigger-ingestion purge-sqs

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
	@set -e ; \
	echo "▶ deploying platform (foundation: queues, ECR, log groups, SSM placeholders)" ; \
	(cd platform && pulumi up --stack dev --yes) ; \
	$(MAKE) -s prompt-secrets ; \
	for stack in api-gateway process-user-prompt vector-query ranking-and-rendering data-ingestion frontend; do \
		echo "" ; \
		echo "▶ deploying $$stack" ; \
		if ! (cd $$stack && pulumi up --stack dev --yes); then \
			echo "" ; \
			echo "❌ $$stack failed — aborting deploy-all." ; \
			echo "   No cleanup needed: Pulumi rolled back the failing resource." ; \
			echo "   Fix the cause, then re-run 'make deploy-all' (it'll resume from here)." ; \
			exit 1 ; \
		fi ; \
	done ; \
	echo "" ; \
	echo "✅ All stacks deployed." ; \
	echo "" ; \
	echo "Frontend URL:    $$(cd frontend && pulumi stack output url --stack dev 2>/dev/null || echo '(not available)')" ; \
	echo "API Gateway:     $$(cd api-gateway && pulumi stack output endpoint --stack dev 2>/dev/null || echo '(not available)')"

# Sync the local HTML source into the S3 ingestion bucket. Run once
# before triggering ingestion for the first time.
seed-html: check-sso
	@account=$$(aws --profile inmo sts get-caller-identity --query Account --output text) ; \
	bucket="inmo-dev-html-source-$$account" ; \
	echo "▶ syncing services/data_ingestion/data/source_html/ → s3://$$bucket/html/" ; \
	aws --profile inmo s3 sync ../../services/data_ingestion/data/source_html/ "s3://$$bucket/html/"

# Purge an SQS queue. Default queue is `search-requests`; override with QUEUE=.
# AWS rate-limits PurgeQueue to once per 60s.
#   make purge-sqs
#   make purge-sqs QUEUE=query-jobs
purge-sqs: check-sso
	@queue=$(or $(QUEUE),search-requests) ; \
	queue_url=$$(aws --profile inmo sqs get-queue-url --queue-name "inmo-dev-queue-$$queue" --query QueueUrl --output text) ; \
	echo "▶ purging inmo-dev-queue-$$queue ($$queue_url)" ; \
	aws --profile inmo sqs purge-queue --queue-url "$$queue_url" && \
	echo "✓ queued for purge — up to 60s to complete"

# Manually trigger data_ingestion by publishing an IngestJob to ingest-jobs.
# Lambda picks it up via the event-source mapping. Run `make aws-logs
# SERVICE=data-ingestion` in another terminal to watch.
trigger-ingestion: check-sso
	@account=$$(aws --profile inmo sts get-caller-identity --query Account --output text) ; \
	bucket="inmo-dev-html-source-$$account" ; \
	queue_url=$$(aws --profile inmo sqs get-queue-url --queue-name inmo-dev-queue-ingest-jobs --query QueueUrl --output text) ; \
	echo "▶ publishing IngestJob (source=s3://$$bucket/html/) to $$queue_url" ; \
	aws --profile inmo sqs send-message \
		--queue-url "$$queue_url" \
		--message-body "{\"source\":\"s3://$$bucket/html/\"}" \
		--output table

# Live-tail one Lambda's CloudWatch log group. Default service is
# process-user-prompt; override with SERVICE=<name>.
#   make aws-logs
#   make aws-logs SERVICE=vector-query
aws-logs:
	aws --profile inmo logs tail /aws/lambda/inmo-dev-$(or $(SERVICE),process-user-prompt) --follow --since 5m

# Invalidate the CloudFront cache for the frontend distribution. Use after
# `make up STACK=frontend` to bypass the ~24h edge TTL and show the new
# build immediately. Returns an invalidation id; takes ~30s to propagate.
fe-invalidate: check-sso
	@DIST_ID=$$(aws --profile inmo cloudfront list-distributions \
		--query "DistributionList.Items[?contains(Origins.Items[0].DomainName,'inmo-dev-frontend')].Id" \
		--output text) ; \
	if [ -z "$$DIST_ID" ]; then echo "❌ No frontend CloudFront distribution found"; exit 1; fi ; \
	echo "▶ invalidating distribution $$DIST_ID" ; \
	aws --profile inmo cloudfront create-invalidation \
		--distribution-id "$$DIST_ID" --paths "/*" \
		--query 'Invalidation.[Id,Status]' --output table

# Print live URLs + console links for every resource we deploy. Pulls the
# account id and the FE/API endpoints from current Pulumi outputs so the
# values reflect what's actually deployed (or shows "(not deployed)").
show-cloud-resources: check-sso
	@account=$$(aws --profile inmo sts get-caller-identity --query Account --output text) ; \
	region=eu-west-1 ; \
	fe_url=$$(cd frontend && pulumi stack output url --stack dev 2>/dev/null || echo "(not deployed)") ; \
	api_url=$$(cd api-gateway && pulumi stack output endpoint --stack dev 2>/dev/null || echo "(not deployed)") ; \
	echo "" ; \
	echo "🌍 inmo-dev — account $$account, region $$region" ; \
	echo "" ; \
	echo "── Live URLs ──────────────────────────────────────────────────────" ; \
	printf "  %-22s %s\n" "Frontend (CloudFront)" "$$fe_url" ; \
	printf "  %-22s %s\n" "API Gateway endpoint" "$$api_url" ; \
	echo "" ; \
	echo "── One-shot view (every resource by tag) ──────────────────────────" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/resource-groups/tag-editor/find-resources?region=%s\n" "Tag Editor" "$$region" "$$region" ; \
	echo "                         filter: Project=inmobiliarIA-jupiter" ; \
	echo "" ; \
	echo "── Per-service consoles (regional → $$region) ─────────────────────" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/apigateway/main/apis\n"             "API Gateway"      "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/lambda/home\n"                       "Lambda"           "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/sqs/v3/home\n"                       "SQS"              "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/ecr/repositories\n"                  "ECR"              "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/cloudwatch/home#logsV2:log-groups\n" "CloudWatch Logs"  "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/systems-manager/parameters\n"        "SSM Parameters"   "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/dynamodbv2/home#tables\n"            "DynamoDB"         "$$region" ; \
	printf "  %-22s https://s3.console.aws.amazon.com/s3/buckets?region=%s\n"              "S3 buckets"       "$$region" ; \
	printf "  %-22s https://%s.console.aws.amazon.com/events/home#/rules\n"                "EventBridge"      "$$region" ; \
	echo "" ; \
	echo "── Global consoles (always us-east-1 in the URL) ──────────────────" ; \
	printf "  %-22s https://us-east-1.console.aws.amazon.com/cloudfront/v4/home#/distributions\n" "CloudFront" ; \
	printf "  %-22s https://us-east-1.console.aws.amazon.com/iam/home#/roles\n"                   "IAM roles" ; \
	echo "" ; \
	echo "Filter most lists by 'inmo-dev' to find what we created." ; \
	echo ""

# Nuclear option — destroy every stack in REVERSE dependency order. Leaves
# `_bootstrap` alone (you'd lose all state references); destroy that
# manually + via the AWS console if you really mean to wipe everything.
destroy-all: check-sso
	@set -e ; \
	echo "⚠  This will destroy every Pulumi stack except _bootstrap." ; \
	printf "Type 'destroy' to confirm: " ; \
	read confirm ; \
	if [ "$$confirm" != "destroy" ]; then echo "aborted." ; exit 1 ; fi ; \
	for stack in frontend data-ingestion ranking-and-rendering vector-query process-user-prompt api-gateway platform; do \
		echo "" ; \
		echo "▶ destroying $$stack" ; \
		(cd $$stack && pulumi destroy --stack dev --yes) || echo "  (skipped — stack may not exist)" ; \
	done

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
