# Xverse connection

Account and Membership now link to `/account/wallet/`. It requests a mainnet payment-address connection using the pinned Sats Connect SDK. The displayed address stays in the page; no transaction, invoice, login credential or publishing entitlement is created by connecting. The paying wallet is separate from the site's receiving wallet.

Checkout now remembers a transfer attempt within the browser tab. Refreshing that tab does not immediately offer another payment. An ambiguous transfer response keeps retry disabled until the author checks wallet history; explicit wallet rejection permits retry. This is a user-interface safeguard, not proof of payment. The server still independently verifies transactions and credits each order once.

To enable collection, first supply an unused-address export from the site's own Bitcoin wallet. Import it with `python manage.py import_receiving_addresses PATH`, then configure DIRECT_BITCOIN_ENABLED=1 and the shared membership worker. No private keys or seed phrases are needed. See [direct-payment setup](STORY_STUDIO_AND_DIRECT_BITCOIN.md) for operational requirements.

The connection requires an Xverse-capable browser. No live extension connection or Bitcoin payment was performed by the assistant. Source: [Xverse wallet_connect](https://docs.xverse.app/sats-connect/connecting-to-the-wallet/connect-to-xverse-wallet).
