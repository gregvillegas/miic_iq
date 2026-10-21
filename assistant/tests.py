import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from assistant.models import Document, DocumentChunk, ChatSession, ChatMessage, Feedback, QueryAuditLog, UserProfile
from assistant.services.document_processor import DocumentParser, RecursiveChunker
from assistant.services.vector_store import VectorStoreService
from assistant.services.ingestion import ingest_document


class DocumentProcessingTests(TestCase):
    def test_recursive_chunker(self):
        chunker = RecursiveChunker(target_chars=200, overlap_chars=40)
        pages = [
            {'page_number': 1, 'text': 'Short text.', 'metadata': {}},
            {'page_number': 2, 'text': 'Paragraph 1 of page 2.\n\nParagraph 2 of page 2 with additional information.', 'metadata': {}}
        ]
        doc_meta = {'title': 'Test Doc'}
        chunks = chunker.chunk_document_pages(pages, doc_meta)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0]['page_number'], 1)
        self.assertEqual(chunks[1]['page_number'], 2)


class VectorStoreAndRAGTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_admin', is_superuser=True)
        UserProfile.objects.create(user=self.user, role='admin', department='IT')

        # Create dummy text document
        dummy_content = (
            "Standard Operating Procedure: Sales Order Invoicing.\n\n"
            "Step 1: All Sales Orders must be created in ERP under code SO-101.\n"
            "Step 2: Orders exceeding $25,000 require Sales Director signoff.\n"
            "Step 3: Finance releases invoice upon Proof of Delivery."
        ).encode('utf-8')
        uploaded = SimpleUploadedFile("sop_test.txt", dummy_content, content_type="text/plain")

        self.doc = Document.objects.create(
            title="SOP Test Invoicing",
            file=uploaded,
            file_type="txt",
            category="Sales Order Workflow",
            department="Sales",
            version="v1.0",
            access_role="all"
        )
        ingest_document(self.doc)

    def test_hybrid_search(self):
        vs = VectorStoreService()
        results = vs.hybrid_search("SO-101 invoicing procedure", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['title'], "SOP Test Invoicing")
        self.assertIn("SO-101", results[0]['content'])

    def test_rbac_filtering(self):
        # Create restricted document
        dummy_secret = "Confidential Manager Bonus Allocation Matrix.".encode('utf-8')
        uploaded_secret = SimpleUploadedFile("secret.txt", dummy_secret, content_type="text/plain")
        secret_doc = Document.objects.create(
            title="Executive Bonus Matrix",
            file=uploaded_secret,
            file_type="txt",
            category="Finance",
            department="Finance",
            version="v1.0",
            access_role="admin_only"
        )
        ingest_document(secret_doc)

        vs = VectorStoreService()
        # Employee should NOT see admin_only docs
        emp_results = vs.hybrid_search("Bonus Allocation Matrix", top_k=5, allowed_roles=['employee'])
        found_titles = [r['title'] for r in emp_results]
        self.assertNotIn("Executive Bonus Matrix", found_titles)

        # Admin SHOULD see admin_only docs
        admin_results = vs.hybrid_search("Bonus Allocation Matrix", top_k=5, allowed_roles=['admin'])
        admin_titles = [r['title'] for r in admin_results]
        self.assertIn("Executive Bonus Matrix", admin_titles)


class ChatViewsAndAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='eval_user', password='testpass123')
        UserProfile.objects.create(user=self.user, role='employee', department='General')
        self.client.force_login(self.user)
        uploaded = SimpleUploadedFile(
            "compatibility_reference.md",
            b"# Laptop Compatibility\nSupports 32GB DDR5 and 2TB NVMe SSD.\n",
            content_type="text/markdown"
        )
        self.doc = Document.objects.create(
            title="Laptop Compatibility Reference",
            file=uploaded,
            file_type="md",
            category="Product Specs & Compatibility",
            department="Engineering",
            version="v1.0",
            access_role="all"
        )
        self.chunk = DocumentChunk.objects.create(
            document=self.doc,
            chunk_index=0,
            content="Supports 32GB DDR5 memory and 2TB NVMe SSD.",
            token_count=9,
            page_number=1,
            metadata_json={"document_id": str(self.doc.id)},
            chroma_id=f"{self.doc.id}_0"
        )

    def test_chat_page_render(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MIICiQ")
        self.assertContains(response, "Chat Mode")
        self.assertContains(response, "Search Mode")
        self.assertContains(response, "Laptop Memory / SSD Compatibility")

    def test_search_page_render(self):
        response = self.client.get('/search/?q=Sales')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semantic & Keyword Search")
        self.assertContains(response, "Product Specs &amp; Compatibility")
        self.assertContains(response, "Engineering")

    def test_admin_dashboard_render(self):
        self.user.profile.role = 'employee'
        self.user.profile.department = 'Engineering'
        self.user.profile.save()
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Knowledge Administration & Query Analytics")
        self.assertContains(response, "Product Specs &amp; Compatibility")
        self.assertContains(response, "Engineering")

    def test_engineering_user_can_access_upload_endpoint(self):
        self.user.profile.role = 'employee'
        self.user.profile.department = 'Engineering'
        self.user.profile.save()
        response = self.client.post('/api/admin/upload/')
        self.assertEqual(response.status_code, 400)

    def test_new_session_api(self):
        response = self.client.get('/api/chat/new/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('session_id', data)

    def test_stream_chat_api(self):
        response = self.client.post(
            '/api/chat/stream/',
            data=json.dumps({'message': 'How do I process a Sales Order?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

    def test_login_required_redirect_for_anonymous_user(self):
        self.client.logout()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_document_category_choices_include_product_specs(self):
        category_values = [value for value, _ in Document.CATEGORY_CHOICES]
        department_values = [value for value, _ in Document.DEPARTMENT_CHOICES]
        self.assertIn('Product Specs & Compatibility', category_values)
        self.assertIn('Engineering', department_values)

    def test_user_can_view_allowed_source_document(self):
        response = self.client.get(f'/api/document/{self.doc.id}/view/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('inline;', response['Content-Disposition'])

    def test_chunk_preview_includes_document_id(self):
        response = self.client.get(f'/api/chunk/{self.chunk.chroma_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['document_id'], str(self.doc.id))

    def test_user_cannot_view_restricted_source_document(self):
        restricted = Document.objects.create(
            title="Restricted Compatibility Notes",
            file=SimpleUploadedFile("restricted.md", b"restricted", content_type="text/markdown"),
            file_type="md",
            category="Product Specs & Compatibility",
            department="Engineering",
            version="v1.0",
            access_role="manager_plus"
        )
        response = self.client.get(f'/api/document/{restricted.id}/view/')
        self.assertEqual(response.status_code, 403)
