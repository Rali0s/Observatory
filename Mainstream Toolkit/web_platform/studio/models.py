import uuid
from django.conf import settings
from django.db import models
from .taxonomy import CHANNELS


class InviteSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    member_issuers_enabled = models.BooleanField(default=False,
        help_text='Allow people with the Can issue invitations permission to create codes. Admins always can.')

    class Meta:
        verbose_name_plural = 'Invite settings'
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='invite_settings_singleton')]


class Invitation(models.Model):
    class Kind(models.TextChoices):
        THREE_MONTHS = 'three_months', 'Free three months'
        LIFETIME = 'lifetime', 'Lifetime access'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_hash = models.CharField(max_length=64, unique=True, editable=False)
    code_hint = models.CharField(max_length=12, editable=False)
    label = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0, editable=False)
    enabled = models.BooleanField(default=True)
    redeem_before = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [('issue_invitations', 'Can issue invitations')]
        constraints = [
            models.CheckConstraint(condition=models.Q(max_uses__gte=1), name='invite_positive_uses'),
            models.CheckConstraint(condition=models.Q(uses__lte=models.F('max_uses')), name='invite_capacity'),
        ]


class ComplimentaryAccess(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lifetime = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)


class InviteRedemption(models.Model):
    invitation = models.ForeignKey(Invitation, on_delete=models.PROTECT, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    redeemed_at = models.DateTimeField(auto_now_add=True)
    granted_until = models.DateTimeField(null=True, blank=True)
    lifetime = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['invitation', 'user'], name='invite_once_per_user')]


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='novel_projects')
    title = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Revision(models.Model):
    """Append-only through the application; text and analysis travel together."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='revisions')
    label = models.CharField(max_length=160)
    manuscript = models.TextField()
    fingerprint = models.CharField(max_length=64)
    profile = models.CharField(max_length=20, choices=[('general', 'General fiction'), ('river', 'The River Beyond Zero'), ('creepypasta', 'Creepypasta · darkness')])
    word_count = models.PositiveIntegerField()
    engine_version = models.CharField(max_length=40)
    analysis = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['project', 'created_at'], name='revision_project_date')]


class RevisionNote(models.Model):
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name='notes')
    text = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class AccessGrant(models.Model):
    """Provider-neutral access. No payment or subscription status is implied."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='observatory_access')
    enabled = models.BooleanField(default=True)
    plan_code = models.CharField(max_length=40, default='pilot')
    max_projects = models.PositiveIntegerField(default=3)
    max_words_per_revision = models.PositiveIntegerField(default=20000)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AuthorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author_profile')
    pen_name = models.CharField(max_length=80)
    bio = models.TextField(max_length=1000, blank=True)


class WalletIdentity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_identities')
    address = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WalletChallenge(models.Model):
    merge_attempt = models.ForeignKey("MergeAttempt", on_delete=models.CASCADE, null=True, related_name="wallet_challenges")
    merge_slot = models.CharField(max_length=5, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address = models.CharField(max_length=100)
    message = models.TextField()
    session_hash = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class PublishingMembership(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='publishing_membership')
    expires_at_block = models.PositiveBigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)


class ChainTip(models.Model):
    # One server-managed Bitcoin mainnet observation. No browser can update it.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    height = models.PositiveBigIntegerField()
    block_hash = models.CharField(max_length=64)
    observed_at = models.DateTimeField()


class Tag(models.Model):
    name = models.CharField(max_length=32, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return '#'+self.name


class Publication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(AuthorProfile, on_delete=models.PROTECT, related_name='publications')
    source_revision = models.ForeignKey(Revision, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=160)
    excerpt = models.CharField(max_length=300)
    body = models.TextField(max_length=120000)
    kind = models.CharField(max_length=20, choices=[('story', 'Short story'), ('chapter', 'Chapter'), ('poetry', 'Poetry'), ('excerpt', 'Excerpt')])
    published_at = models.DateTimeField(auto_now_add=True)
    is_visible = models.BooleanField(default=True)
    channel = models.CharField(max_length=30, choices=CHANNELS, default='general', db_index=True)
    tags = models.ManyToManyField(Tag, related_name='publications', blank=True)

    class Meta:
        ordering = ['-published_at', '-id']


class Upvote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='upvotes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','publication'], name='unique_publication_upvote')]


class Follow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    author = models.ForeignKey(AuthorProfile, on_delete=models.CASCADE, related_name='followers')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'author'], name='unique_author_follow')]


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='bookmarks')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'publication'], name='unique_publication_bookmark')]


class PublicationReport(models.Model):
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    reason = models.TextField(max_length=1000)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['reporter', 'publication'], name='unique_publication_report')]


class PaymentOrder(models.Model):
    billing_user_id = models.PositiveBigIntegerField(null=True, editable=False)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    redemption = models.BooleanField(default=False)
    provider_invoice_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=20, default='creating')
    applied_at_block = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=12, default='btcpay')
    address = models.CharField(max_length=100, blank=True)
    amount_sats = models.PositiveBigIntegerField(null=True, blank=True)
    quote_expires = models.DateTimeField(null=True, blank=True)
    txid = models.CharField(max_length=64, blank=True)
    first_seen = models.DateTimeField(null=True, blank=True)


