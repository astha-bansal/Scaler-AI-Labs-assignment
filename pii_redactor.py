#!/usr/bin/env python3
"""
PII Redaction Tool
------------------
Reads a DOCX and replaces PII with synthetic alternatives.

Usage:
    python pii_redactor.py input.docx output.docx --entities entity_inventory.json

The optional entity inventory is useful for high-recall redaction of document-specific
names, companies and addresses. If it is omitted, the script falls back to regex and
lightweight contextual heuristics.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from docx import Document

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
DOB_RE = re.compile(
    r"(?i)\b(?:date\s+of\s+birth|dob)\s*[:=-]?\s*"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})"
)
PHONE_RES = [
    re.compile(r"(?<!\d)\+?\s*91[\s-]*(?:\(\d{2,4}\)|\d{2,4})[\s-]*\d{3,4}[\s-]*\d{3,4}(?!\d)"),
    re.compile(r"(?<!\d)0\d{2,4}[\s-]\d{6,8}(?!\d)"),
    re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),
]
PIN_RE = re.compile(r"(?<!\d)\d{3}\s?\d{3}(?!\d)")
ORG_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&.'’/-]+(?:\s+(?:[A-Z][A-Za-z0-9&.'’/-]+|of|the|India)){1,7})\s+"
    r"(?:Private Limited|Limited|LLP|Bank|Corporation)\b"
)
COMMON_SURNAMES = set("""
Mehta Hegde Shetty Patil Sharma Joshi Shah Sarkar Rastogi Diwan Bacha Gawade
Teli Jadhav Gavankar Badai Ramani Raste Shukla Wakhele Pulloor Soni Rai
Balasubramanian Prasad Sarvaiya Tiwari Jacob Bhagwat Malvadkar Gopalkrishnan
Bhandary Menon Munot
""".split())

FAKE_NAMES = [
    "Alex Carter", "Jordan Miller", "Taylor Morgan", "Casey Bennett", "Riley Parker",
    "Morgan Ellis", "Avery Brooks", "Jamie Collins", "Cameron Reed", "Drew Foster",
    "Quinn Bailey", "Harper Wilson", "Logan Turner", "Peyton Cooper", "Reese Walker",
    "Blake Sullivan", "Rowan Mitchell", "Skyler Hayes", "Emerson Grant", "Finley Ross",
    "Charlie Adams", "Dakota Hughes", "Kendall Price", "Sage Bennett", "Robin Clarke",
    "Elliot Moore", "Parker Young", "Sydney Bell", "Milan Harper", "Arden Scott",
]
FAKE_COMPANIES = [
    "Example Manufacturing Limited", "Northstar Industrial Limited", "BluePeak Financial Limited",
    "Summit Engineering Limited", "Evergreen Systems Limited", "Pioneer Services Limited",
    "Silverline Technologies Limited", "Acme Industrial Limited", "Metro Business Limited",
    "Vertex Consulting Limited", "Cedar Logistics Limited", "Harbor Capital Limited",
    "Atlas Infrastructure Limited", "Crestline Holdings Limited", "Oakridge Enterprises Limited",
    "BrightPath Solutions Limited", "Redwood Industries Limited", "Lighthouse Ventures Limited",
    "Westbridge Services Limited", "Granite Commercial Limited",
]
FAKE_ADDRESSES = [
    "42 Example Road, Pune – 411001, Maharashtra, India",
    "17 Sample Avenue, Mumbai – 400001, Maharashtra, India",
    "8 Demo Industrial Area, Bengaluru – 560001, Karnataka, India",
    "25 Placeholder Street, Hyderabad – 500001, Telangana, India",
    "61 Test Park, New Delhi – 110001, Delhi, India",
]

def iter_paragraphs(parent) -> Iterable:
    for p in getattr(parent, "paragraphs", []):
        yield p
    for table in getattr(parent, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from iter_paragraphs(cell)

def all_story_paragraphs(doc: Document) -> list:
    out = list(iter_paragraphs(doc))
    for section in doc.sections:
        for part in (
            section.header, section.first_page_header, section.even_page_header,
            section.footer, section.first_page_footer, section.even_page_footer
        ):
            out.extend(iter_paragraphs(part))
    return out

def luhn_ok(value: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", value)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0

def valid_ip(value: str) -> bool:
    try:
        return all(0 <= int(part) <= 255 for part in value.split("."))
    except ValueError:
        return False

def load_inventory(path: Path | None, text: str) -> dict[str, list[str]]:
    if path:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: list(dict.fromkeys(data.get(k, []))) for k in (
            "persons", "companies", "emails", "phones", "addresses",
            "ssns", "credit_cards", "dates_of_birth", "ip_addresses"
        )}

    entities = {
        "persons": [],
        "companies": [],
        "emails": sorted(set(EMAIL_RE.findall(text))),
        "phones": [],
        "addresses": [],
        "ssns": sorted(set(SSN_RE.findall(text))),
        "credit_cards": sorted(set(x for x in CC_RE.findall(text) if luhn_ok(x))),
        "dates_of_birth": [m.group(0) for m in DOB_RE.finditer(text)],
        "ip_addresses": sorted(set(x for x in IP_RE.findall(text) if valid_ip(x))),
    }
    for pattern in PHONE_RES:
        entities["phones"].extend(pattern.findall(text))

    # Lightweight company heuristic.
    for m in ORG_RE.finditer(text):
        value = re.sub(r"\s+", " ", m.group()).strip(" ,;:")
        if len(value.split()) <= 9:
            entities["companies"].append(value)

    # Lightweight person heuristic: capitalized names containing a likely surname.
    name_re = re.compile(r"\b[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){1,4}\b")
    for m in name_re.finditer(text):
        value = m.group().strip(" ,;:")
        words = value.split()
        if len(words) <= 5 and any(w.strip(".") in COMMON_SURNAMES for w in words):
            entities["persons"].append(value)

    return {k: list(dict.fromkeys(v)) for k, v in entities.items()}

def phone_key(value: str) -> str:
    return re.sub(r"\D", "", value)

def make_maps(entities: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    maps = {}
    maps["persons"] = {v: FAKE_NAMES[i % len(FAKE_NAMES)] for i, v in enumerate(entities["persons"])}
    maps["companies"] = {v: FAKE_COMPANIES[i % len(FAKE_COMPANIES)] for i, v in enumerate(entities["companies"])}
    maps["emails"] = {v: f"contact{i+1:03d}@example.com" for i, v in enumerate(entities["emails"])}
    phone_values = {}
    for i, value in enumerate(entities["phones"]):
        phone_values.setdefault(phone_key(value), f"+91 90000 {i+1:05d}")
    maps["phones"] = {v: phone_values[phone_key(v)] for v in entities["phones"]}
    maps["ssns"] = {v: f"000-00-{i+1:04d}" for i, v in enumerate(entities["ssns"])}
    maps["credit_cards"] = {v: f"4111 1111 1111 {1111+i:04d}" for i, v in enumerate(entities["credit_cards"])}
    maps["dates_of_birth"] = {v: "January 1, 1990" for v in entities["dates_of_birth"]}
    maps["ip_addresses"] = {v: f"192.0.2.{i+1}" for i, v in enumerate(entities["ip_addresses"])}
    maps["addresses"] = {v: FAKE_ADDRESSES[i % len(FAKE_ADDRESSES)] for i, v in enumerate(entities["addresses"])}
    return maps

def replace_with_map(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    if not mapping or not text:
        return text, 0
    ordered = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(x) for x in ordered), re.I)
    lower_map = {k.lower(): v for k, v in mapping.items()}
    count = 0
    def repl(match):
        nonlocal count
        count += 1
        return lower_map[match.group(0).lower()]
    return pattern.sub(repl, text), count

def redact_paragraph(text: str, maps: dict[str, dict[str, str]]) -> tuple[str, dict[str, int]]:
    counts = {k: 0 for k in maps}
    for kind in ("addresses", "emails", "phones", "ip_addresses", "ssns",
                 "credit_cards", "dates_of_birth", "persons", "companies"):
        text, n = replace_with_map(text, maps[kind])
        counts[kind] += n
    return text, counts

def redact(input_path: Path, output_path: Path, inventory_path: Path | None = None):
    doc = Document(str(input_path))
    paragraphs = all_story_paragraphs(doc)
    source_text = "\n".join(p.text for p in paragraphs if p.text)
    entities = load_inventory(inventory_path, source_text)
    maps = make_maps(entities)
    counts = {k: 0 for k in maps}

    for paragraph in paragraphs:
        new_text, local = redact_paragraph(paragraph.text, maps)
        if new_text != paragraph.text:
            paragraph.text = new_text
        for kind, n in local.items():
            counts[kind] += n

    props = doc.core_properties
    props.author = "PII Redaction Tool"
    props.last_modified_by = "PII Redaction Tool"
    props.comments = ""
    props.keywords = ""
    props.title = "Redacted Prospectus"
    props.subject = "Redacted document"
    doc.save(str(output_path))

    result = {
        "detected_unique_entities": {k: len(v) for k, v in entities.items()},
        "replacements_applied": counts,
        "output": str(output_path),
    }
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--entities", type=Path, default=None,
                        help="Optional audited entity inventory JSON for higher recall.")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    result = redact(args.input, args.output, args.entities)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
