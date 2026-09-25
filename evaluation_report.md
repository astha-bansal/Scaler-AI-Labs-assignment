# Evaluation Strategy and Metrics

## 1. Evaluation strategy

Two complementary checks were used.

### A. Rule-level labelled benchmark

A 27-case benchmark was created with positive and negative examples covering the required PII types. The negative examples intentionally included common hard negatives such as order/reference numbers, ordinary dates, invalid IPv4 values, and non-DOB dates.

Results:

| Metric | Result |
|---|---:|
| Accuracy | 92.59% |
| Precision | 87.50% |
| Recall | 100.00% |
| F1 | 93.33% |
| True positives | 14 |
| True negatives | 11 |
| False positives | 2 |
| False negatives | 0 |

These are benchmark metrics, not a statistical estimate of production performance.

### B. Document-level reference inventory audit

For the supplied 127-page prospectus, the reviewed reference inventory contained:

| PII type | Unique reference instances |
|---|---:|
| Full names | 54 |
| Company names | 54 |
| Email addresses | 26 |
| Phone numbers | 21 |
| Physical/mailing address spans | 44 |
| SSNs | 0 |
| Credit-card numbers | 0 |
| Dates of birth | 0 |
| IPv4 addresses | 0 |

Every reference name, company, email, phone and address string was absent from the redacted output. The structured categories with zero source instances are reported as **N/A for recall**, rather than assigning an artificial 100%.

The redaction run applied:

| Category | Replacements |
|---|---:|
| Persons | 210 |
| Companies | 135 |
| Emails | 52 |
| Phones | 32 |
| Addresses | 48 |
| SSNs | 0 |
| Credit cards | 0 |
| DOBs | 0 |
| IP addresses | 0 |

## 2. Interpretation

The high recall on the supplied document comes from combining deterministic regex detection with a reviewed document-specific entity inventory. This is intentional: the assignment prioritizes catching every PII instance.

The main precision risks are:
- capitalized names that are not actually people,
- numeric strings that resemble telephone numbers,
- addresses fragmented across tables/line breaks.

For a larger production corpus, the next improvement would be adding a trained NER component (for example, spaCy/Presidio) and maintaining a human-reviewed validation set.

## 3. Reproducibility

Run:

```bash
python pii_redactor.py "Red Herring Prospectus.docx" redacted_prospectus.docx --entities entity_inventory.json --report redaction_run.json
```

The generated output is the submitted `redacted_prospectus.docx`.