class ReceivingAddress(models.Model):
    address = models.CharField(max_length=100, unique=True)
    order = models.OneToOneField(PaymentOrder, on_delete=models.PROTECT, null=True, blank=True)


class StoryWorkspace(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='story_workspace')
    board = models.JSONField(default=dict)
    roster = models.JSONField(default=dict)
    clues = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)


class StoryEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='story_entries')
    kind = models.CharField(max_length=20, choices=[('character','Character'),('location','Location'),('rule','World rule'),('continuity','Continuity fact'),('task','Revision task')])
    title = models.CharField(max_length=160)
    text = models.TextField(max_length=12000, blank=True)
    reference = models.CharField(max_length=240, blank=True)
    done = models.BooleanField(default=False)


class DraftChapter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='draft_chapters')
    title = models.CharField(max_length=160)
    section = models.CharField(max_length=120, blank=True)
    position = models.PositiveIntegerField(default=1)
    markdown = models.TextField(max_length=500000, blank=True)
    version = models.PositiveIntegerField(default=0)
    art = models.BinaryField(blank=True, default=bytes)
    art_type = models.CharField(max_length=30, blank=True)
    art_alt = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['position', 'id']


class ClueAnnotation(models.Model):
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name='clue_annotations')
    clue = models.CharField(max_length=120)
    passage_id = models.CharField(max_length=16)
    status = models.CharField(max_length=30)
    note = models.TextField(max_length=4000, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision','clue','passage_id'], name='unique_revision_clue_passage')]


class SemanticReading(models.Model):
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name='semantic_readings')
    passage_id = models.CharField(max_length=16)
    result = models.JSONField(default=dict)
    model = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision','passage_id'], name='unique_semantic_passage')]


class OrdinalSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False, help_text='Allow new ordinal editions and wallet mint requests. Existing inscriptions remain readable.')
    special_sats_enabled = models.BooleanField(default=False, help_text='Allow export to Gamma for special-sat inscriptions.')

    def __str__(self):
        return 'Ordinal minting controls'


class OrdinalEdition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.OneToOneField(Publication, on_delete=models.PROTECT, related_name='ordinal')
    metadata = models.JSONField(default=dict)
    content = models.TextField()
    content_hash = models.CharField(max_length=64)
    sat_mode = models.CharField(max_length=12, choices=[('regular','Regular sat'),('special','Special sat')])
    requested_sat = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, default='prepared', choices=[('prepared','Ready'),('awaiting','Awaiting inscription'),('submitted','Verifying'),('minted','Minted')])
    inscription_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    txid = models.CharField(max_length=64, blank=True)
    sat_number = models.PositiveBigIntegerField(null=True, blank=True)
    sat_rarity = models.CharField(max_length=20, blank=True)
    marketplace_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    minted_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)

class Achievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements')
    code = models.CharField(max_length=32)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','code'], name='unique_user_achievement')]

class ProfileUnlock(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_unlock')
    badge = models.CharField(max_length=32, blank=True)
    show_scene = models.BooleanField(default=False)
    scene = models.PositiveSmallIntegerField(default=0)


class OrdinalListing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    edition = models.ForeignKey(OrdinalEdition, on_delete=models.PROTECT, related_name='listings')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    seller_address = models.CharField(max_length=100)
    payout_address = models.CharField(max_length=100)
    price_sats = models.PositiveBigIntegerField()
    outpoint = models.CharField(max_length=80)
    postage_sats = models.PositiveBigIntegerField()
    unsigned_psbt = models.TextField()
    signed_psbt = models.TextField(blank=True)
    status = models.CharField(max_length=12, default='draft', choices=[('draft', 'Awaiting signature'), ('active', 'For sale'), ('cancelled', 'Delisted'), ('sold', 'Sold'), ('stale', 'Ownership changed')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['edition'], condition=models.Q(status__in=['draft', 'active']), name='one_open_ordinal_listing')]


class OrdinalTrade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(OrdinalListing, on_delete=models.PROTECT, related_name='trades')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    receive_address = models.CharField(max_length=100)
    payment_address = models.CharField(max_length=100)
    unsigned_psbt = models.TextField()
    raw_transaction = models.TextField(blank=True)
    txid = models.CharField(max_length=64, blank=True)
    fee_sats = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, default='prepared', choices=[('prepared', 'Review in wallet'), ('broadcasting', 'Broadcast pending'), ('broadcast', 'Awaiting confirmations'), ('confirmed', 'Collected'), ('conflict', 'Inputs spent elsewhere')])
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True)


class OrdinalHolding(models.Model):
    edition = models.OneToOneField(OrdinalEdition, on_delete=models.CASCADE, related_name='holding')
    address = models.CharField(max_length=100, db_index=True)
    outpoint = models.CharField(max_length=80)
    checked_at = models.DateTimeField()


class AccountMerge(models.Model):
    source = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='merged_account')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='merged_aliases')
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class MergeAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    other = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, related_name='+')
    session_hash = models.CharField(max_length=64)
    owner_auth_hash = models.CharField(max_length=64, blank=True)
    other_auth_hash = models.CharField(max_length=64, blank=True)
    owner_wallet = models.CharField(max_length=100, blank=True)
    other_wallet = models.CharField(max_length=100, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
