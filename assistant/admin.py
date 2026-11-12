from django.contrib import admin
from assistant.models import CachedAnswer


@admin.register(CachedAnswer)
class CachedAnswerAdmin(admin.ModelAdmin):
    """Manage canned answers: curate FAQs, retire bad cached answers, see what is asked most."""
    list_display = ('question', 'topic', 'scope', 'is_curated', 'is_active', 'hit_count', 'upvotes', 'downvotes', 'last_hit_at')
    list_filter = ('is_curated', 'is_active', 'scope', 'topic')
    search_fields = ('question', 'answer')
    actions = ['mark_curated', 'deactivate']

    @admin.action(description='Promote to curated FAQ (survives re-indexing)')
    def mark_curated(self, request, queryset):
        queryset.update(is_curated=True, is_active=True)

    @admin.action(description='Deactivate selected answers')
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)
