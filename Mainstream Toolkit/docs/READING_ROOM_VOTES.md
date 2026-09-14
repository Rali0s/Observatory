# Reading Room votes and discovery

Free accounts can like each visible post once and remove their own like. Authors cannot upvote their own work. A database uniqueness constraint prevents duplicates; mutations require authenticated, CSRF-protected POST requests.

Top ranked orders by total likes, then publication time (newest first), then publication ID for stable ordering. Rank numbers continue across pages within the selected filters. Removal recalculates rank on the next page load. This is all-time ranking without paid boosts or time decay.

New posts offers a chronological feed and a three-post sidebar. Channel and hashtag filters apply to both. Withdrawn posts are excluded. No demo votes were fabricated.

Before broad launch, add account verification and voting abuse controls: one vote per account cannot guarantee one vote per human.

## Ordinal inscriptions

Ordinal minting is not implemented. Xverse connects a payment address and requests Bitcoin membership payments; it does not inscribe publications. An optional future “Inscribe this edition” flow needs an immutable edition preview, separate fee quote, explicit wallet approval, and inscription tracking. Private drafts must never be inscribed automatically.
