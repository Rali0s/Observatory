# The Observatory: Story Studio and direct Bitcoin

## Implemented

The Django platform now includes an editable chapter workbench, section names and numeric chapter order, sanitized Markdown preview, chapter artwork, private notes, chapter summary/imagery/theme candidates from the original `analysis_engine.py`, and PDF/EPUB/Markdown exports using the original `publisher.py`. Existing revisions can be copied into an empty chapter workbench without replacing them. A separate action snapshots the ordered chapters for analysis; synchronous analysis remains capped at 20,000 words. Larger drafts can still be edited and exported within storage limits.

Revision Story Aids includes chapter/scene/passage timelines with an optional overlay, character aliases and context signals, co-occurrence evidence, clue vocabulary, revision-specific foreshadowing annotations, open-clue counts, CSV export and River-profile discontinuity review. These are literary heuristics, not verified plot facts. Optional semantic readings and chapter revision/artwork/action suggestions require configured AI service and explicit per-request sharing consent. No AI calls were made while implementing this release.

Story Studio includes a draggable scene board with keyboard position controls, POV, chapter reference, goal, conflict, outcome and notes. Typed connections include sequence, conflict, support, revelation, dependency, payoff and branch, with condition/effect notes. Boards allow loops and branches, JSON import/export, and reject stale-tab saves. The accompanying story bible stores characters, places, world rules, continuity facts and revision tasks with references and completion status. These are author-maintained records; automatic contradiction detection is not implemented.

## Unlimited reuse

The board schema and validation approach are adapted from the user's `C:/Users/Support/Documents/ChatGPT/Unlimited/unlimited_lab/workflows.py` and `workflow_ui.py`. That application uses catalog cards, typed edges, positions, connection provenance, branches and loops. The Observatory substitutes scene cards and story relationships and implements the interface in browser JavaScript with Django ownership checks. It does not depend on Streamlit Flow, read Unlimited's database or modify the Unlimited project. Card-game rules, artwork and decks were not copied.

## Storage

Every account receives 100,000,000 content bytes by default, configurable through STORAGE_QUOTA_BYTES. Publishing membership does not buy access to private tools or change this allowance. The Storage page shows usage and explicit export/removal controls. Counted content includes revision text and analysis JSON, chapter text/artwork, story boards/vocabulary, notes/tasks, clue annotations, semantic results and public publication snapshots. Metadata, indexes, SQL overhead, backups and payment records are excluded. Actual infrastructure disk use will exceed this logical allowance.

All application content writes share an account-row transaction lock and reject increases above quota. Existing over-quota accounts may read/export and reduce stored content. Cleanup requires explicit selection and confirmation; there is no timed deletion. Removing a revision also removes its attached private notes/annotations/semantic readings; separate public snapshots remain. PostgreSQL concurrency and large-account performance testing remain deployment gates. Storage accounting currently scans owned content; a maintained usage ledger would be preferable at larger scale.

## Direct Xverse payment flow

Direct checkout uses the pinned @sats-connect/core wallet library, bundled locally into `static/xverse-payment.js`. It requests a mainnet payment connection and sends the server-quoted sats using sendTransfer. A transaction broadcast message never activates membership. Django independently discovers transactions to the invoice address, checks amount and canonical block inclusion, and credits only at six confirmations. Each order can credit one 4,320-block term. Expired publishing memberships cost $18 during renewal windows; redemption costs $45 total. Early renewal preserves unused blocks.

No BTCPay account is required for this path. Existing BTCPay orders/code remain available for reconciliation, but direct checkout is preferred when configured. No Stripe, spending key, seed phrase or custodial wallet is added.

### Configure receiving addresses

1. Export a pool of **unused mainnet receiving addresses from a wallet you control**, one per line. Do not export seed phrases or private keys. The address-pool design avoids storing spending keys on the web server. Back up the originating wallet and track its address discovery/gap limit so every issued address remains discoverable during recovery.
2. Run `python manage.py import_receiving_addresses /path/to/addresses.txt`. The importer validates address encoding and mainnet network and never reassigns an already-issued address. Address ownership/unused status must be verified by the operator; encoding validation does not prove control.
3. Set DIRECT_BITCOIN_ENABLED=1 on the web service, and run `python manage.py sync_memberships --loop` with the same SQL database. Refill the address pool before it empties. Receiving addresses are not configured in the delivered local app, so live checkout stays disabled.
4. Verify the full flow in a dedicated staging setup before accepting live membership payments. The current direct adapter is mainnet-only; testnet support and real extension/mobile compatibility are not yet verified. The Codex in-app browser may not have a wallet extension; test an installed Xverse wallet in its supported browser.

Quotes use Coinbase's public BTC/USD spot endpoint and last 15 minutes. Fees are extra. The worker observes transactions independently of the browser; replacement transactions are checked afresh. Late and partial payments require support reconciliation, not another immediate payment. Split payments are not automatically combined. More than 24 transactions to one invoice address triggers review rather than guessing. The worker currently scans up to 100 unpaid orders per pass, including expired orders, so queue latency needs monitoring. Deep reorganizations after activation require operator review; six confirmations reduce rather than eliminate that risk. Quote timing uses local observation or qualifying confirmed block time, which is approximate.

The wallet bundle overrides the SDK's pinned axios version to 1.20.0; the installed dependency audit reports zero known vulnerabilities. Rebuild with `npm ci` and `npm run build` in web_platform/frontend after dependency changes. Keep node_modules out of deployment context.

## Optional AI configuration

Set SEMANTIC_ENABLED=1, OPENAI_NARRATIVE_MODEL to the reviewed model, and OPENAI_API_KEY in the service environment. No local .env secrets are imported into the Django app. Passage interpretation shares the passage, bounded neighboring context, roster and motif counts; chapter-note actions share the chapter excerpt and entered note. Responses request store=False. Suggestions supplement saved work rather than overwriting the manuscript. Per-user request cooldown exists; provider spending budgets and durable job processing remain hosting work. Do not enable this on a public host without cost controls.

## Sources and deployment boundaries

- [Xverse sendTransfer](https://docs.xverse.app/sats-connect/bitcoin-methods/sendtransfer)
- [Xverse wallet connection](https://docs.xverse.app/sats-connect/connecting-to-the-wallet/connect-to-xverse-wallet)
- [Coinbase public spot price](https://docs.cdp.coinbase.com/coinbase-app/track-apis/prices)
- [Esplora transaction/block API](https://github.com/Blockstream/esplora/blob/master/API.md)

Railway hosting has not been executed. Current code uses local SQLite in development; production still requires PostgreSQL, Redis, HTTPS/proxy verification, login abuse protection, account recovery, backups and moderation operations. Long manuscripts need asynchronous analysis before lifting the 20,000-word analysis limit. Streamlit snapshots are not automatically imported; the original app remains available alongside Django.
