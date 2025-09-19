"""Webhook ingest + kafka replay path.

OpenProject posts JSON to /webhooks/openproject. We HMAC-validate, publish
to a durable kafka topic, and a background consumer hydrates an in-memory
recent-events cache that the get_recent_events MCP tool reads from.
"""
