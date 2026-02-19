# Internal License Issuance

This flow is for internal operators issuing `license.v1` files with explicit `kid` key selection.

## 1) Generate issuer key once

Choose a new `kid` and generate:

```bash
./bin/mk-license-keygen \
  --kid mk-prod-2026-02 \
  --out-priv ./secrets/mk-prod-2026-02.priv.raw32 \
  --out-keyring ./dist/license_public_keys.json
```

Notes:
- Private key output is raw 32-byte Ed25519 seed and is set to mode `0600`.
- Keyring format is JSON map: `{ "kid": "pubkey_b64_raw32" }`.
- JSON output is deterministic (`indent=2`, `sort_keys=True`).

To append a new `kid` into an existing keyring:

```bash
./bin/mk-license-keygen \
  --kid mk-prod-2026-03 \
  --out-priv ./secrets/mk-prod-2026-03.priv.raw32 \
  --out-keyring ./dist/license_public_keys.json \
  --merge-keyring ./dist/license_public_keys.json
```

## 2) Issue a customer license

Set the issuer private key path:

```bash
export MODEKEEPER_ISSUER_PRIVKEY_PATH=./secrets/mk-prod-2026-02.priv.raw32
```

Issue license:

```bash
./bin/mk-license-issue \
  --kid mk-prod-2026-02 \
  --org "Customer Inc" \
  --expires 2027-12-31T23:59:59Z \
  --entitlements apply,observe,paid \
  --out ./dist/customer_inc.license.json
```

## 3) What to send to customer

Send exactly:
- License file (for example `customer_inc.license.json`)
- Keyring file used for verification (for example `license_public_keys.json`)

Recommended customer placement:
- `~/.config/modekeeper/license.json`
- `~/.config/modekeeper/license_public_keys.json`

Customer verifies with zero env and no `--license`:

```bash
mk license verify --out ./report/_license_verify
```

Verifier artifact (`license_verify_latest.json`) includes:
- `license_ok`, `kid`, `issuer`, `expiry`, `entitlements`
- `reason_code` (stable outcome code)
- `failure_code`, `failure_detail` (when blocked; safe reason-coded values only)

## 4) Rotate `kid`

Rotation flow:
1. Generate a new keypair with a new `kid`.
2. Merge the new `kid` into keyring allowlist (keep old `kid` entries).
3. Start issuing new licenses with the new `kid`.
4. Keep old `kid` in keyring while old licenses must remain valid.
5. Remove old `kid` from keyring only after migration window is complete.

Verifier semantics stay unchanged:
- If `kid` exists in license, verifier uses only that key.
- Unknown `kid` is `license_invalid`.
- If no `kid` is present, verifier may fall back to allowlist scan.

## 5) Optional trust chain mode

Trust chain mode is available for explicit verify runs:

```bash
mk license verify \
  --trust-chain \
  --issuer-keyset ./dist/issuer_keyset.json \
  --root-public-keys ./dist/root_public_keys.json \
  --license ./dist/customer_inc.license.json \
  --out ./report/_license_verify
```

`issuer_keyset.json` contract:
- `schema_version: issuer_keyset.v1`
- `root_kid`: key id from root allowlist
- `keys`: JSON map `{kid -> pubkey_b64_raw32}` for issuer keys
- `signature`: Ed25519 signature by selected root key over canonical JSON (`sort_keys=True`, `separators=(',',':')`) of keyset object without `signature`.

Default production flow remains allowlist-by-`kid` when trust-chain mode is not enabled.
