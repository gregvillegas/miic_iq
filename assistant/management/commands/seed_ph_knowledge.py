"""
Seeds the knowledge base with Philippine compliance guides (Data Privacy Act RA 10173,
Labor Code / DOLE) and an IT product pre-sales guide, then creates curated FAQ
(canned) answers that are served instantly and cite those documents.

Idempotent: re-running updates existing documents/FAQs instead of duplicating them.
Usage: python manage.py seed_ph_knowledge [--skip-faq]
"""
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from assistant.models import CachedAnswer, Document, DocumentChunk
from assistant.services.ingestion import ingest_document
from assistant.services.query_utils import detect_topic, query_hash, token_key

SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_knowledge'

DPA = 'Data Privacy Act (RA 10173) - Employee Guide'
LABOR = 'Philippine Labor Law (DOLE) - Employee and HR Quick Guide'
ITKB = 'IT and Office Products - Pre-Sales and Support Knowledge Base'

DOCS = [
    # (file, title, category, department, version)
    ('Data_Privacy_Act_RA10173_Employee_Guide.md', DPA, 'Data Privacy', 'All', 'v1.0'),
    ('Philippine_Labor_Law_DOLE_Employee_Guide.md', LABOR, 'Labor Law', 'HR', 'v1.0'),
    ('IT_Products_Pre-Sales_and_Support_Knowledge_Base.md', ITKB, 'IT Products', 'All', 'v1.0'),
]

DISCLAIMER_LEGAL = "\n\n_This is general guidance, not legal advice. Confirm with HR or the Data Protection Officer for your specific case._"

