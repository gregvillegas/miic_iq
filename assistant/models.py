import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('admin', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = models.CharField(max_length=100, default='General')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()} - {self.department})"


class Document(models.Model):
    CATEGORY_CHOICES = [
        ('Policy', 'Company Policy'),
        ('Sales Order Workflow', 'Sales Order Workflow'),
        ('HR', 'Human Resources'),
        ('IT', 'Information Technology & Security'),
        ('Finance', 'Finance & Expenses'),
        ('Other', 'Other Documentation'),
    ]

    ACCESS_ROLE_CHOICES = [
        ('all', 'All Employees'),
        ('manager_plus', 'Managers & Admins'),
        ('admin_only', 'Admin Only'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Indexing'),
        ('processing', 'Processing & Chunking'),
        ('indexed', 'Indexed & Ready'),
        ('failed', 'Indexing Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=20)  # pdf, docx, txt, md, xlsx, csv
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Policy')
    department = models.CharField(max_length=100, default='All')
    version = models.CharField(max_length=50, default='v1.0')
    effective_date = models.DateField(default=timezone.now)
    access_role = models.CharField(max_length=20, choices=ACCESS_ROLE_CHOICES, default='all')
    
    file_size = models.BigIntegerField(default=0)  # in bytes
    chunk_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, default='')

    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.version}) - {self.category}"


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    token_count = models.IntegerField(default=0)
    page_number = models.IntegerField(default=1)
    metadata_json = models.JSONField(default=dict, blank=True)
    chroma_id = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['chroma_id']),
            models.Index(fields=['document', 'page_number']),
        ]

    def __str__(self):
        return f"{self.document.title} - Chunk {self.chunk_index} (p.{self.page_number})"


class ChatSession(models.Model):
    MODE_CHOICES = [
        ('chat', 'Chat Mode (RAG Assistant)'),
        ('search', 'Search Mode (Ranked Snippets)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=255, default='New Inquiry')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('user', 'User'),
        ('assistant', 'MIICiQ Assistant'),
        ('system', 'System'),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    sources_json = models.JSONField(default=list, blank=True)  # list of citations
    latency_ms = models.IntegerField(null=True, blank=True)
    is_low_confidence = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.session_id}] {self.sender}: {self.content[:40]}"


class Feedback(models.Model):
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE, related_name='feedback')
    rating = models.SmallIntegerField()  # +1 (Thumbs Up), -1 (Thumbs Down)
    comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback {'👍' if self.rating > 0 else '👎'} for Msg {self.message_id}"


class QueryAuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_role = models.CharField(max_length=50, default='employee')
    query_text = models.TextField()
    mode = models.CharField(max_length=20, default='chat')
    retrieved_sources_count = models.IntegerField(default=0)
    top_sources_json = models.JSONField(default=list, blank=True)
    response_latency_ms = models.IntegerField(default=0)
    is_unanswered_or_low_confidence = models.BooleanField(default=False)
    feedback_rating = models.SmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.user}: {self.query_text[:50]}"


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_val(cls, key, default=''):
        obj = cls.objects.filter(key=key).first()
        return obj.value if obj else default
