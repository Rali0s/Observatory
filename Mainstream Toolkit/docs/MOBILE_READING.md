# Mobile reading

At viewport widths below 768 CSS pixels, Observatory provides a focused reading experience:

- Four main links: Read, Authors, Invite, and Account or Sign in.
- Public readings, channel/hashtag filters, author search and profiles, follows, saved stories, likes, reporting, and social sharing.
- Password signup/sign-in, existing Xverse sign-in, public profile editing, membership status, and sign-out.
- Invite-link entry and redemption without requiring a card.

Writing, publishing, billing, storage, and ordinal management pages display a notice directing readers to the desktop app. The header also explains the mobile scope. Desktop navigation and tools remain available at 768 pixels and above; the visual writing editor initializes only at that width. This is a responsive presentation boundary, not an authorization control. Normal server permissions continue to apply to every request.

Phone layouts use one column, readable text, larger form inputs and touch targets, icon sharing controls, and a collapsible reading filter. The decorative reading banner uses a tiny placeholder source on phones instead of downloading its large desktop image.

## Invite links

After creating an invite in `/account/invites/`, admins receive a code and a copyable link in the form `/invite/#code=OBS-…`. Both appear only at creation. The fragment keeps the bearer code out of HTTP URLs and referral headers; JavaScript places it in the form and removes it from the address bar. Manual code entry works without JavaScript.

Recipients choose Create account or Sign in. The submitted code is kept in their server-side session for up to one hour while they authenticate. Signup, password sign-in, and wallet sign-in return them to the invite page. A separate Redeem invite submission grants access; opening a link or creating an account does not redeem it. Redemption retains the existing capacity, expiry, duplicate-use, rate-limit, and transactional checks. Successful redemption clears the pending code. The invite page is not cached.

The invitation record itself retains only a hash and short hint. The temporary pending code in the recipient's session is an exception needed to continue the authentication flow. Invites are sent by the administrator; the app does not send messages automatically.

## Verification

`make test` covers password and wallet invite continuation, explicit redemption, expired sessions, CSRF, rate limits, duplicate redemption, one-time link display, and mobile route presentation, alongside the existing reading and account tests. A 390-pixel browser preview verified the main phone layout. Further interactive browser checks were interrupted by the workstation locking; real iOS/Android wallet behavior was not tested.
