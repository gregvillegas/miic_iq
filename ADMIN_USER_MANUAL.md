# MIICiQ — Knowledge Administrator & Ops Manual

**Target Audience:** HR Administrators, Sales Operations Leads, IT Security Officers, Knowledge Base Managers  
**URL:** `http://<your-server>/admin-dashboard/`  

---

## 1. Accessing the Admin Dashboard

1. Navigate to the top-level URL and click **"⚙️ Knowledge Admin & Analytics"** in the sidebar.
2. If accessing via a role-restricted session, use the **"Switch Role"** button in the lower-left profile badge to activate the **Administrator** or **Manager** profile.
3. Access is restricted according to Role-Based Access Control (RBAC).

---

## 2. Ingesting New Company Documents

### Supported File Formats
| Format | Extension | Capabilities |
| :--- | :--- | :--- |
| **PDF** | `.pdf` | Extracts text with accurate page-level numbering for citations. |
| **Word** | `.docx`, `.doc` | Extracts headings, paragraphs, and embedded tables. |
| **Markdown / Text** | `.md`, `.txt` | Parses sections, bulleted lists, and structured headers. |
| **Excel** | `.xlsx`, `.xls` | Ingests multi-sheet tables (matrices, pricing tiers, approval rules). |
| **CSV** | `.csv` | Paginated tabular record ingestion. |

### Upload Steps:
1. Under **"📚 Document Library & Upload"**, click **Choose File**.
2. **Title:** Give the document a descriptive name (e.g., *Sales Order (SO) Fulfillment Workflow SOP*).
3. **Category:** Select from:
   - `Company Policy`
   - `Sales Order Workflow`
   - `Human Resources`
   - `Information Technology & Security`
   - `Finance & Expenses`
   - `Other Documentation`
4. **Department:** Specify owning business unit (e.g., `Sales`, `HR`, `IT`, `Finance`, or `All`).
5. **Version:** Enter version code (e.g., `v2.4`).
6. **Access Role:**
   - `All Employees`: Accessible by every staff member.
   - `Managers & Admins`: Restricted to leadership roles (e.g., discount matrices, executive compensation).
   - `Admin Only`: Restricted to system administrators.
7. Click **"Upload & Ingest Document"**. The pipeline splits text into 500–1000 token chunks and indexes them into ChromaDB within 5 seconds.

---

## 3. Managing Existing Documents

- **Re-index:** Click **"Re-index"** next to any document to re-parse and refresh its vector chunks.
- **Delete:** Click **"Delete"** to permanently remove the document file and automatically purge all associated vector embeddings from ChromaDB.
- **Rebuild Vector Index:** Click the **"🔄 Rebuild Vector Index"** button to perform a complete re-index of the entire knowledge base.

---

## 4. Query Analytics & Content Gap Analysis

Navigate to **"📊 Query Analytics & Missing Docs"**:
1. **Most Frequent Inquiries:** Highlights what employees ask about most frequently, identifying topics that benefit from streamlined policies.
2. **Low-Confidence / Unanswered Queries:** Tracks questions where the vector similarity score fell below confidence thresholds.
   - *Example:* If multiple employees ask *"What is the parental leave duration?"* and it appears here, upload the updated Parental Leave SOP to immediately resolve the knowledge gap.

---

## 5. Security & Query Audit Log

Navigate to **"🔍 Security & Query Audit Log"**:
- Records every employee interaction:
  - Timestamp
  - Username & Role
  - Mode (Chat vs. Search)
  - Full Question Text
  - Number of Sources Cited
  - Retrieval & Generation Latency (in ms)
  - User Feedback (👍 Helpful / 👎 Issue)
  - Employee Client IP Address
- Ensures full regulatory compliance and auditability.
