"""Per-service SQS publisher hook.

Empty placeholder. ``routes`` currently calls ``shared.sqs.publish`` directly;
api_gateway-specific publishing concerns (auth-derived attributes, batching,
metrics) will move into this module as they emerge.
"""
