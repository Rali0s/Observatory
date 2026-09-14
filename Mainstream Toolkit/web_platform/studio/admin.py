from django.contrib import admin
from .models import AccessGrant, Publication, PublicationReport, AuthorProfile, PublishingMembership, PaymentOrder, ChainTip


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan_code', 'enabled', 'max_projects', 'max_words_per_revision', 'expires_at']
    list_filter = ['enabled', 'plan_code']
    search_fields = ['user__username']
# Manuscripts deliberately stay out of the general administrative interface.

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'published_at', 'is_visible']
    list_filter = ['is_visible', 'kind', 'channel']
    search_fields = ['title', 'author__pen_name']
    readonly_fields = ['author', 'source_revision', 'title', 'excerpt', 'body', 'kind', 'published_at']
    def has_add_permission(self, request):
        return False


@admin.register(PublicationReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['publication', 'reporter', 'created_at', 'resolved']
    list_filter = ['resolved']
    readonly_fields = ['publication', 'reporter', 'reason', 'created_at']


@admin.register(PublishingMembership, PaymentOrder, ChainTip)
class ReadOnlyBillingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

from .models import OrdinalSettings, OrdinalEdition

@admin.register(OrdinalSettings)
class OrdinalSettingsAdmin(admin.ModelAdmin):
    list_display = ['enabled', 'special_sats_enabled']
    def has_add_permission(self, request):
        return not OrdinalSettings.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(OrdinalEdition)
class OrdinalEditionAdmin(admin.ModelAdmin):
    list_display = ['publication', 'status', 'sat_mode', 'inscription_id', 'minted_at']
    list_filter = ['status', 'sat_mode']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
