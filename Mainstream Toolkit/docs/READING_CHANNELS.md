# Reading channels and hashtags

Publications now have one primary channel and up to eight normalized hashtags. Channels: General, Poetry, Fiction, Mystery, Romance, Erotica, Non-Fiction, Memoir, Fantasy, Science Fiction, Horror, Historical Fiction and Essays. The publication format (short story, chapter, poetry or excerpt) remains separate from its subject channel.

The Reading Room supports channel and hashtag intersection filters in Latest, Following and Saved, preserving filters across pagination. Channel counts reflect the selected feed tab. Hashtag suggestions derive only from visible publications in that tab/channel; withdrawn-post tags are not exposed. Labels on cards and reading pages link back to discovery.

Publishers choose classification during preview. Owners can update classification through Account → Edit channel & hashtags, including during membership lockout, without changing prose, publication date or visibility. Existing unclassified posts use General; only known demo readings were assigned sample categories automatically. Hashtags are case-normalized, deduplicated and limited to 32 characters each. No hashtags are extracted from private manuscripts.

Migration 0004 adds indexed Publication.channel, unique Tag.name and a many-to-many Publication.tags join table. This release implements browsing channels, not private groups, chat rooms, group membership or channel moderation teams. Erotica is a genre label; no age-verification system is implied.

Validation covers normalization, invalid tags, category intersections, withdrawn-post privacy, following/saved filters, pagination and owner-only recategorization.
