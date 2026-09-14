# Observatory ordinal editions

## Operator controls

Django admin → Studio → Ordinal minting controls (Ordinal settings). The singleton is seeded OFF. `enabled` gates preparation and the server wallet-start endpoint. `special_sats_enabled` additionally gates preparation of special-sat editions. Pausing does not hide verified editions, remove collection links, stop confirmation of existing attempts, or undo Bitcoin broadcasts. An already-open wallet request cannot be revoked by this switch.

Set `ORDINAL_INDEX_URL` to an operator-trusted HTTPS mainnet `ord server` with the JSON API, sat index, and rune index enabled. The app requires `/status`, `/output/{outpoint}`, `/inscription/{id}`, `/content/{id}`, and `/sat/{number}`. It checks exact UTF-8 content hash, mainnet index height, the selected sat, and six canonical confirmations against the existing Esplora/ChainTip configuration. The launch deployment explicitly uses `https://ord-mainnet.gamma.io`. Run `sync_memberships --loop` for automatic reconciliation of submitted inscription IDs; the post also has a rate-limited manual check.

## Author workflow

1. Publish through the existing membership flow. On the public post, open **Ordinal edition**.
2. Enter a name, description, optional collection/language/genre, and up to 17 additional name/value traits. No JSON entry is required. Calculate a fee estimate, give explicit permanent-publication consent, then freeze the edition. A sandboxed preview and downloads show exactly what will be inscribed; the UTF-8 HTML limit is 350,000 bytes.
3. Regular: the rare-sat fields are hidden. Refresh the frozen edition's fee estimate and authorize `createInscription` in Xverse. The launch platform fee is **0 sats**. Xverse supplies its own inscription recipient; the app does not claim the returned transaction ID proves ownership or settlement.
4. Special: link an Ordinals wallet with a signature, load its confirmed outputs, and select a rare sat from the dropdown. Observatory reads classical rarity from indexed sat ranges, excluding bundles with inscriptions or runes. Scans cover 12 outputs per page, up to 200 candidates per page; use “Scan more outputs” to continue. Signed choices expire after ten minutes and ownership, unspent status, canonical confirmation, and exact sat offset are rechecked when freezing. Download the unchanged HTML and use Gamma's inscription tools to choose that same sat and approve fees. Xverse's standard inscription API cannot choose a specific sat. Gamma execution remains an external manual flow; historical/exotic traits such as Pizza are not independently certified here.
5. Paste the reveal inscription ID (`txidiN`). A wallet transaction ID may be the commit, so the app never guesses `i0`. Once verified, the existing public post and author profile automatically display the Observatory sats icon. This does not create a duplicate post, change its original publication date, or reverse withdrawal/moderation.
6. Add a specific HTTPS Gamma listing URL to enable **Collect on Gamma**. This is an author-provided external listing; availability, price, wallet approval and ownership transfer happen on Gamma. Observatory does not claim a listing is live, verify its contents, or maintain collector ownership histories. Bookmarks remain reading-list saves.

## Metadata and edition limits

The inscription is a self-contained, escaped HTML reading edition. Metadata is embedded in its content and exported as companion JSON, NOT protocol tag-5 CBOR metadata or a preformatted Gamma collection import. One immutable edition per post is supported. Public profiles offer Publications and Ordinal editions tabs. There is no edition-supply contract, batch mint, royalty enforcement, or in-app resale settlement.

## Fees and receiving wallets

Live economy, standard, and fast rates come from `BITCOIN_FEE_URL` (default: mempool.space's recommended-fees API), cached for one minute. If unavailable, a custom rate from 1 to 1,000 sats/vB can still produce an estimate. The estimate counts UTF-8 content bytes and models commit plus reveal transaction size, with a range for funding inputs/change. It includes a 546-sat postage planning allowance and separately displays the platform fee. Wallet input count, actual postage, and provider charges can change the final amount; provider charges are excluded. The wallet/provider must show the final transaction before approval.

Regular-mint quotes expire after five minutes and are signed against the immutable edition, content hash, rate, platform fee, and recipient. Changing the policy or content requires a new quote before a mint attempt can start. `ORDINAL_PLATFORM_FEE_SATS=0` omits both `appFee` and `appFeeAddress` from Xverse. Future nonzero fees must be explicitly configured (546–1,000,000 sats); Gamma estimates do not add an Observatory fee.

Registered public wallet references, also shown to admins on the wallet page:

| Role | Address |
| --- | --- |
| Portal membership | `bc1qhke8vfglf2t2gu8tv7pm3x7yma3uz8ucndfaex` |
| Ordinal platform fees | `bc1qzs2nsqjhx8hnrg4vvlzzpmp3smjkh0xl75h90g` |
| Redemption | `bc1qwfsp8c2af6lxkmqmddu53s7pcmck6936rwg8wm` |

Miner fees go to miners, not the platform-fee wallet. Membership and redemption invoices continue to require unused invoice addresses for unambiguous payment attribution; these shared references are not automatically inserted into that pool. Registering these settings does not activate payments or trading.

## Recovery and validation

Wallet attempts are recorded before opening Xverse. The SDK's `onCancel` also runs for transport errors, so it is not sufficient evidence of cancellation: the app leaves ambiguous attempts blocked from automatic retry. Check Xverse for a broadcast; an externally completed inscription can be tracked with the same frozen content. Operator-assisted retry recovery is still required when no transaction was broadcast. Never clear an attempt merely because the browser timed out.

Verification trusts the configured ord index and Esplora sources. Six confirmations reduce reorganization risk; continuously auditing already-minted editions after deep reorganizations remains future work. Live wallet minting, rare-sat execution and purchases have not been exercised with real Bitcoin. Local tests mock chain responses and wallet calls. Before enabling publicly, validate those flows end-to-end with the operator's index and wallet.

## References

- Xverse inscription API: https://docs.xverse.app/sats-connect/bitcoin-methods/createinscription
- Gamma special sats: https://support.gamma.io/hc/en-us/articles/28511767752851-Minting-on-Special-Sats
- Ord server API: https://docs.ordinals.com/guides/api.html
- Native metadata format: https://docs.ordinals.com/inscriptions/metadata.html
