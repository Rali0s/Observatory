# Admin access and publishing invites

Active Django staff and superuser accounts have complimentary publishing access, unlimited project count, no membership word quota, and no content storage allowance cap. Ownership checks, input/file validation, and operator switches for external services still apply. Admin access does not depend on the Bitcoin block feed, and active complimentary accounts cannot start a payment checkout.

Open **Account → Invite management → Manage invite codes & track progress** (`/account/invites/`) while signed in as an admin on desktop. Membership also links to the dashboard. Expand **Create an invite code** to create separate campaigns for **Free three months** and **Lifetime access**, choose a maximum number of recipients (default one), and optionally set a UTC redemption deadline. Save the full code and shareable invite link when they appear: the invitation record retains only its SHA-256 hash and short hint. Send the link or code privately yourself. No email or social post is sent automatically.

The dashboard shows total campaigns, available codes, and redeemed places. Search campaign names or code prefixes, filter by pass type and Available / Fully used / Expired / Disabled status, and page through all campaigns. Status precedence is disabled, expired deadline, full capacity, then available. Overview counts cover all campaigns accessible to the issuer before filtering.

Open a campaign to see redemption progress, unused capacity, creation/deadline timestamps, and paginated recipient history. History records redemption time and the grant made then (three-month expiry or lifetime). A historical grant ending does not imply the account has lost access: later passes or paid memberships may extend it. Admins see recipient sign-in names; non-admin issuers see public pen names, falling back to “Invited reader.” No emails or private manuscripts are exposed. Full codes cannot be recovered from hashes; create a replacement and disable the old code if its saved copy is lost.

Campaign settings allow renaming, changing capacity/deadlines, and disabling or re-enabling future redemptions. Capacity cannot be reduced below already redeemed places; edits use a row lock shared with redemption. Reopening an expired code requires clearing or extending its deadline. The pass type remains fixed and existing grants are preserved. Progress covers completed redemptions only, not message delivery, link opens, or incomplete signup journeys.

Shareable links open `/invite/` and fill the code from a URL fragment. Recipients can sign up or sign in, then explicitly redeem their invitation. A pending code is retained temporarily in their server-side session for up to one hour during authentication. See [mobile reading and invite links](MOBILE_READING.md).

Recipients create a free account or sign in, then open Membership → Redeem invite. Three calendar months start at redemption, with month-end dates clamped to the final day of the destination month. Additional distinct three-month codes extend the current invite expiry. Lifetime passes have no expiry. Each account can redeem a given code once. Code capacity and account entitlement changes use a single database transaction and row locks. Existing paid block membership is retained unchanged and can overlap an invite pass. Expired passes fall back to the account's paid/free state. Disabling a code blocks new redemptions, preserving previously granted access.

Issuing is admin-only by default. To enable selected people later, turn on **Enable selected people to issue invites**, then assign `studio.issue_invitations` (“Can issue invitations”) to their account or group in Django admin. Both the switch and explicit permission are required. These people can create either pass type and manage only their own codes; the permission does not make them admins. Turning the switch off prevents further issuing/management by non-admins without cancelling codes or redeemed passes.

# Reading Room sharing

Public feed cards, author post lists, and individual reading pages include accessible SVG icons for X, Facebook, Blogger/BlogSpot, and LinkedIn. Each opens the platform's composer with the reading's canonical URL. Blogger also receives the title and public excerpt, not the full story. Copy link and native device sharing appear where supported. The reader completes posting on the destination platform. Private manuscripts and withdrawn posts are not shared. Individual readings expose escaped canonical/Open Graph metadata.

Set `PUBLIC_BASE_URL` to the chosen HTTPS custom domain when it is attached; all generated share links follow that setting. No social API credentials are required for these composer links.

# Domain shortlist — checked September 14, 2026

Recommended brand: **The Observatory**; first domain choice: **observatory.press**.

| Domain | Name | Fit |
| --- | --- | --- |
| observatory.press | Observatory Press | Closest to the current name; clear publishing identity |
| readobservatory.com | Read Observatory | Familiar suffix and a direct invitation to readers |
| readobservatory.blog | Read Observatory | Clear home for author posts and ongoing stories |
| theobservatory.press | The Observatory | Matches the existing masthead exactly |
| readobservatory.xyz | Read Observatory | Fits the ordinal collecting side of the community |

Registry RDAP lookups returned “not found” for all five on this date. This is an availability indication, not a purchase guarantee; reserved/premium status, current price, and registration must be confirmed in Railway. Railway's public search listed observatory.xyz and observatory.blog as taken. Its browser purchase/detail flow required sign-in, so no final price is quoted and no domain was purchased.

Railway supports domain search, registration, and attachment: https://docs.railway.com/networking/domains/railway-domains. Search at https://railway.com/domains. A custom-domain change requires matching `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL`, and the Stripe webhook URL.

# Supplied Stripe catalog

`Mainstream Toolkit/.env.stripe` is ignored by Git and excluded from Docker uploads. Nonempty runtime variables take precedence over its local defaults. Aliases map product 001 to Writer and product 002 to Unlock. The supplied original images are copied byte-for-byte into `web_platform/static/products/writer.png` and `unlock.png`.

The supplied Writer price is a live **$18/month recurring** price. The current app implements a **one-time $18 / 4,320-block** membership; Unlock is a one-time $27 price. These are different billing models. Checkout remains disabled pending the owner's choice; catalog credentials alone do not enable recurring billing. The webhook is registered for completed, async-success, and expired Checkout sessions. No real charge was made.

The supplied credentials and catalog IDs are now configured in both Railway services with checkout disabled. Stripe product images point to the verified production PNGs. Webhook signature acceptance and rejection were checked without creating an order or charge.
