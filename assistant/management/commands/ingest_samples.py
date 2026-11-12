import secrets
from pathlib import Path
from django.conf import settings
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File
from django.utils import timezone
from assistant.models import Document, UserProfile
from assistant.services.sample_docs_generator import create_sample_docs
from assistant.services.ingestion import ingest_document


class Command(BaseCommand):
    help = 'Seeds sample company documents and demo users (Admin, Manager, Employee). Does not fabricate analytics.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing MIICiQ sample data and document ingestion..."))

        # 1. Create demo users. Passwords are only set on creation, never reset on re-runs.
        #    Set DEMO_ADMIN_PASSWORD / DEMO_MANAGER_PASSWORD / DEMO_EMPLOYEE_PASSWORD, otherwise
        #    simple demo passwords are used only when DEBUG is on and random ones are generated otherwise.
        def make_user(username, env_name, dev_pw, first, last, role, dept, superuser=False):
            user, created = User.objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last})
            if created:
                pw = os.getenv(env_name) or (dev_pw if settings.DEBUG else secrets.token_urlsafe(12))
                user.set_password(pw)
                user.is_superuser = superuser
                user.is_staff = superuser
                user.save()
                shown = pw if (settings.DEBUG or not os.getenv(env_name)) else '(from ' + env_name + ')'
                self.stdout.write(self.style.WARNING(f"  created {username} / password: {shown}"))
            UserProfile.objects.get_or_create(user=user, defaults={'role': role, 'department': dept})
            return user

        admin_user = make_user('admin', 'DEMO_ADMIN_PASSWORD', 'admin123', 'System', 'Admin', 'admin', 'IT & Security', True)
        make_user('sarah_manager', 'DEMO_MANAGER_PASSWORD', 'manager123', 'Sarah', 'Lin', 'manager', 'Sales Operations')
        make_user('john_employee', 'DEMO_EMPLOYEE_PASSWORD', 'employee123', 'John', 'Doe', 'employee', 'Engineering')
        self.stdout.write(self.style.SUCCESS("✓ Users ready: admin, sarah_manager, john_employee"))

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

            if not created and doc.status == 'indexed':
                self.stdout.write(f"- Skipped (already indexed): {doc.title}")
                continue

            if created or not doc.file:
                with open(f_path, 'rb') as f_stream:
                    doc.file.save(cfg['file_name'], File(f_stream), save=True)

            success, msg = ingest_document(doc)
            self.stdout.write(self.style.SUCCESS(f"✓ Ingested: {doc.title} ({doc.chunk_count} chunks) - {msg}"))

        self.stdout.write(self.style.SUCCESS("MIICiQ sample ingestion completed successfully!"))
