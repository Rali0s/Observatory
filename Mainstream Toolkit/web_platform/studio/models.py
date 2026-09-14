import uuid
from django.conf import settings
from django.db import models
from .taxonomy import CHANNELS


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
    profile = models.CharField(max_length=20, choices=[('general', 'General fiction'), ('river', 'The River Beyond Zero')])
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
