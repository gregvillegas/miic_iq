# Laptop Compatibility Reference Template

Use this template when uploading a product datasheet, service manual summary, or internal engineering reference so MIICiQ can answer memory and SSD compatibility questions accurately.

## 1. Document Metadata
- Document Title:
- Manufacturer / Brand:
- Product Family:
- Exact Model Name:
- Model Code / SKU:
- Region / Country Variant:
- Version / Revision:
- Effective Date:
- Source Type: OEM datasheet / service manual / internal engineering validation / sales enablement note
- Prepared By:
- Reviewed By:

## 2. Supported User Questions
List the exact kinds of questions this document is meant to answer.
- Can this laptop be upgraded to 32GB or 64GB RAM?
- How many memory slots are available?
- What RAM type and speed are supported?
- Does the unit support NVMe SSD, SATA SSD, or both?
- What is the maximum supported SSD capacity?
- Which storage slot or form factor is required?
- Are there any compatibility limits for specific configurations?

## 3. Product Identification
- Marketing Model Name:
- Internal Model Code:
- Processor Options:
- Chipset / Platform:
- BIOS Version Requirement:
- Release Year:

## 4. Memory Compatibility
- Installed Memory (Base Configuration):
- Maximum Supported Memory:
- Memory Type: DDR4 / DDR5 / LPDDR5 / etc.
- Memory Speed:
- Number of Slots:
- Empty Slots Available:
- Soldered Memory: Yes / No
- Dual Channel Support: Yes / No
- ECC Support: Yes / No
- Supported Module Sizes:
- Supported Module Ranks / Notes:

### Memory Upgrade Rules
- Rule 1:
- Rule 2:
- Rule 3:

### Unsupported Memory Configurations
- Unsupported configuration:
- Reason:

## 5. Storage / SSD Compatibility
- Installed Storage (Base Configuration):
- Maximum Supported Storage Capacity:
- Storage Interface: PCIe NVMe / SATA / both
- SSD Form Factor: M.2 2280 / 2242 / 2.5-inch / etc.
- Number of Storage Slots:
- Empty Storage Slots Available:
- RAID Support: Yes / No
- Gen Support: PCIe Gen3 / Gen4 / Gen5
- Thermal Shield / Bracket Requirement:

### SSD Upgrade Rules
- Rule 1:
- Rule 2:
- Rule 3:

### Unsupported SSD Configurations
- Unsupported configuration:
- Reason:

## 6. Compatibility Matrix
Use one row per validated option.

| Component Type | Brand / Part Number | Capacity | Interface / Speed | Supported | Conditions / Notes |
| --- | --- | --- | --- | --- | --- |
| Memory | Example DDR5 SODIMM | 16GB | DDR5-5600 | Yes | Tested in slot 1 and slot 2 |
| Memory | Example DDR5 SODIMM | 32GB | DDR5-5600 | Yes | Requires BIOS 1.08 or later |
| SSD | Example NVMe SSD | 1TB | PCIe Gen4 M.2 2280 | Yes | Single-sided module only |
| SSD | Example NVMe SSD | 2TB | PCIe Gen4 M.2 2280 | Yes | Keep thermal pad installed |

## 7. Installation / Validation Notes
- Required screw / bracket:
- BIOS setting to verify:
- Post-upgrade validation steps:
- Known warning messages:
- ESD / handling reminders:

## 8. Sales Guidance
Write short, direct answers that salespeople can use with customers.
- Customer-friendly answer for RAM upgrades:
- Customer-friendly answer for SSD upgrades:
- When to escalate to Engineering:
- When the answer is still unverified:

## 9. Source Evidence
Paste exact excerpts or references from the OEM datasheet or engineering validation notes.

### Source Excerpt 1
- Source Document:
- Page / Section:
- Exact Text:

### Source Excerpt 2
- Source Document:
- Page / Section:
- Exact Text:

## 10. Final Answer Examples
These examples help the AI mirror the wording you want.

### Example Question
Can this laptop support 32GB RAM and a 2TB NVMe SSD?

### Example Grounded Answer
Yes, based on the uploaded compatibility reference, this model supports up to 32GB DDR5 memory and a 2TB NVMe SSD, subject to the listed BIOS and form-factor requirements. See the cited source sections for the exact validated configurations.

## 11. Approval
- Engineering Approver:
- Approval Date:
- Status: Draft / Approved / Superseded

## Authoring Tips
- Use the exact model code, not only the marketing name.
- State maximum capacity explicitly.
- State form factor explicitly, such as `M.2 2280`.
- Write unsupported combinations clearly.
- Include page numbers or section names for every important claim.
- Prefer short bullet points and tables over long paragraphs.
