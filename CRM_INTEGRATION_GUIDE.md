# MIICiQ — Django CRM Chatbot Integration Guide

This guide explains how to embed the **MIICiQ Chatbot Widget** into your **Django CRM application** so sales representatives, account managers, and staff can access instant company policy guidance, Sales Order (SO-101) procedures, and approval thresholds directly from your CRM.

---

## 🎯 How It Works

1. A floating, non-intrusive **"🤖 Ask MIICiQ"** launcher appears in the corner of your Django CRM application.
2. Clicking it opens a sleek, enterprise popup window featuring:
   - Quick CRM inquiry buttons (e.g. *Sales Order SO-101 Workflow*, *Discount Approval Matrix*, *Payment Terms & Credit Checks*, *Travel & Expense Limits*).
   - A free-text inquiry input box.
3. When an employee asks a question or clicks an inquiry, the widget **redirects them to the MIIC_iQ application URL address** with the question prefilled and an answer streamed instantly from verified company SOPs!
4. Alternatively, it can open in a **Slideout Drawer** or **New Tab** without leaving the active CRM page.

---

## 🚀 Method 1: The 1-Line Drop-In Script (Recommended)

Add this single `<script>` tag right before the closing `</body>` tag of your Django CRM application's base layout (e.g., `templates/base.html` or `crm/templates/crm_base.html`):

```html
<!-- MIICiQ Floating Chatbot for Django CRM -->
<script 
  src="http://127.0.0.1:8000/static/assistant/js/miiciq-widget.js" 
  data-miiciq-url="http://127.0.0.1:8000" 
  data-mode="redirect" 
  data-button-text="Ask MIICiQ" 
  defer>
</script>
```

> **Note:** In production, replace `http://127.0.0.1:8000` with your internal MIIC_iQ domain (e.g., `https://miiciq.company.local` or `http://192.168.1.50:8000`).

---

## 🧩 Method 2: Using the Reusable Django Template Include

If both apps share a project or if you copied the widget template into your CRM project:

### Step 1: Copy `miiciq_widget.html`
Copy `assistant/templates/crm_widget/miiciq_widget.html` into your CRM's `templates/includes/` directory.

### Step 2: Include in your CRM `base.html`
```django
{% include "includes/miiciq_widget.html" with miiciq_url="http://127.0.0.1:8000" mode="redirect" %}
```

---

## ⚙️ Widget Configuration Options

You can customize the widget behavior via `data-*` attributes on the `<script>` tag:

| Attribute | Default | Options | Description |
| :--- | :--- | :--- | :--- |
| `data-miiciq-url` | `window.location.origin` | *URL* | Base URL of the MIIC_iQ application instance. |
| `data-mode` | `redirect` | `redirect`, `new_tab`, `slideout` | **`redirect`**: Navigates CRM tab to MIIC_iQ.<br>**`new_tab`**: Opens in new browser tab.<br>**`slideout`**: Opens an in-page slideout drawer! |
| `data-position` | `bottom-right` | `bottom-right`, `bottom-left` | Screen corner positioning. |
| `data-button-text` | `Ask MIICiQ` | *Text* | Text displayed inside the floating launcher button. |
| `data-title` | `MIICiQ Sales & Policy Assistant` | *Text* | Header title in the widget popup. |
| `data-subtitle` | `Private AI Knowledge Assistant` | *Text* | Subheader description. |

---

## 💡 Triggering MIICiQ from Anywhere in your CRM Code

The widget exposes a global JavaScript API `window.MIICiQ`:

### Example 1: Add a "Verify Approval Policy" Button next to a CRM Deal
```html
<button type="button" class="btn btn-sm btn-info" onclick="MIICiQ.ask('What is the approval threshold for a 20% discount on order over $50,000?')">
  🔍 Verify Discount Approval Rule
</button>
```

### Example 2: Programmatically Open the Widget
```javascript
// Open the widget popup
MIICiQ.open();

// Close the widget popup
MIICiQ.close();

// Redirect to MIICiQ with a custom question prefilled
MIICiQ.ask('How do I process a Sales Order in ERP?');
```

---

## 🧪 Live Demo & Testing

You can test this in action right now:
1. Open the interactive CRM demonstration page at:
   **[http://127.0.0.1:8000/crm-demo/](http://127.0.0.1:8000/crm-demo/)**
2. See the floating **"🤖 Ask MIICiQ"** chatbot in the bottom right corner of the CRM deals table.
3. Click any prompt or type a custom question.
4. Watch it redirect smoothly to **MIIC_iQ** with the query pre-filled and an answer streamed with verified citations!
