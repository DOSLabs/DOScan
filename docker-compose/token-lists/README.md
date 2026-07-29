# DOS Chain token lists

This directory is the source of truth for curated ERC-20 metadata imported by the
DOScan backend.

Blockscout reads the environment-specific list through `TOKEN_LIST_URL` when
the backend starts and refreshes it every 24 hours. Entries use the Token Lists
schema and may provide:

- `chainId`
- `address`
- `name`
- `symbol`
- `decimals`
- `logoURI`

The backend imports the logo, name, symbol, and decimals for tokens that match
the configured chain ID. Existing on-chain name, symbol, and decimals are not
overwritten by the list.

Project descriptions, websites, support links, and social links do not belong
in this list. Those fields are served by the separate Contract Info/Metadata
Service endpoint consumed by the frontend.

## Adding a token

1. Add a permanent SVG or PNG under `assets/`.
2. Add the token to the matching network JSON file. Do not configure an empty
   token list for a network without a verified token deployment.
3. Use the checksummed contract address and the network's exact chain ID.
4. Increment the list version and timestamp.
5. Confirm the token contract exists and its on-chain metadata matches the list.
