from django.urls import path
from assistant import views

app_name = 'assistant'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # UI Pages
    path('', views.chat_view, name='chat'),
    path('chat/', views.chat_view, name='chat_alias'),
    path('search/', views.search_view, name='search'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('crm-demo/', views.crm_demo_view, name='crm_demo'),

    # Chat & Search APIs
    path('api/chat/stream/', views.stream_chat_api, name='api_chat_stream'),
    path('api/chat/session/<uuid:session_id>/', views.get_session_messages_api, name='api_session_messages'),
    path('api/chat/new/', views.create_new_session_api, name='api_new_session'),
    path('api/chat/session/<uuid:session_id>/delete/', views.delete_session_api, name='api_delete_session'),
    path('api/feedback/', views.feedback_api, name='api_feedback'),
    path('api/chunk/<str:chunk_id>/', views.get_chunk_preview_api, name='api_chunk_preview'),
    path('api/source/resolve/', views.resolve_source_api, name='api_resolve_source'),
    path('api/document/<uuid:doc_id>/view/', views.view_document_api, name='api_view_document'),

    # Admin Management APIs
    path('api/admin/upload/', views.upload_document_api, name='api_upload_document'),
    path('api/admin/reindex/<uuid:doc_id>/', views.reindex_document_api, name='api_reindex_document'),
    path('api/admin/rebuild-index/', views.rebuild_index_api, name='api_rebuild_index'),
    path('api/admin/delete/<uuid:doc_id>/', views.delete_document_api, name='api_delete_document'),

    # System
    path('api/system/health/', views.system_health_api, name='api_system_health'),
]