# (question, [alternate phrasings], answer, [(doc title, page)])
FAQS = [
    ("How soon must a personal data breach be reported to the NPC?",
     ["What do I do if I lose a laptop with customer data?", "What is the data breach notification period under the Data Privacy Act?"],
     "**Report it to the Data Protection Officer (DPO) and IT Security immediately.** Do not wait to confirm the details or try to fix it quietly.\n\n"
     "- The company must notify the **NPC and affected data subjects within 72 hours** of knowledge of, or reasonable belief in, a breach involving sensitive personal information or data usable for identity fraud, where there is a real risk of serious harm.\n"
     "- Keep evidence (emails, logs, the device) and follow IT instructions.\n"
     "- All breaches must be documented, and concealing a breach is a punishable offence.\n\n"
     "Examples: lost laptop, email sent to the wrong recipient, ransomware, exposed shared folder.\n\n"
     "[Source: " + DPA + ", Page 7]" + DISCLAIMER_LEGAL,
     [(DPA, 7)]),
    ("What are the rights of a data subject under the Data Privacy Act?",
     ["What are data privacy rights under RA 10173?"],
     "Under RA 10173, individuals have the right to:\n\n"
     "- **Be informed** how their data is processed\n- **Object** to processing (including direct marketing)\n- **Access** their personal data\n- **Rectify** inaccurate data\n- **Erasure or blocking** of unlawfully obtained or unnecessary data\n"
     "- **Damages** for misuse\n- **Data portability**\n- **File a complaint** with the National Privacy Commission\n\n"
     "If a customer or colleague makes such a request, forward it to the DPO right away.\n\n[Source: " + DPA + ", Page 5]" + DISCLAIMER_LEGAL,
     [(DPA, 5)]),
    ("Can I send customer data through my personal email or messaging app?",
     ["Can I share customer information on Viber or WhatsApp?"],
     "**No.** Keep personal data inside approved company systems (CRM, ERP, HR system, approved file shares).\n\n"
     "- Do not use personal email, personal cloud storage or consumer chat apps for customer or employee data.\n"
     "- Do not copy lists to USB drives or personal devices.\n"
     "- When sharing is needed, use approved channels with access control, and password-protect or encrypt the files.\n\n"
     "[Source: " + DPA + ", Page 6]" + DISCLAIMER_LEGAL,
     [(DPA, 6)]),
    ("What are the three principles of the Data Privacy Act?",
     ["What are the general privacy principles of RA 10173?"],
     "Personal data must be processed following:\n\n"
     "1. **Transparency**: the person knows what is collected, why, how it is used and who receives it.\n"
     "2. **Legitimate purpose**: the purpose is lawful and declared in advance.\n"
     "3. **Proportionality**: only data that is necessary for the declared purpose is collected and kept.\n\n"
     "[Source: " + DPA + ", Page 3]" + DISCLAIMER_LEGAL,
     [(DPA, 3)]),
    ("What are the penalties for violating the Data Privacy Act?",
     ["What is the penalty for unauthorized processing of personal information?"],
     "Penalties include imprisonment and fines. Examples:\n\n"
     "- Unauthorised processing of personal information: **1 to 3 years** and **PHP 500,000 to 2,000,000**.\n"
     "- Unauthorised processing of sensitive personal information: **3 to 6 years** and **PHP 500,000 to 4,000,000**.\n"
     "- Concealing a security breach: **1 year 6 months to 5 years** and **PHP 500,000 to 1,000,000**.\n\n"
     "Responsible officers can be held personally liable. Verify details against the text of the Act.\n\n[Source: " + DPA + ", Page 12]" + DISCLAIMER_LEGAL,
     [(DPA, 12)]),
    ("How is the 13th month pay computed and when must it be paid?",
     ["When is the deadline for 13th month pay?", "What is the formula for 13th month pay?"],
     "**13th month pay (PD 851)**\n\n"
     "- **Who:** all rank-and-file employees who worked at least one month in the calendar year, regardless of position or employment status.\n"
     "- **Formula:** total basic salary earned during the year **divided by 12**. Allowances, overtime, premium pay and night differential are not part of basic salary.\n"
     "- **Deadline:** not later than **December 24**. Half may be given mid-year and the balance by December 24.\n"
     "- Employees who resign or are terminated mid-year get a pro-rated amount.\n\n"
     "[Source: " + LABOR + ", Page 4]" + DISCLAIMER_LEGAL,
     [(LABOR, 4)]),
    ("How is overtime pay computed in the Philippines?",
     ["What is the overtime rate for regular days, rest days and holidays?", "How much is holiday pay?"],
     "Premium rates under the Labor Code:\n\n"
     "- **Ordinary day overtime:** +25% of the hourly rate (125%).\n"
     "- **Rest day or special non-working day:** 130% for the first 8 hours; overtime adds 30% of the hourly rate on top.\n"
     "- **Regular holiday:** 200% for the first 8 hours (100% if not worked, subject to conditions); overtime adds 30% on top.\n"
     "- **Regular holiday on a rest day:** 260%.\n"
     "- **Night shift differential:** at least +10% for hours worked between 10:00 PM and 6:00 AM.\n\n"
     "Managerial employees and field personnel are generally exempt. Confirm eligibility with HR.\n\n[Source: " + LABOR + ", Page 3]" + DISCLAIMER_LEGAL,
     [(LABOR, 3)]),
    ("How many service incentive leave days are required by law?",
     ["Is unused service incentive leave convertible to cash?", "How many days of SIL am I entitled to?"],
     "Employees with at least **one year of service** are entitled to **5 days of paid service incentive leave (SIL)** per year.\n\n"
     "- Unused SIL is **convertible to cash** at year-end.\n"
     "- Exempt: establishments with fewer than 10 employees, those already giving at least 5 days paid leave, and managerial employees and field personnel.\n"
     "- Company vacation or sick leave of at least 5 paid days satisfies the requirement.\n\n[Source: " + LABOR + ", Page 5]" + DISCLAIMER_LEGAL,
     [(LABOR, 5)]),
    ("How many days is maternity leave in the Philippines?",
     ["What is the paternity leave entitlement?", "What are the statutory leaves in the Philippines?"],
     "Statutory leaves:\n\n"
     "- **Maternity (RA 11210):** 105 days paid for live childbirth; +15 days for solo parents; 60 days for miscarriage or emergency termination of pregnancy; optional 30-day extension without pay; up to 7 days may be allocated to the father or an alternate caregiver.\n"
     "- **Paternity (RA 8187):** 7 calendar days for married male employees, for the first four deliveries of the legitimate spouse.\n"
     "- **Solo parent leave (RA 8972 / RA 11861):** 7 working days a year after 6 months of service.\n"
     "- **VAWC leave (RA 9262):** up to 10 days.\n"
     "- **Special leave for women (RA 9710):** up to 2 months for gynecological surgery.\n\n[Source: " + LABOR + ", Page 6]" + DISCLAIMER_LEGAL,
     [(LABOR, 6)]),
    ("When must final pay be released after resignation?",
     ["How long does the company have to release final pay?", "How soon can I get a Certificate of Employment?"],
     "Under DOLE Labor Advisory 06-20:\n\n"
     "- **Final pay** is released within **30 days** from separation, unless a more favourable company policy applies. It includes unpaid salary, pro-rated 13th month pay, cash conversion of unused leave where applicable, and other benefits due.\n"
     "- A **Certificate of Employment** must be issued within **3 days** of the request.\n\n"
     "[Source: " + LABOR + ", Page 7]" + DISCLAIMER_LEGAL,
     [(LABOR, 7)]),
    ("What is the procedure for terminating an employee for just cause?",
     ["What is the twin notice rule?", "How much separation pay is due for redundancy?"],
     "**Just cause (twin-notice rule):**\n\n"
     "1. Written **notice to explain** stating the specific acts and the rule violated.\n"
     "2. A reasonable chance to answer (at least 5 calendar days), with a hearing or conference if requested.\n"
     "3. Written **notice of decision** with the reasons.\n\n"
     "**Authorised causes** (redundancy, retrenchment, closure, labor-saving devices, disease): written notice to the employee and DOLE **at least 30 days** before the effective date, plus separation pay (for redundancy, at least one month pay or one month per year of service, whichever is higher).\n\n"
     "Always involve HR before taking action.\n\n[Source: " + LABOR + ", Page 10]" + DISCLAIMER_LEGAL,
     [(LABOR, 10)]),
    ("How long can a probationary employee be on probation?",
     ["When does a probationary employee become regular?"],
     "Probationary employment **may not exceed 6 months** unless covered by an apprenticeship agreement. The standards for regularization must be explained to the employee at the time of engagement. An employee allowed to work after the probationary period becomes a **regular employee**.\n\n[Source: " + LABOR + ", Page 9]" + DISCLAIMER_LEGAL,
     [(LABOR, 9)]),
    ("What is the minimum retirement pay under the Labor Code?",
     ["At what age can an employee retire in the Philippines?"],
     "Under RA 7641 (absent a better plan or CBA):\n\n"
     "- Optional retirement at **60** (with at least 5 years of service); compulsory at **65**.\n"
     "- Retirement pay is at least **one-half month salary per year of service**, computed as **22.5 days** (15 days salary + 2.5 days from 13th month pay + 5 days SIL). A fraction of at least 6 months counts as a full year.\n\n"
     "[Source: " + LABOR + ", Page 11]" + DISCLAIMER_LEGAL,
     [(LABOR, 11)]),
    ("How do I size a UPS for a server or network rack?",
     ["What is the difference between line-interactive and online UPS?", "What is the difference between VA and watts on a UPS?"],
     "**Sizing steps**\n\n"
     "1. Add the **watts** of all connected equipment (nameplate or measured).\n"
     "2. Add **20 to 30% headroom**.\n"
     "3. Choose a UPS whose **watt rating** exceeds that figure, then check the runtime chart for the backup time you need.\n\n"
     "**VA vs watts:** watts = VA x power factor (about 0.6 to 0.7 on older units, 0.9 to 1.0 on newer ones). Always size by watts.\n\n"
     "**Types:** *standby* (basic, desktops), *line-interactive* (AVR, small offices and network gear), *online double-conversion* (zero transfer time, recommended for servers and storage).\n\n"
     "Install shutdown software or a network card so servers power down gracefully. Batteries usually last 3 to 5 years.\n\n[Source: " + ITKB + ", Page 6]",
     [(ITKB, 6)]),
    ("What is the difference between RAID 5, RAID 6 and RAID 10?",
     ["Which RAID level should I recommend for a server?", "Is RAID a backup?"],
     "With *n* identical drives:\n\n"
     "- **RAID 1:** capacity n/2, survives one drive failure.\n"
     "- **RAID 5:** capacity n-1, survives one failure, min 3 drives. Rebuilds on large drives are slow and risky.\n"
     "- **RAID 6:** capacity n-2, survives two failures, min 4 drives. Recommended for large HDD arrays.\n"
     "- **RAID 10:** capacity n/2, striped mirrors, min 4 drives, best mix of performance and redundancy.\n\n"
     "**RAID is not a backup.** Follow the 3-2-1 rule: 3 copies, 2 media types, 1 off-site or offline (immutable) copy. Define RPO/RTO and test restores.\n\n[Source: " + ITKB + ", Page 3]",
     [(ITKB, 3)]),
    ("What is the difference between a managed and unmanaged switch, and when do I need PoE?",
     ["How do I check the PoE budget of a switch?", "What PoE standard do I need for access points and cameras?"],
     "- **Unmanaged:** plug and play, no configuration; fine for small, simple networks.\n"
     "- **Smart / web-managed:** basic VLAN, QoS and port mirroring.\n"
     "- **Managed:** full CLI/web control, advanced VLANs, LACP, spanning tree, ACLs, SNMP, 802.1X.\n"
     "- **Layer 3:** also routes between VLANs; used at the core or distribution.\n\n"
     "**PoE** powers phones, access points and cameras over the network cable: 802.3af up to 15.4 W, 802.3at up to 30 W, 802.3bt up to 60 or 90 W per port. Always check the switch's **total PoE budget** in watts, which is lower than ports x per-port maximum.\n\n[Source: " + ITKB + ", Page 7]",
     [(ITKB, 7)]),
    ("How do I choose the right firewall size for a customer?",
     ["What is the difference between a firewall and a UTM or NGFW?", "Why is the firewall throughput lower with security features on?"],
     "- Use the **threat-protection / NGFW throughput** figure (security features enabled), not just the maximum firewall throughput; it is often much lower.\n"
     "- Consider concurrent sessions, VPN tunnels and users, internet bandwidth, and number of users and devices.\n"
     "- Check **subscription licences** (IPS, antivirus, web filtering, application control, updates). Protection and updates may stop when they expire.\n"
     "- Consider **HA** (two units) for no single point of failure and MFA for remote-access VPN.\n\n"
     "**Types:** stateful firewall, NGFW (app control, IPS, user identity), UTM (bundled AV, web filter, anti-spam, VPN).\n\n[Source: " + ITKB + ", Page 8]",
     [(ITKB, 8)]),
    ("How is Windows Server licensed?",
     ["What do I need to license Windows Server virtual machines?", "Is Windows 10 still supported?", "What are the Windows 11 requirements?"],
     "**Windows Server** is licensed **per physical core** (minimum 8 core licences per processor and 16 per server) plus **CALs** for users or devices. Standard edition covers 2 VMs; Datacenter allows unlimited VMs. Remote desktop sessions need RDS CALs.\n\n"
     "**Windows 10** reached end of support on **14 October 2025**; upgrade to Windows 11 or use Extended Security Updates where available.\n\n"
     "**Windows 11** needs a 64-bit CPU (1 GHz, 2+ cores), 4 GB RAM, 64 GB storage, UEFI Secure Boot and TPM 2.0.\n\n[Source: " + ITKB + ", Page 9]",
     [(ITKB, 9)]),
    ("What size is an A0 plotter and which roll width do I need?",
     ["How do I choose a plotter for CAD drawings?", "Dye vs pigment ink for plotters?"],
     "- **Sizes:** A2 420 x 594 mm, A1 594 x 841 mm, A0 841 x 1189 mm.\n"
     "- **Roll widths:** 24 in (610 mm), 36 in (914 mm), 44 in (1118 mm). A **36-inch** plotter prints A0.\n"
     "- **Ink:** *pigment* for water-resistant, sharp technical drawings; *dye* for vivid posters.\n"
     "- Compare print speed for A1/A0, number of inks, ink tank size, media handling, network and file format support (PDF, HP-GL/2, TIFF).\n\n[Source: " + ITKB + ", Page 5]",
     [(ITKB, 5)]),
    ("What information do I need to open a warranty or RMA case?",
     ["How do I process a warranty claim?"],
     "Collect: customer name, product model, **serial number**, purchase invoice or delivery receipt, a clear fault description, steps already tried, photos or error codes, and the site address.\n\n"
     "Flow: log the case -> basic troubleshooting -> RMA number issued -> repair or replacement per warranty terms -> record the RMA reference.\n\n"
     "Warranty usually excludes physical or liquid damage, unprotected power surges, unauthorised repair, and consumables. Ask customers to **back up data** before sending devices and follow the customer's wipe instructions (personal data).\n\n[Source: " + ITKB + ", Page 11]",
     [(ITKB, 11)]),
    ("What should I do if I receive a suspicious email or click a phishing link?",
     ["How do I report phishing?"],
     "- **Do not click links or open attachments.** Report the email to IT Security.\n"
     "- If you already clicked or entered credentials, **report immediately** to IT Security and the DPO. It may be a personal data breach with a 72-hour notification clock.\n"
     "- Change your password and enable MFA as IT directs.\n\n[Source: " + ITKB + ", Page 13]",
     [(ITKB, 13)]),
]


