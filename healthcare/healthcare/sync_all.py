import frappe
import json
import re

from pathlib import Path
from datetime import datetime, date
from decimal import Decimal

try:
    from healthcare.healthcare.khanza_satusehat.constants import TARGET_DOCTYPES as KHANZA_TARGET_DOCTYPES
except Exception:
    KHANZA_TARGET_DOCTYPES = ()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FHIR_EXPORT_PATH = Path(
    "/mnt/c/Program Files/duckdb_cli-windows-amd64/data/healthcare_data"
)

SYNC_STATE_PATH = FHIR_EXPORT_PATH / "_sync_state"

DEFAULT_LAST_SYNC = "2000-01-01 00:00:00.000000"

# FHIR resource type mapping: Frappe DocType -> FHIR resourceType.
BASE_TARGET_DOCTYPES = [
    "Patient",
    "Medication",
    "Medication Linked Item",
    "Healthcare Practitioner",
    "Patient Encounter",
    "Healthcare Service Unit Type",
    "Healthcare Service Unit",
    "Clinical Procedure Template",
    "Inpatient Medication Entry",
    "Therapy Plan",
    "Lab Test Template",
    "Patient Appointment",
    "Therapy Plan Template",
    "Appointment Type",
    "Therapy Session",
    "Lab Test",
    "Diagnostic Report",
    "Observation Reference Range",
    "Observation Template",
]

FHIR_RESOURCE_TYPE_OVERRIDES = {
    "Allergy": "AllergyIntolerance",
    "Clinical Note": "Composition",
    "Clinical Procedure": "Procedure",
    "Diagnosis": "Condition",
    "Diagnostic Report": "DiagnosticReport",
    "Healthcare Practitioner": "Practitioner",
    "Medication Dispense": "MedicationDispense",
    "Medication Request": "MedicationRequest",
    "Medication Statement": "MedicationStatement",
    "Patient Assessment": "ClinicalImpression",
    "Patient Encounter": "Encounter",
    "Questionnaire Response": "QuestionnaireResponse",
    "Service Request": "ServiceRequest",
    "Therapy Plan": "CarePlan",
    "Vital Signs": "Observation",
}

FHIR_RESOURCE_TYPE_MAP = {}
for doctype in list(dict.fromkeys(BASE_TARGET_DOCTYPES + list(KHANZA_TARGET_DOCTYPES))):
    FHIR_RESOURCE_TYPE_MAP[doctype] = FHIR_RESOURCE_TYPE_OVERRIDES.get(
        doctype,
        doctype.replace(" ", ""),
    )

TARGET_DOCTYPES = list(FHIR_RESOURCE_TYPE_MAP.keys())

# Standard FHIR base URL for identifier systems
FHIR_BASE_URL = "https://erpnext.com/fhir"

