````markdown
# PII Redaction Tool

## Assignment

This submission implements a DOCX PII redaction pipeline for the supplied Red Herring Prospectus.

The tool detects and replaces:
- Full names
- Email addresses
- Phone numbers
- Company names
- Physical/mailing addresses
- Social Security Numbers (SSNs)
- Credit-card numbers
- Dates of birth
- IPv4 addresses

## Approach

The implementation is hybrid:

1. **Regex detectors** for high-precision structured PII: email, Indian phone numbers, IPv4, SSN, credit cards (with Luhn validation), and explicitly labelled dates of birth.

2. **Document-specific entity inventory** for the supplied prospectus. This inventory contains the reviewed names, company names, contact emails/phones and address spans. The deployed API automatically loads `entity_inventory.json`, while the CLI can also receive it explicitly with `--entities`. This improves recall for names, organizations and addresses because these categories are difficult to detect reliably using regex alone.

3. **Heuristic fallback** when no entity inventory is supplied: corporate suffixes are used for organizations and common Indian surnames plus contextual capitalization are used for names.

4. **Synthetic replacements** are deterministic and type-specific. Emails use `example.com`, IPs use the TEST-NET range `192.0.2.0/24`, and phone numbers use synthetic +91 values.

5. **DOCX coverage** includes normal paragraphs, paragraphs inside tables, headers, and footers.

6. **Document metadata** is sanitized so that identifying information is not unnecessarily retained in the DOCX core properties.

## Usage

```bash
pip install -r requirements.txt
python pii_redactor.py "Red Herring Prospectus.docx" redacted_prospectus.docx --entities entity_inventory.json --report redaction_run.json
````

Without `--entities`, the script falls back to generic detection:

```bash
python pii_redactor.py input.docx output.docx
```

## Web API

`app.py` exposes a FastAPI service with:

* `GET /` — browser upload interface
* `GET /health` — service health check
* `POST /redact` — accepts a DOCX file and returns the redacted DOCX

The API automatically loads `entity_inventory.json` from the application directory, so the document-specific inventory is used during web redaction without requiring manual configuration.

## Tradeoffs

* Names and company names are inherently ambiguous without a trained NER model or a document-specific entity inventory. The inventory was therefore used for the supplied prospectus to prioritize recall.
* Phone-number detection is deliberately conservative to avoid treating financial figures, registration numbers and order-like identifiers as phone numbers.
* Credit-card detection additionally applies the Luhn checksum.
* DOB detection requires an explicit `DOB`/`Date of Birth` label, avoiding false positives on ordinary prospectus dates.
* Address extraction is the hardest category because addresses are split across table cells and line fragments in the source document.
* Paragraph-level replacement preserves the DOCX's overall structure and tables, but edited paragraphs may lose some run-level font formatting.

## Evaluation

The evaluation report contains the rule-level benchmark metrics and a document-level reference-inventory coverage audit. The benchmark is intentionally small and should not be interpreted as a production statistical estimate.

See `evaluation_report.docx` and `evaluation_report.md`.

## Cloud Deployment

The application is configured for deployment using `render.yaml`.

Live deployment:

**[https://scaler-ai-labs-assignment-tqyt.onrender.com](https://scaler-ai-labs-assignment-tqyt.onrender.com)**

The deployed service uses the same redaction pipeline and automatically loads `entity_inventory.json`.

## Files

* `pii_redactor.py` — source code
* `entity_inventory.json` — reviewed entity inventory for this specific prospectus
* `redacted_prospectus.docx` — assignment output
* `evaluation_report.docx` — evaluation strategy and metrics
* `evaluation_report.md` — Markdown version for GitHub
* `app.py` — FastAPI cloud service
* `render.yaml` — Render deployment configuration
* `requirements.txt` — dependencies
* `redaction_run.json` — run manifest

```
```