class Command(BaseCommand):
    help = "Ingest Philippine DPA / Labor Law / IT product guides and create curated FAQ canned answers."

    def add_arguments(self, parser):
        parser.add_argument('--skip-faq', action='store_true', help='Only ingest documents')

    def handle(self, *args, **opts):
        uploader = User.objects.filter(is_superuser=True).first()
        docs = {}
        for filename, title, category, dept, version in DOCS:
            text = (SEED_DIR / filename).read_bytes()
            doc = Document.objects.filter(title=title).first()
            created = doc is None
            if created:
                doc = Document(
                    title=title, file_type='md', category=category, department=dept,
                    version=version, access_role='all', effective_date=date.today(),
                    uploaded_by=uploader,
                )
                doc.file.save(filename, ContentFile(text), save=True)
            else:
                # refresh content in place (no duplicate files)
                with open(doc.file.path, 'wb') as fh:
                    fh.write(text)
            ok, msg = ingest_document(doc)
            docs[title] = doc
            self.stdout.write(f"{'Created' if created else 'Updated'} '{title}': {msg}")

        if opts['skip_faq']:
            return

        created_n = 0
        for question, alts, answer, source_refs in FAQS:
            sources = []
            for title, page in source_refs:
                doc = docs.get(title)
                chunk = DocumentChunk.objects.filter(document=doc, page_number=page).order_by('chunk_index').first() if doc else None
                if chunk is None and doc:
                    chunk = doc.chunks.order_by('chunk_index').first()
                sources.append({
                    'document_id': str(doc.id) if doc else None,
                    'chunk_id': chunk.chroma_id if chunk else None,
                    'title': title, 'page_number': page,
                    'category': doc.category if doc else '', 'department': doc.department if doc else '',
                    'version': doc.version if doc else 'v1.0', 'access_role': 'all', 'score': 1.0,
                    'snippet': (chunk.content[:280] + '...') if chunk else '',
                })
            for q in [question] + alts:
                _, was_created = CachedAnswer.objects.update_or_create(
                    query_hash=query_hash(q), scope='all', is_curated=True,
                    defaults=dict(
                        token_key=token_key(q), question=q, answer=answer, sources_json=sources,
                        topic=detect_topic(q), is_active=True,
                    ),
                )
                created_n += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Curated FAQ entries created: {created_n} (total {CachedAnswer.objects.filter(is_curated=True).count()})"))
