# NFT Media Handler

## Status

The Blockscout NFT Media Handler is enabled in inline mode on DOS Chain Mainnet and Testnet.

| Environment | Backend | Bucket prefix | Public media base URL |
|---|---|---|---|
| Mainnet | `doscan-l1-backend-1` on `doscan-mainnet` | `mainnet/nft-media` | `https://storage.googleapis.com/doscan/mainnet/nft-media/` |
| Testnet | Blockscout backend on `dos-testnet-r0` | `testnet/nft-media` | `https://storage.googleapis.com/doscan/testnet/nft-media/` |

The handler runs inside the existing Blockscout backend. It does not require a separate media-handler container.

## Architecture

1. Blockscout reads an NFT image or animation URL from token metadata.
2. The inline media handler downloads and validates the source.
3. The handler uploads the original object and generated thumbnails to Google Cloud Storage through the S3-compatible XML API.
4. Blockscout stores the object template and thumbnail sizes in `token_instances.thumbnails`.
5. The frontend reads the public object URLs from `https://storage.googleapis.com/doscan`.

Google Cloud Storage is compatible with this Blockscout integration because the handler uses the S3-compatible API exposed by `storage.googleapis.com`. Cloudflare R2 is not required.

## Configuration

Shared non-secret settings are defined in `docker-compose/envs/common-blockscout.env`:

```dotenv
NFT_MEDIA_HANDLER_ENABLED=true
NFT_MEDIA_HANDLER_REMOTE_DISPATCHER_NODE_MODE_ENABLED=false
NFT_MEDIA_HANDLER_AWS_BUCKET_HOST=storage.googleapis.com
NFT_MEDIA_HANDLER_AWS_BUCKET_NAME=doscan
NFT_MEDIA_HANDLER_AWS_PUBLIC_BUCKET_URL=https://storage.googleapis.com/doscan
NFT_MEDIA_HANDLER_BACKFILL_ENABLED=true
```

Environment-specific prefixes are defined in:

- `docker-compose/envs/common-blockscout-mainnet.env`
- `docker-compose/envs/common-blockscout-testnet.env`

The production bucket is exactly `gs://doscan`. Mainnet and Testnet share the bucket but use separate prefixes.

## Credentials and deployment

The HMAC credential is stored in Google Secret Manager as `doscan-nft-media-hmac`. The secret JSON contains the storage host, access ID, service account, secret, and bucket name. Never commit or print the HMAC values.

`deploy-config.yml` performs the following steps:

1. Authenticates through GitHub Actions Workload Identity Federation.
2. Reads the latest enabled Secret Manager version.
3. Validates that the secret targets bucket `doscan` and host `storage.googleapis.com`.
4. Creates a temporary mode-0600 env file containing only the two HMAC variables.
5. Copies the deployment archive through IAP.
6. Merges the HMAC values into the VM secret env file without printing them.
7. Removes local and remote temporary credential files.
8. Force-recreates the Mainnet backend when a backend env file or HMAC credential changes.
9. Runs a write-read-delete runtime probe against GCS and verifies that the inline dispatcher process exists.

The deployment service account has secret accessor permission only for `doscan-nft-media-hmac`.

## Bucket security

- Public access prevention is overridden only where required for the `doscan` bucket.
- Anonymous users receive the custom project role `doscanPublicObjectReader`, containing only `storage.objects.get`.
- Anonymous users cannot list, upload, overwrite, or delete objects.
- The HMAC service account writes media objects. It must not be used by frontend code or exposed to browsers.
- Mainnet and Testnet currently share one HMAC credential. Rotation affects both environments, so rotate through Secret Manager and redeploy both environments in the same maintenance window.

## Rotation procedure

1. Create a new HMAC key for `doscan-nft-media@dos--ai.iam.gserviceaccount.com`.
2. Add a new Secret Manager version to `doscan-nft-media-hmac`.
3. Verify the JSON fields and bucket name without printing the secret value.
4. Deploy Mainnet and Testnet through `deploy-config.yml`.
5. Confirm both backend containers are healthy and use the expected bucket prefixes.
6. Upload or process a test NFT and verify original plus 60, 250, and 500 pixel objects.
7. Disable the previous HMAC key only after both environments pass.

## Verification

The initial production rollout was merged through:

- [PR #115](https://github.com/DOS/DOScan/pull/115), GCS-backed NFT media processing
- [PR #116](https://github.com/DOS/DOScan/pull/116), backend recreation when env files change
- [PR #117](https://github.com/DOS/DOScan/pull/117), write-read-delete runtime verification
- [PR #119](https://github.com/DOS/DOScan/pull/119), short Erlang node names for Docker service DNS
- [PR #120](https://github.com/DOS/DOScan/pull/120), matching node naming for the optional standalone worker
- [Deployment run 30331379243](https://github.com/DOS/DOScan/actions/runs/30331379243), Mainnet and Testnet runtime probes successful

Mainnet evidence after the hotfix:

- Backend container creation time: `2026-07-28T05:24:02Z`
- Container state: healthy
- `NFT_MEDIA_HANDLER_ENABLED=true`
- `NFT_MEDIA_HANDLER_AWS_BUCKET_NAME=doscan`
- `NFT_MEDIA_HANDLER_BUCKET_FOLDER=mainnet/nft-media`
- Local Blockscout API health check passed
- The release RPC connected to the running backend and completed the GCS write-read-delete probe

Testnet end-to-end evidence:

- Contract: `0x9f2accb76defe1735fb55c41e1741c54a2d0fea7`
- Token ID: `1`
- Stored media type: `image/png`
- Thumbnail template: `/testnet/nft-media/7b8e97c33251b92003aa6c06833ab64a8b529855_{}.png`
- Generated sizes: 60, 250, and 500 pixels
- `cdn_upload_error` was empty
- Anonymous access to a known thumbnail returned HTTP 200, while anonymous bucket listing returned HTTP 403 through the XML API and HTTP 401 through the JSON API.

## Troubleshooting

- If configuration files changed but the container creation time did not, inspect the force-recreate logic in `deploy-config.yml`.
- If release RPC reports an illegal hostname, keep Compose service hostnames on `RELEASE_DISTRIBUTION=sname` and ensure every participating Erlang node uses the same distribution mode.
- If uploads return an authorization error, verify the active HMAC key and bucket IAM bindings without printing secrets.
- If public objects return HTTP 403, verify the anonymous `doscanPublicObjectReader` binding and the bucket-level public access prevention setting.
- If the database has no thumbnail template, inspect backend logs and `cdn_upload_error` for the affected token instance.
- If Mainnet has no indexed NFT instances, validate the handler on Testnet rather than fabricating a Mainnet fixture.
