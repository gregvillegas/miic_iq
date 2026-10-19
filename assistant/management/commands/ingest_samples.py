import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File
from django.utils import timezone
from assistant.models import Document, UserProfile, QueryAuditLog, ChatSession, ChatMessage, Feedback
from assistant.services.sample_docs_generator import create_sample_docs
from assistant.services.ingestion import ingest_document


class Command(BaseCommand):
    help = 'Seeds sample company documents, users (Admin, Manager, Employee), and query analytics.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing MIICiQ sample data and document ingestion..."))

        # 1. Create or update sample users
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'first_name': 'System', 'last_name': 'Admin'})
        admin_user.set_password('admin123')
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.save()
        UserProfile.objects.update_or_create(user=admin_user, defaults={'role': 'admin', 'department': 'IT & Security'})

        mgr_user, _ = User.objects.get_or_create(username='sarah_manager', defaults={'first_name': 'Sarah', 'last_name': 'Lin'})
        mgr_user.set_password('manager123')
        mgr_user.save()
        UserProfile.objects.update_or_create(user=mgr_user, defaults={'role': 'manager', 'department': 'Sales Operations'})

        emp_user, _ = User.objects.get_or_create(username='john_employee', defaults={'first_name': 'John', 'last_name': 'Doe'})
        emp_user.set_password('employee123')
        emp_user.save()
        UserProfile.objects.update_or_create(user=emp_user, defaults={'role': 'employee', 'department': 'Engineering'})

        self.stdout.write(self.style.SUCCESS("✓ Users initialized: admin, sarah_manager, john_employee"))

        # 2. Generate sample documents
        created_paths = create_sample_docs()
        self.stdout.write(self.style.NOTICE(f"Generated {len(created_paths)} realistic sample document files."))

        # 3. Document configurations
        doc_configs = [
            {
                'file_name': 'SO_Process_Workflow_SOP_v2.docx',
                'title': 'Sales Order (SO) Fulfillment Workflow SOP',
                'category': 'Sales Order Workflow',
                'department': 'Sales',
                'version': 'v2.3',
                'access_role': 'all',
            },
            {
                'file_name': 'HR_Leave_and_Remote_Work_Policy_v3.pdf',
                'title': 'Global HR Policy: Leave & Flexible Working 2026',
                'category': 'HR',
                'department': 'HR',
                'version': 'v3.2',
                'access_role': 'all',
            },
            {
                'file_name': 'Travel_and_Expense_Reimbursement_Policy_v2.pdf',
                'title': 'Corporate Travel & Expense Reimbursement Guidelines',
                'category': 'Finance',
                'department': 'Finance',
                'version': 'v2.0',
                'access_role': 'all',
            },
            {
                'file_name': 'IT_Security_and_Acceptable_Use_Policy.md',
                'title': 'Corporate IT Security & Acceptable Use Policy',
                'category': 'IT',
                'department': 'IT',
                'version': 'v3.1',
                'access_role': 'all',
            },
            {
                'file_name': 'Sales_Discount_Matrix_and_Payment_Terms.xlsx',
                'title': 'Sales Discount Approval Matrix & Terms',
                'category': 'Sales Order Workflow',
                'department': 'Sales',
                'version': 'v1.4',
                'access_role': 'manager_plus',
            },
        ]

        base_sample_dir = Path(__file__).resolve().parent.parent.parent.parent / 'sample_documents'

        for cfg in doc_configs:
            f_path = base_sample_dir / cfg['file_name']
            if not f_path.exists():
                continue

            doc, created = Document.objects.get_or_create(
                title=cfg['title'],
                defaults={
                    'category': cfg['category'],
                    'department': cfg['department'],
                    'version': cfg['version'],
                    'access_role': cfg['access_role'],
                    'file_type': cfg['file_name'].split('.')[-1].lower(),
                    'effective_date': timezone.now().date(),
                    'uploaded_by': admin_user
                }
            )

            with open(f_path, 'rb') as f_stream:
                doc.file.save(cfg['file_name'], File(f_stream), save=True)

            success, msg = ingest_document(doc)
            self.stdout.write(self.style.SUCCESS(f"✓ Ingested: {doc.title} ({doc.chunk_count} chunks) - {msg}"))

        # 4. Seed initial realistic audit logs for analytics dashboard
        sample_queries = [
            ("How do I process a Sales Order in ERP?", "chat", 3, 45, 1),
            ("What is our annual leave rollover limit?", "chat", 2, 38, 1),
            ("What are the daily lunch and dinner per diem rates for business travel?", "chat", 2, 42, 1),
            ("What is the discount approval threshold for a 20% discount?", "chat", 1, 51, 1),
            ("How do I report a phishing email to IT?", "chat", 2, 35, 1),
            ("Who approves orders exceeding $100,000?", "chat", 2, 40, 1),
            ("Can I expense solo traveler alcoholic beverages?", "chat", 1, 39, 1),
            ("What is the company stock purchase plan discount?", "chat", 0, 30, None, True),
        ]

        for q in sample_queries:
            q_text = q[0]
            mode = q[1]
            sources_count = q[2]
            latency = q[3]
            fb = q[4]
            is_low = q[5] if len(q) > 5 else False

            QueryAuditLog.objects.create(
                user=john_employee if (john_employee := User.objects.filter(username='john_employee').first()) else admin_user,
                user_role='employee',
                query_text=q_text,
                mode=mode,
                retrieved_sources_count=sources_count,
                response_latency_ms=latency,
                feedback_rating=fb,
                is_unanswered_or_low_confidence=is_low,
                ip_address='127.0.0.1'
            )

        self.stdout.write(self.style.SUCCESS("✓ Seeded realistic query analytics and audit log entries."))
        self.stdout.write(self.style.SUCCESS("MIICiQ sample ingestion completed successfully!"))
