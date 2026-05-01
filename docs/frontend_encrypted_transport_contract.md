# Frontend Encrypted Transport Contract (v17)

## Scope
This backend repo implements encrypted transport support for sensitive questionnaire v2 endpoints.
Frontend code is **not** modified here.

## Endpoints to use
1. Public key/config bootstrap:
   - `GET /api/v2/security/transport-key`
2. Encrypted results (recommended, replaces plaintext legacy results endpoint):
   - `POST /api/v2/questionnaires/history/{session_id}/results-secure`
3. Encrypted clinical summary (new simulated diagnostic report):
   - `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`
4. Sensitive write endpoints (support encrypted request/response):
   - `POST /api/v2/questionnaires/sessions`
   - `PATCH /api/v2/questionnaires/sessions/{session_id}/answers`
   - `POST /api/v2/questionnaires/sessions/{session_id}/submit`

Legacy plaintext endpoint remains available for compatibility:
- `GET /api/v2/questionnaires/history/{session_id}/results`
- Status header: `X-CognIA-Endpoint-Status: legacy_plaintext`

## Transport key fetch
Request:
- `GET /api/v2/security/transport-key`
- Auth: Bearer token

Response shape:
```json
{
  "key_id": "transport-key-v1",
  "algorithm": "RSA-OAEP-256+AES-256-GCM",
  "public_key_jwk": {"kty":"RSA","alg":"RSA-OAEP-256","use":"enc","n":"...","e":"AQAB"},
  "expires_at": "2026-05-01T...Z",
  "version": "transport_envelope_v1"
}
```

## Request envelope format
Required headers for encrypted calls:
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`

Body:
```json
{
  "encrypted": true,
  "version": "transport_envelope_v1",
  "key_id": "transport-key-v1",
  "alg": "AES-256-GCM",
  "encrypted_key": "...",
  "iv": "...",
  "ciphertext": "...",
  "aad": "transport_envelope_v1|your_context"
}
```

## Response envelope format
When request is encrypted and backend encryption is enabled, response comes encrypted:
```json
{
  "encrypted": true,
  "version": "transport_envelope_v1",
  "key_id": "transport-key-v1",
  "alg": "AES-256-GCM",
  "iv": "...",
  "ciphertext": "...",
  "aad": "transport_envelope_v1|transport-key-v1"
}
```

Response headers:
- `X-CognIA-Encrypted: 1`
- `X-CognIA-Crypto-Version: transport_envelope_v1`

## WebCrypto flow (frontend)
1. Fetch transport key from `/api/v2/security/transport-key`.
2. Generate random 32-byte AES key (`AES-GCM`) per request or very short-lived session.
3. Generate unique 12-byte IV per encrypted request.
4. Serialize payload JSON UTF-8 and encrypt with AES-GCM.
5. Encrypt AES key with backend RSA public key (`RSA-OAEP-256`).
6. Send envelope + required headers.
7. Decrypt response envelope with same AES key.

## TypeScript pseudocode
```ts
async function encryptRequest(payload: unknown, transportKey: TransportKey) {
  const aesKeyBytes = crypto.getRandomValues(new Uint8Array(32));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const aad = new TextEncoder().encode("transport_envelope_v1|frontend");

  const aesKey = await crypto.subtle.importKey("raw", aesKeyBytes, "AES-GCM", false, ["encrypt", "decrypt"]);
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad }, aesKey, plaintext);

  const rsaKey = await crypto.subtle.importKey("jwk", transportKey.public_key_jwk, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt"]);
  const encryptedKey = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, rsaKey, aesKeyBytes);

  return {
    envelope: {
      encrypted: true,
      version: "transport_envelope_v1",
      key_id: transportKey.key_id,
      alg: "AES-256-GCM",
      encrypted_key: b64url(encryptedKey),
      iv: b64url(iv),
      ciphertext: b64url(ciphertext),
      aad: "transport_envelope_v1|frontend"
    },
    aesKeyBytes
  };
}
```

## Error handling
- `400 plaintext_not_allowed`: plaintext request rejected by policy.
- `400 encrypted_payload_invalid`: envelope malformed or decrypt failure.
- `401/403`: auth/permission error.
- `5xx`: backend internal error.

## Feature flags and environment
- Backend flag: `COGNIA_TRANSPORT_PAYLOAD_ENCRYPTION=true`
- Production policy can reject plaintext for sensitive endpoints.
- In transition/dev environments plaintext may be allowed by backend policy.

## What frontend must NOT do
- Do not persist plaintext clinical payloads in `localStorage` or `sessionStorage`.
- Do not log clinical payloads to `console.log`.
- Do not send sensitive endpoints in plaintext when encrypted contract is enabled.
- Do not cache decrypted reports unencrypted.

## Memory handling recommendation
- Keep decrypted payloads only in short-lived in-memory state.
- Clear sensitive state on logout/session end.
- Avoid redux-persist/localStorage for decrypted clinical content.

## Honest limitation
- Network tab will show ciphertext when encrypted transport is used.
- UI must decrypt data to render it, so a user controlling browser memory/runtime can still inspect decrypted data.
- This transport encryption does not replace frontend hardening, secure session handling, or endpoint authorization controls.
