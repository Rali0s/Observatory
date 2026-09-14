> Current implementation update: see [Story Studio, storage and direct Bitcoin](STORY_STUDIO_AND_DIRECT_BITCOIN.md). Direct Xverse checkout no longer requires BTCPay; live payments remain disabled pending receiving-wallet setup. The platform brand is The Observatory.

# Publishing membership policy

$18 USD buys 4,320 Bitcoin blocks, approximately 30 days. Redemption is $27 plus $18 membership: $45 total. Terms are prepaid, not automatic billing or guaranteed calendar months.

| Stage | Confirmed block boundary | Publishing | Price |
| --- | --- | --- | --- |
| Free | No term | Locked | $18 to start |
| Active | Before expiry E | Open | $18 to extend |
| Renewal | E to E+4,319 | Locked | $18 |
| Final renewal | E+4,320 to E+6,479 | Locked | $18 |
| Redemption | E+6,480 onward | Locked | $45 |

Accounts, private tools, analysis and exports remain free throughout. Existing posts remain public until withdrawn or moderated. No account or manuscript deletion occurs. Interfaces say redemption rather than deletion.

The clock is mainnet tip minus five blocks (six-confirmation height); estimates use 144 blocks/day. The worker polls every minute. Data older than five minutes pauses publishing and new checkout until verification returns. Deep reorganizations and source outages require monitoring.

Only server-verified BTCPay Settled invoices activate membership. Invoice identity, USD amount and order metadata must match. Transactional account/order locks prevent duplicate extension. Early renewal keeps unused blocks; late renewal starts from current confirmed height. Invoices quote a price for 15 minutes; delayed settlement of that issued invoice is honored.

Uncertain invoice creation reserves the order for 15 minutes. If no invoice ID was returned, an operator must reconcile BTCPay metadata before requesting another payment. Recovery tooling, refunds and live wallet tests remain launch work. No Stripe, wallet custody, direct wallet connection or ordinal minting is implemented. Live checkout is disabled without credentials.
