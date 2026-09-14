# Observatory ordinal editions

## Operator controls

Django admin → Studio → Ordinal minting controls (Ordinal settings). The singleton is seeded OFF. `enabled` gates preparation and the server wallet-start endpoint. `special_sats_enabled` additionally gates preparation of special-sat editions. Pausing does not hide verified editions, remove collection links, stop confirmation of existing attempts, or undo Bitcoin broadcasts. An already-open wallet request cannot be revoked by this switch.

Set `ORDINAL_INDEX_URL` to an operator-trusted HTTPS mainnet `ord server` with the JSON API and sat index enabled. The app requires `/status`, `/inscription/{id}`, `/content/{id}`, and `/sat/{number}`. It checks exact UTF-8 content hash, mainnet index height, the selected sat, and six canonical confirmations against the existing Esplora/ChainTip configuration. No public index is silently selected. Run `sync_memberships --loop` for automatic reconciliation of submitted inscription IDs; the post also has a rate-limited manual check.

## Author workflow

1. Publish through the existing membership flow. On the public post, open **Ordinal edition**.
2. Freeze one edition with a name, description, up to 20 metadata attributes, and explicit permanent-publication consent. A sandboxed preview and downloads show exactly what will be inscribed.
3. Regular: review fees and authorize `createInscription` in Xverse. No platform fee is added. Xverse supplies its own inscription recipient; the app does not claim the returned transaction ID proves ownership or settlement.
4. Special: enter the exact sat number, download the unchanged HTML, and use Gamma's inscription tools to select that sat and approve fees. This is a manual external flow, not a Gamma API integration or a source of rare-sat inventory. Sat rarity is read from the index; choosing “special” does not fabricate rarity. Historical/exotic traits such as Pizza are not independently certified here.
5. Paste the reveal inscription ID (`txidiN`). A wallet transaction ID may be the commit, so the app never guesses `i0`. Once verified, the existing public post and author profile automatically display the Observatory sats icon. This does not create a duplicate post, change its original publication date, or reverse withdrawal/moderation.
6. Add a specific HTTPS Gamma listing URL to enable **Collect on Gamma**. This is an author-provided external listing; availability, price, wallet approval and ownership transfer happen on Gamma. Observatory does not claim a listing is live, verify its contents, or maintain collector ownership histories. Bookmarks remain reading-list saves.

## Metadata and edition limits

The inscription is a self-contained, escaped HTML reading edition. Metadata is embedded in its content and exported as companion JSON, NOT protocol tag-5 CBOR metadata or a preformatted Gamma collection import. One immutable edition per post is supported. Public profiles offer Publications and Ordinal editions tabs. There is no edition-supply contract, batch mint, royalty enforcement, or in-app resale settlement.

## Recovery and validation

Wallet attempts are recorded before opening Xverse. The SDK's `onCancel` also runs for transport errors, so it is not sufficient evidence of cancellation: the app leaves ambiguous attempts blocked from automatic retry. Check Xverse for a broadcast; an externally completed inscription can be tracked with the same frozen content. Operator-assisted retry recovery is still required when no transaction was broadcast. Never clear an attempt merely because the browser timed out.

Verification trusts the configured ord index and Esplora sources. Six confirmations reduce reorganization risk; continuously auditing already-minted editions after deep reorganizations remains future work. Live wallet minting, rare-sat execution and purchases have not been exercised with real Bitcoin. Local tests mock chain responses and wallet calls. Before enabling publicly, validate those flows end-to-end with the operator's index and wallet.

## References

- Xverse inscription API: https://docs.xverse.app/sats-connect/bitcoin-methods/createinscription
- Gamma special sats: https://support.gamma.io/hc/en-us/articles/28511767752851-Minting-on-Special-Sats
- Ord server API: https://docs.ordinals.com/guides/api.html
- Native metadata format: https://docs.ordinals.com/inscriptions/metadata.html
