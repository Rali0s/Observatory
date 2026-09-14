# Account merging and Xverse conflicts

Open **Account → Merge password and wallet accounts** (`/account/merge/`). A wallet-link conflict also offers this link. Merging is available on desktop and mobile.

1. Verify the current account with its password or an already-linked Xverse address.
2. Verify the other account with its username/password or linked Xverse payment/ordinal address. Wallet-only accounts do not need a password.
3. Review the selected main account, check the ownership confirmation, and select **Merge accounts**.

Verification lasts ten minutes and is tied to the browser session. Wallet proofs explicitly describe account-merge verification and never authorize payment. They cannot silently link, transfer, or merge an account. An existing signed-in session alone is not enough: both accounts require fresh proof.

## What is kept

The main account is selected by superuser/staff privileges, then paid membership/history, then linked-wallet ownership. Ties keep the account that started the merge. Its username and public pen name remain primary. Both original password usernames continue signing in to the main account; all linked wallets move with them. Admin privileges and selected-member invitation permissions are preserved.

Private projects (including chapters, revisions, notes, and art), publications, wallets, payment orders, invitations, saved posts, follows, votes, achievements, and completed ordinal history are consolidated. Duplicated saved items/follows/votes collapse into one; self-follows and self-votes are removed. Duplicate invite redemption and report records remain on the retired account for audit. Old author-profile URLs redirect to the main profile. The secondary profile and its biography remain retained; an empty main biography is filled from the secondary one.

Unused paid block terms add together using a fresh verified block height. Expired terms do not generate new access. Remaining time-limited invite access also combines; lifetime access wins. Existing quota grants keep the larger effective limits. Primary profile decoration preferences are retained when both accounts have them.

The secondary account is retired, not deleted. Its old sessions stop authenticating. An account-merge record preserves the original identities and profile details. The app has no undo control; operator intervention would be needed to disentangle later changes. No live account is merged by a deployment or merely by opening this page.

## Payments and concurrency

`PaymentOrder.billing_user_id` preserves the original Stripe checkout user identity when orders move. Verified callbacks can still settle into the main account, and each order is applied once. A worker holding an outdated owner snapshot rejects it and retries with fresh ownership. Two existing paid memberships require a fresh chain observation before their remaining time can be combined.

Pending ordinal trades must finish or be resolved before merging, so an in-flight signed trade cannot change ownership mid-broadcast. Wallet addresses and inscription ownership are not changed on-chain.

Merges lock both accounts in sorted order and consume a database-backed attempt once. Authenticated writes lock the active account for the request, preventing a stale write from recreating content under a just-retired account. Confirmation uses its own ordered locks. Expired, cancelled, reused, cross-session, password-changed, and wallet-reassigned proofs cannot merge accounts.

## Verification

Regression tests cover password and cryptographic wallet proofs, wallet conflict actions, priority, content/entitlement preservation, alias logins, retired sessions, duplicate relationships, old profile links, repeated merges, and late Stripe fulfillment. PostgreSQL tests exercise duplicate simultaneous merges and payment fulfillment racing a merge. Browser testing used disposable local accounts and confirmed both proofs, paid-account priority, the mobile review, and successful consolidation. Real Xverse-device interaction still requires the account owner's wallet approval.
