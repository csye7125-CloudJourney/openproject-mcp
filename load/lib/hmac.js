import crypto from 'k6/crypto';

// matches webhooks/ingest.py hmac validation:
//   X-OpenProject-Signature: sha256=<hex hmac of raw body>

export function sign(body, secret) {
  const hex = crypto.hmac('sha256', secret, body, 'hex');
  return `sha256=${hex}`;
}