# Frappe fieldtypes that are stored as actual columns in the database.
# UI/layout-only types (Section Break, Column Break, HTML, Fold, etc.)
# are NOT stored in the DB and must be excluded from SELECT queries.
DB_FIELDTYPES = {
    "Autocomplete",
    "Attach",
    "Attach Image",
    "Barcode",
    "Check",
    "Code",
    "Color",
    "Currency",
    "Data",
    "Date",
    "Datetime",
    "Duration",
    "Dynamic Link",
    "Float",
    "Geolocation",
    "Int",
    "JSON",
    "Link",
    "Long Text",
    "Markdown Editor",
    "Password",
    "Percent",
    "Phone",
    "Rating",
    "Read Only",
    "Select",
    "Small Text",
    "Text",
    "Text Editor",
    "Time",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def slugify(value: str) -> str:
    """Convert a string to a safe filename slug."""
    return re.sub(
        r"[^a-z0-9_]+",
        "_",
        value.lower().replace(" ", "_"),
    ).strip("_")


def get_export_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def serialize_value(value):
    """
    Recursively serialize a value to a JSON-safe type.
    Handles: None, datetime, date, Decimal, dict, list, and primitives.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if not isinstance(value, (str, int, float, bool)):
        return str(value)
    return value


def serialize_row(row: dict) -> dict:
    """Serialize all values in a row dict."""
    return {key: serialize_value(value) for key, value in row.items()}


# ---------------------------------------------------------------------------
# Sync state management
# ---------------------------------------------------------------------------

def get_last_sync_file(doctype: str) -> Path:
    return SYNC_STATE_PATH / f"{slugify(doctype)}_last_sync.txt"


def get_last_sync_time(doctype: str) -> str:
    sync_file = get_last_sync_file(doctype)
    if sync_file.exists():
        return sync_file.read_text().strip()
    return DEFAULT_LAST_SYNC


def update_last_sync_time(doctype: str, sync_time: str) -> None:
    sync_file = get_last_sync_file(doctype)
    sync_file.parent.mkdir(parents=True, exist_ok=True)
    sync_file.write_text(str(sync_time))


# ---------------------------------------------------------------------------
# Field discovery
# ---------------------------------------------------------------------------

def get_db_columns(doctype: str) -> set:
    """
    Return the set of column names that actually exist in the DB table
    for this DocType. This is the ground truth — meta fields that haven't
    been migrated yet won't appear here.
    """
    return set(frappe.db.get_table_columns(doctype))


def get_doctype_fields(doctype: str) -> list:
    """
    Return fields that are both:
    - stored as DB columns (via DB_FIELDTYPES whitelist), AND
    - actually present in the live DB table (via frappe.db.get_table_columns)

    This double-check prevents errors from fields defined in meta but not
    yet migrated to the database (e.g. custom fields, pending patches).
    """
    meta = frappe.get_meta(doctype)
    db_columns = get_db_columns(doctype)

    base_fields = [
        "name",
        "creation",
        "modified",
        "modified_by",
        "owner",
        "docstatus",
        "idx",
    ]

    doc_fields = [
        field.fieldname
        for field in meta.fields
        if (
            field.fieldname
            and field.fieldtype in DB_FIELDTYPES
            and field.fieldname in db_columns      # must exist in actual DB
        )
    ]

    all_fields = base_fields + doc_fields

    # Deduplicate while preserving order
    seen = set()
    unique_fields = []
    for f in all_fields:
        if f not in seen:
            seen.add(f)
            unique_fields.append(f)

    return unique_fields


def get_child_doctypes(doctype: str) -> list:
    """
    Return [{fieldname, child_doctype}] for all Table fields on this DocType.
    """
    meta = frappe.get_meta(doctype)
    return [
        {"fieldname": field.fieldname, "child_doctype": field.options}
        for field in meta.fields
        if field.fieldtype in ("Table", "Table MultiSelect") and field.options
    ]


def get_child_rows(parent_doctype: str, child_doctype: str, parent_name: str) -> list:
    """Fetch all rows of a child table for a specific parent document."""
    child_meta = frappe.get_meta(child_doctype)
    child_db_columns = get_db_columns(child_doctype)

    child_fields = ["name", "idx"] + [
        f.fieldname
        for f in child_meta.fields
        if (
            f.fieldname
            and f.fieldtype in DB_FIELDTYPES
            and f.fieldname in child_db_columns
        )
    ]

    # Deduplicate
    child_fields = list(dict.fromkeys(child_fields))

    rows = frappe.get_all(
        child_doctype,
        filters={"parent": parent_name, "parenttype": parent_doctype},
        fields=child_fields,
        order_by="idx asc",
        ignore_permissions=True,
    )

    return [serialize_row(row) for row in rows]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_new_docs(doctype: str, last_sync: str) -> list:
    """Fetch all documents modified after last_sync, with all DB fields."""
    fields = get_doctype_fields(doctype)

    return frappe.get_all(
        doctype,
        filters={"modified": [">", last_sync]},
        fields=fields,
        order_by="modified asc",
        ignore_permissions=True,
    )


# ---------------------------------------------------------------------------
# FHIR resource builder
# ---------------------------------------------------------------------------

def build_fhir_resource(doctype: str, row: dict, child_tables: list) -> dict:
    """
    Wrap a Frappe document as a FHIR-compatible resource.

    {
        "resourceType": "<DocTypeWithoutSpaces>",
        "id": "<name>",
        "meta": { "lastUpdated", "versionId", "source", "tag" },
        "identifier": [{ "system", "value" }],
        "extension": [{ "url": ".../fields", "extension": [...per-field...] }],
        "_childTables": { "<fieldname>": [<rows>] },
        "_exportMeta": { "sourceDoctype", "exportedAt", "frappeName" }
    }
    """
    resource_type = FHIR_RESOURCE_TYPE_MAP.get(doctype, doctype.replace(" ", ""))
    clean = serialize_row(row)

    doc_name = clean.get("name", "")
    last_updated = clean.get("modified") or datetime.now().isoformat()

    field_extensions = [
        {
            "url": fieldname,
            "valueString": str(value) if value is not None else None,
        }
        for fieldname, value in clean.items()
    ]

    resource = {
        "resourceType": resource_type,
        "id": doc_name,
        "meta": {
            "source": f"{FHIR_BASE_URL}/{slugify(doctype)}",
            "lastUpdated": last_updated,
            "versionId": str(last_updated),
            "tag": [
                {
                    "system": f"{FHIR_BASE_URL}/doctype",
                    "code": "frappe-doctype",
                    "display": doctype,
                }
            ],
        },
        "identifier": [
            {
                "system": f"{FHIR_BASE_URL}/{slugify(doctype)}/id",
                "value": doc_name,
            }
        ],
        "extension": [
            {
                "url": f"{FHIR_BASE_URL}/{slugify(doctype)}/fields",
                "extension": field_extensions,
            }
        ],
        "_exportMeta": {
            "sourceDoctype": doctype,
            "exportedAt": datetime.now().isoformat(),
            "frappeName": doc_name,
        },
    }

    if child_tables:
        resource["_childTables"] = {}
        for ct in child_tables:
            rows = get_child_rows(doctype, ct["child_doctype"], doc_name)
            if rows:
                resource["_childTables"][ct["fieldname"]] = rows

    return resource


# ---------------------------------------------------------------------------
# NDJSON writer
# ---------------------------------------------------------------------------

def write_ndjson(doctype: str, resources: list) -> Path:
    """Write FHIR resources as NDJSON (one JSON object per line)."""
    export_folder = FHIR_EXPORT_PATH / get_export_date()
    export_folder.mkdir(parents=True, exist_ok=True)

    file_path = export_folder / f"{slugify(doctype)}.ndjson"

    with open(file_path, "w", encoding="utf-8") as f:
        for resource in resources:
            f.write(json.dumps(resource, ensure_ascii=False))
            f.write("\n")

    return file_path


# ---------------------------------------------------------------------------
# Per-doctype export orchestration
# ---------------------------------------------------------------------------

def export_doctype(doctype: str) -> None:
    last_sync = get_last_sync_time(doctype)

    print(f"\nEXPORTING : {doctype}")
    print(f"LAST SYNC : {last_sync}")

    rows = fetch_new_docs(doctype, last_sync)

    print(f"NEW ROWS  : {len(rows)}")

    if not rows:
        return

    child_tables = get_child_doctypes(doctype)

    resources = [
        build_fhir_resource(doctype, row, child_tables)
        for row in rows
    ]

    file_path = write_ndjson(doctype, resources)

    latest_modified = rows[-1].get("modified") or DEFAULT_LAST_SYNC
    update_last_sync_time(doctype, latest_modified)

    print(f"SUCCESS   -> {file_path}")
    print(f"LAST SYNC -> {latest_modified}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    print("=" * 60)
    print("HEALTHCARE FHIR EXPORT STARTED")
    print("=" * 60)

    success_count = 0
    error_count = 0

    for doctype in TARGET_DOCTYPES:
        try:
            export_doctype(doctype)
            success_count += 1

        except Exception as error:
            error_count += 1
            print(f"ERROR [{doctype}]: {error}")
            frappe.log_error(
                title=f"Healthcare FHIR Export Error: {doctype}",
                message=frappe.get_traceback(),
            )

    print("\n" + "=" * 60)
    print("HEALTHCARE FHIR EXPORT FINISHED")
    print(f"  success : {success_count}")
    print(f"  errors  : {error_count}")
    print("=" * 60)
