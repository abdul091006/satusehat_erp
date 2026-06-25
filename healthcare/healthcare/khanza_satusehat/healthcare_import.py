import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from .constants import (
    CUSTOM_FIELD_TARGET_DOCTYPES,
    FHIR_FIELD_DOCTYPE,
    QUEUE_DOCTYPE,
    RESOURCE_TARGETS,
)
from .document_events import sync_all_queue_target_docstatus, sync_queue_target_docstatus
from .utils import _as_dict, _json_dumps

TARGET_SUBMIT_ROLES = ("System Manager", "Healthcare Administrator")
TARGET_SUBMIT_PERMISSIONS = {
	"read": 1,
	"write": 1,
	"create": 1,
	"delete": 1,
	"submit": 1,
	"cancel": 1,
	"amend": 1,
	"report": 1,
	"export": 1,
	"print": 1,
	"email": 1,
	"share": 1,
	"select": 1,
}

def ensure_khanza_custom_fields(sync_existing=True, ensure_submit=True):
	if ensure_submit:
		ensure_target_doctypes_submitable()

	if not frappe.db.exists("DocType", FHIR_FIELD_DOCTYPE):
		return

	common_fields = [
		{
			"fieldname": "fhir_section",
			"label": "FHIR",
			"fieldtype": "Section Break",
			"insert_after": None,
		},
		{
			"fieldname": "khanza_queue",
			"label": "Source Sync Record",
			"fieldtype": "Link",
			"options": QUEUE_DOCTYPE,
			"read_only": 1,
			"insert_after": "fhir_section",
		},
		{
			"fieldname": "khanza_external_id",
			"label": "External ID",
			"fieldtype": "Data",
			"read_only": 1,
			"unique": 1,
			"insert_after": "khanza_queue",
		},
		{
			"fieldname": "khanza_function",
			"label": "Source Function",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "khanza_external_id",
		},
		{
			"fieldname": "satusehat_resource_type",
			"label": "FHIR Resource Type",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "khanza_function",
		},
		{
			"fieldname": "satusehat_resource_id",
			"label": "FHIR Resource ID",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "satusehat_resource_type",
		},
		{
			"fieldname": "fhir_status",
			"label": "FHIR Status",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "satusehat_resource_id",
		},
		{
			"fieldname": "khanza_patient_reference",
			"label": "FHIR Patient Reference",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "fhir_status",
		},
		{
			"fieldname": "khanza_encounter_reference",
			"label": "FHIR Encounter Reference",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "khanza_patient_reference",
		},
		{
			"fieldname": "khanza_fhir_fields",
			"label": "FHIR Fields",
			"fieldtype": "Table",
			"options": FHIR_FIELD_DOCTYPE,
			"read_only": 1,
			"insert_after": "khanza_encounter_reference",
		},
		{
			"fieldname": "khanza_fhir_payload",
			"label": "FHIR Payload",
			"fieldtype": "Code",
			"options": "JSON",
			"read_only": 1,
			"insert_after": "khanza_fhir_fields",
		},
	]
	fields_by_doctype = {}
	for doctype in CUSTOM_FIELD_TARGET_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		missing_fields = [
			field for field in common_fields
			if not _doctype_has_field(doctype, field["fieldname"])
		]
		if missing_fields:
			fields_by_doctype[doctype] = missing_fields

	if fields_by_doctype:
		create_custom_fields(fields_by_doctype)
	if sync_existing:
		sync_all_queue_target_docstatus()

def ensure_target_doctypes_submitable():
	for role in TARGET_SUBMIT_ROLES:
		_ensure_role(role)

	for doctype in CUSTOM_FIELD_TARGET_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue

		frappe.db.set_value("DocType", doctype, "is_submittable", 1, update_modified=False)
		for role in TARGET_SUBMIT_ROLES:
			_ensure_submit_permission(doctype, role)
		frappe.clear_cache(doctype=doctype)

	frappe.clear_cache()

def _ensure_role(role):
	if frappe.db.exists("Role", role):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)

def _ensure_submit_permission(doctype, role):
	perm_name = frappe.db.exists(
		"DocPerm",
		{
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
		},
	)

	if perm_name:
		frappe.db.set_value(
			"DocPerm",
			perm_name,
			TARGET_SUBMIT_PERMISSIONS,
			update_modified=False,
		)
		return

	doc = frappe.get_doc("DocType", doctype)
	doc.is_submittable = 1
	doc.append("permissions", {"role": role, "permlevel": 0, **TARGET_SUBMIT_PERMISSIONS})
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)

def _doctype_has_field(doctype, fieldname):
	return bool(
		frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname})
		or frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})
	)

def _text(value):
	if value is None:
		return ""
	if isinstance(value, str):
		return value
	return str(value)

def _first(value):
	return value[0] if isinstance(value, list) and value else {}

def _coding_text(codeable):
	if not isinstance(codeable, dict):
		return ""
	coding = _first(codeable.get("coding"))
	return codeable.get("text") or coding.get("display") or coding.get("code") or ""

def _coding_code(codeable):
	if not isinstance(codeable, dict):
		return ""
	coding = _first(codeable.get("coding"))
	return coding.get("code") or codeable.get("text") or coding.get("display") or ""

def _reference_id(reference):
	reference = _text(reference)
	return reference.split("/", 1)[1] if "/" in reference else reference

def _find_reference(fhir, resource_type):
	prefix = f"{resource_type}/"

	def walk(value):
		if isinstance(value, dict):
			reference = value.get("reference")
			if isinstance(reference, str) and reference.startswith(prefix):
				return value
			for child in value.values():
				found = walk(child)
				if found:
					return found
		elif isinstance(value, list):
			for child in value:
				found = walk(child)
				if found:
					return found
		return None

	return walk(fhir) or {}

def _patient_reference(fhir):
	return fhir.get("subject") or fhir.get("patient") or _find_reference(fhir, "Patient")

def _practitioner_reference(fhir):
	for key in ("participant", "performer", "requester", "asserter", "recorder"):
		value = fhir.get(key)
		if isinstance(value, dict):
			if value.get("reference", "").startswith("Practitioner/"):
				return value
			actor = value.get("actor")
			if isinstance(actor, dict) and actor.get("reference", "").startswith("Practitioner/"):
				return actor
		if isinstance(value, list):
			for row in value:
				if isinstance(row, dict):
					if row.get("reference", "").startswith("Practitioner/"):
						return row
					actor = row.get("actor")
					if isinstance(actor, dict) and actor.get("reference", "").startswith("Practitioner/"):
						return actor
	return _find_reference(fhir, "Practitioner")

def _encounter_reference(fhir):
	return fhir.get("encounter") or _find_reference(fhir, "Encounter")

def _effective_datetime(fhir):
	period = fhir.get("period") or fhir.get("performedPeriod") or fhir.get("effectivePeriod")
	if isinstance(period, dict):
		return period.get("start") or period.get("end")
	return (
		fhir.get("effectiveDateTime")
		or fhir.get("performedDateTime")
		or fhir.get("authoredOn")
		or fhir.get("recordedDate")
		or fhir.get("issued")
		or fhir.get("occurrenceDateTime")
		or fhir.get("date")
	)

def _date_part(value):
	value = _text(value)
	return value[:10] if value else None

def _time_part(value):
	value = _text(value)
	if "T" in value:
		return value.split("T", 1)[1][:8]
	return value[11:19] if len(value) >= 19 else None

def _target_for_fhir(fhir):
	resource_type = fhir.get("resourceType")
	if resource_type == "Observation":
		category_code = ""
		for category in fhir.get("category") or []:
			coding = _first(category.get("coding"))
			category_code = (coding.get("code") or "").lower()
			if category_code == "vital-signs":
				target = "Vital Signs"
				break
		else:
			target = "Observation"
	else:
		target = RESOURCE_TARGETS.get(resource_type, "Clinical Note")

	if not frappe.db.exists("DocType", target):
		return "Clinical Note"
	return target

def _function_for_fhir(fhir):
	resource_type = fhir.get("resourceType")
	target = _target_for_fhir(fhir)
	category_text = " ".join(
		[
			_coding_text(category)
			for category in (fhir.get("category") or [])
			if isinstance(category, dict)
		]
	).lower()
	if resource_type == "Observation" and target == "Vital Signs":
		return "observationTTV"
	if resource_type == "ServiceRequest":
		return "servicerequestradiologi" if "imaging" in category_text else "servicerequestlab"
	if resource_type == "Specimen":
		return "specimen"
	if resource_type == "DiagnosticReport":
		return "diagnosticreportradiologi" if "imaging" in category_text else "diagnosticreportlab"
	return {
		"Encounter": "encounter",
		"ClinicalImpression": "clinicalimpression",
		"Immunization": "vaksin",
		"Procedure": "prosedur",
		"Condition": "condition",
		"Composition": "dietgizi",
		"Medication": "medication",
		"MedicationRequest": "medicationrequest",
		"MedicationDispense": "medicationdispense",
		"CarePlan": "careplan",
		"MedicationStatement": "medicationstatement",
		"QuestionnaireResponse": "qrtelaahresep",
		"AllergyIntolerance": "alergi",
	}.get(resource_type, resource_type or "unknown")

def _flatten_fhir(value, prefix=""):
	rows = []
	if isinstance(value, dict):
		for key, child in value.items():
			child_prefix = f"{prefix}.{key}" if prefix else key
			rows.extend(_flatten_fhir(child, child_prefix))
	elif isinstance(value, list):
		for idx, child in enumerate(value):
			rows.extend(_flatten_fhir(child, f"{prefix}[{idx}]"))
	else:
		rows.append(
			{
				"field_path": prefix,
				"value_type": type(value).__name__,
				"value": "" if value is None else _text(value),
			}
		)
	return rows

def _set_if_field(doc, fieldname, value):
	if value in (None, "") or not doc.meta.has_field(fieldname):
		return
	field = doc.meta.get_field(fieldname)
	value = _coerce_for_field(field, value)
	if field.fieldtype == "Link" and field.options and not frappe.db.exists(field.options, value):
		return
	if field.fieldtype == "Select" and field.options:
		options = [option for option in field.options.split("\n") if option]
		if options and value not in options:
			return
	doc.set(fieldname, value)

def _coerce_for_field(field, value):
	if value in (None, ""):
		return value
	if not isinstance(value, str):
		return value

	value = value.strip()
	if field.fieldtype == "Datetime" and "T" in value and len(value) >= 19:
		return value[:19].replace("T", " ")
	if field.fieldtype == "Date":
		return value[:10]
	if field.fieldtype == "Time":
		if "T" in value:
			return value.split("T", 1)[1][:8]
		return value[:8]
	return value

def _append_fhir_audit_fields(doc, fhir, queue_doc, external_id, khanza_function):
	for row in _flatten_fhir(fhir):
		doc.append("khanza_fhir_fields", row)
	doc.khanza_queue = queue_doc.name
	doc.khanza_external_id = external_id
	doc.khanza_function = khanza_function
	doc.satusehat_resource_type = fhir.get("resourceType")
	doc.satusehat_resource_id = fhir.get("id")
	if doc.meta.has_field("fhir_status"):
		doc.fhir_status = fhir.get("status")
	doc.khanza_patient_reference = (_patient_reference(fhir) or {}).get("reference")
	doc.khanza_encounter_reference = (_encounter_reference(fhir) or {}).get("reference")
	doc.khanza_fhir_payload = _json_dumps(fhir)

def _ensure_gender(gender):
	gender = gender or "Other"
	if not frappe.db.exists("Gender", gender):
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	return gender

def _ensure_patient(reference):
	ref = _reference_id((reference or {}).get("reference"))
	display = (reference or {}).get("display") or ref or "Unknown Patient"
	if not ref:
		return None
	existing = frappe.db.exists("Patient", {"satusehat_resource_id": ref}) or frappe.db.exists("Patient", {"uid": ref})
	if existing:
		return existing
	doc = frappe.new_doc("Patient")
	doc.first_name = display[:140]
	doc.patient_name = display[:140]
	doc.sex = _ensure_gender("Other")
	doc.uid = ref
	doc.satusehat_resource_id = ref
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_practitioner(reference):
	ref = _reference_id((reference or {}).get("reference"))
	display = (reference or {}).get("display") or ref or "Unknown Practitioner"
	if not ref:
		return None
	existing = frappe.db.exists("Healthcare Practitioner", {"satusehat_resource_id": ref})
	if existing:
		return existing
	doc = frappe.new_doc("Healthcare Practitioner")
	doc.first_name = display[:140]
	doc.practitioner_name = display[:140]
	doc.status = "Active"
	doc.satusehat_resource_id = ref
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _default_company():
	company = frappe.defaults.get_global_default("company")
	if company:
		return company
	company = frappe.db.get_value("Company", {}, "name")
	if company:
		return company
	return None

def _quantity_value(fhir):
	quantity = fhir.get("valueQuantity") or {}
	return quantity.get("value")

def _quantity_unit(fhir):
	quantity = fhir.get("valueQuantity") or {}
	return quantity.get("unit") or quantity.get("code")

def _ensure_medication_class(value):
	value = _text(value).strip() or "Tablet"
	if not frappe.db.exists("Medication Class", value):
		doc = frappe.new_doc("Medication Class")
		doc.medication_class = value
		doc.insert(ignore_permissions=True)
	return value

def _ensure_uom(value):
	value = _text(value).strip() or "mg"
	if frappe.db.exists("UOM", value):
		return value

	try:
		doc = frappe.new_doc("UOM")
		doc.uom_name = value
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		fallback = (
			frappe.db.exists("UOM", "mg")
			or frappe.db.exists("UOM", "Nos")
			or frappe.db.get_single_value("Stock Settings", "stock_uom")
		)
		return fallback or value

def _medication_form_text(fhir):
	return _coding_text(fhir.get("form")) or "Tablet"

def _medication_strength(fhir):
	search_text = " ".join(
		[
			_coding_text(fhir.get("code")),
			_coding_code(fhir.get("code")),
			_text(fhir.get("id")),
		]
	)
	match = re.search(
		r"(?i)(\d+(?:[\.,]\d+)?)\s*(mcg|microgram|mg|g|gram|ml|mL|l|iu|unit|units)\b",
		search_text,
	)
	if not match:
		return 1, "mg"

	value = float(match.group(1).replace(",", "."))
	unit = match.group(2)
	unit_map = {
		"microgram": "mcg",
		"gram": "g",
		"ml": "mL",
		"unit": "Unit",
		"units": "Unit",
	}
	return value, unit_map.get(unit.lower(), unit)

def _clean_link_name(value, fallback):
	value = re.sub(r"\s+", " ", _text(value)).strip()
	value = re.sub(r"[\\/#?%:;]+", "-", value)
	return (value or fallback)[:140]

def _insert_minimal_doc(doctype, values):
	doc = frappe.new_doc(doctype)
	for key, value in values.items():
		if doc.meta.has_field(key) and value not in (None, ""):
			doc.set(key, value)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_code_system(name, uri=None):
	name = _clean_link_name(name, "Khanza Code System")
	if frappe.db.exists("Code System", name):
		return name

	doc = frappe.new_doc("Code System")
	doc.code_system = name
	doc.uri = uri or f"http://terminology.khanza.local/CodeSystem/{name.lower().replace(' ', '-')}"
	if doc.meta.has_field("experimental"):
		doc.experimental = 0
	if doc.meta.has_field("custom"):
		doc.custom = 1
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_code_value(code, system, display=None):
	code = _clean_link_name(code, "unknown")
	system = _ensure_code_system(system)
	existing = frappe.db.exists("Code Value", {"code_system": system, "code_value": code})
	if existing:
		return existing

	doc = frappe.new_doc("Code Value")
	doc.code_system = system
	doc.code_value = code
	doc.display = (display or code)[:140]
	if doc.meta.has_field("experimental"):
		doc.experimental = 0
	if doc.meta.has_field("custom"):
		doc.custom = 1
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_dosage_form(value):
	value = _clean_link_name(value, "Tablet")
	if frappe.db.exists("Dosage Form", value):
		return value
	return _insert_minimal_doc("Dosage Form", {"dosage_form": value})

def _ensure_prescription_dosage(value):
	value = _clean_link_name(value, "Sesuai resep")
	if frappe.db.exists("Prescription Dosage", value):
		return value
	return _insert_minimal_doc("Prescription Dosage", {"dosage": value})

def _default_stock_uom():
	return (
		frappe.db.exists("UOM", "Nos")
		or frappe.db.exists("UOM", "Unit")
		or frappe.db.get_single_value("Stock Settings", "stock_uom")
		or _ensure_uom("Nos")
	)

def _default_item_group():
	return (
		frappe.db.exists("Item Group", "All Item Groups")
		or frappe.db.get_value("Item Group", {}, "name")
	)

def _ensure_item(value):
	item_name = _clean_link_name(value, "Khanza Medication Item")
	if frappe.db.exists("Item", item_name):
		return item_name

	doc = frappe.new_doc("Item")
	doc.item_code = item_name
	doc.item_name = item_name
	doc.item_group = _default_item_group()
	doc.stock_uom = _default_stock_uom()
	if doc.meta.has_field("is_stock_item"):
		doc.is_stock_item = 0
	if doc.meta.has_field("disabled"):
		doc.disabled = 0
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _medication_reference(fhir):
	reference = fhir.get("medicationReference")
	if isinstance(reference, dict):
		return reference
	return _find_reference(fhir, "Medication")

def _medication_display(fhir):
	reference = _medication_reference(fhir)
	if reference.get("display"):
		return reference.get("display")
	return (
		_coding_text(fhir.get("medicationCodeableConcept"))
		or _coding_text(fhir.get("code"))
		or _coding_code(fhir.get("medicationCodeableConcept"))
		or _coding_code(fhir.get("code"))
		or _text(fhir.get("id"))
		or "Khanza Medication"
	)

def _medication_docname_from_reference(fhir):
	reference = _medication_reference(fhir)
	local_id = _reference_id(reference.get("reference"))
	if local_id:
		existing = (
			frappe.db.exists("Medication", {"satusehat_resource_id": local_id})
			or frappe.db.exists("Medication", {"khanza_external_id": local_id})
			or frappe.db.exists("Medication", local_id)
		)
		if existing:
			return existing

	display = _medication_display(fhir)
	if display:
		return frappe.db.exists("Medication", {"generic_name": display})
	return None

def _medication_form_from_text(value):
	value = _text(value).lower()
	if "capsule" in value or "kapsul" in value:
		return "Capsule"
	if "syrup" in value or "sirup" in value:
		return "Syrup"
	if "injection" in value or "inj" in value:
		return "Injection"
	if "ointment" in value or "salep" in value:
		return "Ointment"
	return "Tablet"

def _dosage_text(fhir):
	instruction = _first(fhir.get("dosageInstruction") or fhir.get("dosage") or [])
	if isinstance(instruction, dict):
		if instruction.get("text"):
			return instruction.get("text")
		timing = instruction.get("timing") or {}
		repeat = timing.get("repeat") or {}
		frequency = repeat.get("frequency")
		period = repeat.get("period")
		dose = _first(instruction.get("doseAndRate") or {}).get("doseQuantity") or {}
		dose_text = " ".join([_text(dose.get("value")), _text(dose.get("unit") or dose.get("code"))]).strip()
		if frequency and dose_text:
			return f"{frequency} x {dose_text}"
		if frequency and period:
			return f"{frequency} x per {period} hari"
	return "Sesuai resep"

def _medication_quantity(fhir):
	quantity = ((fhir.get("dispenseRequest") or {}).get("quantity") or {}).get("value")
	if quantity not in (None, ""):
		return quantity
	dose = _first(_first(fhir.get("dosageInstruction") or []).get("doseAndRate") or {}).get("doseQuantity") or {}
	return dose.get("value") or 1

def _apply_medication_request_fields(target, fhir):
	medication_name = _medication_display(fhir)
	medication_doc = _medication_docname_from_reference(fhir)
	dosage_form = _medication_form_from_text(medication_name)
	when = _effective_datetime(fhir)
	quantity = _medication_quantity(fhir)

	_set_if_field(target, "naming_series", "HMR-")
	_set_if_field(target, "title", medication_name)
	_set_if_field(target, "status", _ensure_code_value(fhir.get("status") or "active", "Medication Request Status"))
	_set_if_field(target, "intent", _ensure_code_value(fhir.get("intent") or "order", "Request Intent"))
	_set_if_field(target, "priority", _ensure_code_value(fhir.get("priority") or "routine", "Request Priority"))
	_set_if_field(target, "medication", medication_doc)
	_set_if_field(target, "medication_item", _ensure_item(medication_name))
	_set_if_field(target, "dosage_form", _ensure_dosage_form(dosage_form))
	_set_if_field(target, "dosage", _ensure_prescription_dosage(_dosage_text(fhir)))
	_set_if_field(target, "quantity", quantity)
	_set_if_field(target, "total_dispensable_quantity", quantity)
	_set_if_field(target, "number_of_repeats_allowed", 0)
	_set_if_field(target, "order_description", medication_name)
	_set_if_field(target, "order_date", _date_part(when) or frappe.utils.nowdate())
	_set_if_field(target, "expected_date", _date_part(when) or frappe.utils.nowdate())
	_set_if_field(target, "order_time", _time_part(when) or "00:00:00")

def _apply_medication_child_fields(target, fhir):
	medication_name = _medication_display(fhir)
	_set_if_field(target, "code", _reference_id((_medication_reference(fhir) or {}).get("reference")) or medication_name)
	_set_if_field(target, "code_display", medication_name)
	_set_if_field(target, "status", fhir.get("status") or "unknown")
	_set_if_field(target, "note", _json_dumps(fhir.get("note")) if fhir.get("note") else medication_name)

def _fill_common_target_fields(target, fhir, queue_doc, external_id, khanza_function):
	patient = _ensure_patient(_patient_reference(fhir))
	practitioner = _ensure_practitioner(_practitioner_reference(fhir))
	when = _effective_datetime(fhir)
	code_text = _coding_text(fhir.get("code") or fhir.get("vaccineCode") or fhir.get("medicationCodeableConcept"))
	code = _coding_code(fhir.get("code") or fhir.get("vaccineCode") or fhir.get("medicationCodeableConcept"))
	company = _default_company()

	_set_if_field(target, "patient", patient)
	_set_if_field(target, "subject", patient)
	_set_if_field(target, "patient_name", (_patient_reference(fhir) or {}).get("display"))
	_set_if_field(target, "practitioner", practitioner)
	_set_if_field(target, "healthcare_practitioner", practitioner)
	_set_if_field(target, "practitioner_name", (_practitioner_reference(fhir) or {}).get("display"))
	_set_if_field(target, "company", company)
	_set_if_field(target, "status", fhir.get("status"))
	_set_if_field(target, "title", code_text or external_id)
	_set_if_field(target, "description", code_text)
	_set_if_field(target, "order_description", code_text)
	_set_if_field(target, "note", _json_dumps(fhir.get("note")) if fhir.get("note") else code_text)
	_set_if_field(target, "encounter_comment", code_text)
	_set_if_field(target, "reference_doc", QUEUE_DOCTYPE)
	_set_if_field(target, "reference_name", queue_doc.name)
	_set_if_field(target, "reference_doctype", QUEUE_DOCTYPE)
	_set_if_field(target, "reference_docname", queue_doc.name)
	_set_if_field(target, "ref_doctype", QUEUE_DOCTYPE)
	_set_if_field(target, "docname", queue_doc.name)
	_set_if_field(target, "code", code)
	_set_if_field(target, "code_display", code_text)
	_set_if_field(target, "code_text", code_text)
	_set_if_field(target, "fhir_status", fhir.get("status"))
	_set_if_field(target, "occurred_at", when)
	_set_if_field(target, "authored_on", fhir.get("authoredOn"))
	_set_if_field(target, "encounter_reference", (_encounter_reference(fhir) or {}).get("reference"))

	if when:
		_set_if_field(target, "encounter_date", _date_part(when))
		_set_if_field(target, "encounter_time", _time_part(when))
		_set_if_field(target, "signs_date", _date_part(when))
		_set_if_field(target, "signs_time", _time_part(when))
		_set_if_field(target, "order_date", _date_part(when))
		_set_if_field(target, "order_time", _time_part(when))
		_set_if_field(target, "start_date", _date_part(when))
		_set_if_field(target, "start_time", _time_part(when))
		_set_if_field(target, "posting_date", when)
		_set_if_field(target, "assessment_datetime", when)
		_set_if_field(target, "received_time", when)
		_set_if_field(target, "reference_posting_date", _date_part(when))
		_set_if_field(target, "result_datetime", when)
		_set_if_field(target, "time_of_result", when)

	_append_fhir_audit_fields(target, fhir, queue_doc, external_id, khanza_function)
	return target

def _apply_resource_specific_fields(target, fhir, target_doctype):
	if target_doctype == "Vital Signs":
		code = _coding_code(fhir.get("code")).lower()
		value = _quantity_value(fhir)
		unit = (_quantity_unit(fhir) or "").lower()
		if "8310-5" in code or "temperature" in code:
			target.temperature = value
		elif "8867-4" in code or "heart" in code or "pulse" in code:
			target.pulse = value
		elif "9279-1" in code or "respiratory" in code:
			target.respiratory_rate = value
		elif "8480-6" in code:
			target.bp_systolic = value
		elif "8462-4" in code:
			target.bp_diastolic = value
		elif "8302-2" in code or unit in ("cm", "m"):
			target.height = value / 100 if unit == "cm" and value else value
		elif "29463-7" in code or unit == "kg":
			target.weight = value
		target.vital_signs_note = _coding_text(fhir.get("code"))

	if target_doctype == "Observation":
		template = _ensure_observation_template(fhir)
		_set_if_field(target, "observation_template", template)
		target.observation_category = _observation_category(fhir)
		target.result_data = ""
		target.result_text = _observation_result(fhir)
		target.preferred_display_name = _coding_text(fhir.get("code"))
		target.description = target.description or _coding_text(fhir.get("code"))

	if target_doctype == "Diagnosis":
		target.diagnosis = _coding_text(fhir.get("code")) or _coding_code(fhir.get("code")) or target.khanza_external_id

	if target_doctype == "Medication":
		target.generic_name = _coding_text(fhir.get("code")) or target.khanza_external_id
		target.national_drug_code = _coding_code(fhir.get("code"))
		strength, strength_uom = _medication_strength(fhir)
		target.medication_class = _ensure_medication_class(_medication_form_text(fhir))
		target.strength = strength
		target.strength_uom = _ensure_uom(strength_uom)
		target.disabled = 1 if fhir.get("status") == "inactive" else 0

	if target_doctype == "Medication Request":
		_apply_medication_request_fields(target, fhir)

	if target_doctype in ("Medication Dispense", "Medication Statement"):
		_apply_medication_child_fields(target, fhir)

	if target_doctype == "Service Request":
		template_dt, template_dn = _ensure_service_request_template(fhir)
		_set_if_field(target, "template_dt", template_dt)
		_set_if_field(target, "template_dn", template_dn)
		_set_if_field(target, "source", "Direct")
		_set_if_field(target, "quantity", 1)
		when = _effective_datetime(fhir)
		_set_if_field(target, "occurrence_date", _date_part(when))
		_set_if_field(target, "occurrence_time", _time_part(when))
		_set_if_field(target, "expected_date", _date_part(when))

	if target_doctype == "Clinical Note":
		target.note = target.note or _json_dumps(fhir)

	if target_doctype == "Questionnaire Response":
		target.questionnaire = fhir.get("questionnaire") or target.khanza_external_id
		target.note = target.note or _json_dumps(fhir.get("item") or [])

	if target_doctype == "Patient Assessment":
		template = _ensure_patient_assessment_template()
		_set_if_field(target, "assessment_template", template)
		_set_if_field(target, "assessment_description", _json_dumps(fhir.get("summary") or fhir.get("finding") or fhir))
		if target.meta.has_field("assessment_sheet") and not target.get("assessment_sheet"):
			parameter = _ensure_patient_assessment_parameter("Clinical Impression")
			target.append(
				"assessment_sheet",
				{
					"parameter": parameter,
					"score": "0",
					"comments": _coding_text(fhir.get("code")) or _text(fhir.get("description")),
				},
			)

	return target

def _ensure_service_request_template(fhir):
	template = _ensure_observation_template(fhir)
	return "Observation Template", template

def _ensure_observation_template(fhir):
	name = _coding_text(fhir.get("code")) or _coding_code(fhir.get("code")) or "Khanza Observation"
	name = name[:140]
	if frappe.db.exists("Observation Template", name):
		return name

	doc = frappe.new_doc("Observation Template")
	doc.observation = name
	doc.observation_category = _observation_category(fhir)
	doc.preferred_display_name = name
	doc.description = name
	doc.permitted_data_type = "Text"
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_patient_assessment_parameter(name):
	name = (name or "Clinical Impression")[:140]
	if frappe.db.exists("Patient Assessment Parameter", name):
		return name
	doc = frappe.new_doc("Patient Assessment Parameter")
	doc.assessment_parameter = name
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _ensure_patient_assessment_template():
	name = "Clinical Impression"
	if frappe.db.exists("Patient Assessment Template", name):
		return name

	parameter = _ensure_patient_assessment_parameter(name)
	doc = frappe.new_doc("Patient Assessment Template")
	doc.assessment_name = name
	doc.scale_min = 0
	doc.scale_max = 10
	doc.assessment_description = "Clinical impression imported from FHIR"
	doc.append("parameters", {"assessment_parameter": parameter})
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name

def _observation_category(fhir):
	for category in fhir.get("category") or []:
		code = (_coding_code(category) or "").lower()
		if code == "imaging":
			return "Imaging"
		if code == "laboratory":
			return "Laboratory"
		if code == "vital-signs":
			return "Vital Signs"
	return "Exam"

def _observation_result(fhir):
	for key in ("valueString", "valueCodeableConcept", "valueBoolean", "valueInteger", "valueDateTime"):
		if key in fhir:
			value = fhir.get(key)
			return _coding_text(value) if isinstance(value, dict) else _text(value)
	if fhir.get("valueQuantity"):
		quantity = fhir.get("valueQuantity")
		return f"{quantity.get('value', '')} {quantity.get('unit') or quantity.get('code') or ''}".strip()
	return fhir.get("conclusion") or fhir.get("description") or ""

def _new_target_doc(target_doctype, fhir, queue_doc, external_id, khanza_function):
	existing = frappe.db.exists(target_doctype, {"khanza_external_id": external_id})
	if existing:
		target = frappe.get_doc(target_doctype, existing)
		if int(getattr(target, "docstatus", 0) or 0) == 1:
			target.flags.ignore_validate_update_after_submit = True
		target.set("khanza_fhir_fields", [])
	elif target_doctype == "Diagnosis":
		diagnosis = _coding_text(fhir.get("code")) or _coding_code(fhir.get("code")) or external_id
		existing_diagnosis = frappe.db.exists("Diagnosis", {"diagnosis": diagnosis})
		if existing_diagnosis:
			target = frappe.get_doc("Diagnosis", existing_diagnosis)
			if int(getattr(target, "docstatus", 0) or 0) == 1:
				target.flags.ignore_validate_update_after_submit = True
			if target.meta.has_field("khanza_fhir_fields"):
				target.set("khanza_fhir_fields", [])
		else:
			target = frappe.new_doc(target_doctype)
	elif target_doctype == "Medication":
		existing_medication = None
		if fhir.get("id"):
			existing_medication = frappe.db.exists("Medication", {"satusehat_resource_id": fhir.get("id")})

		if existing_medication:
			target = frappe.get_doc("Medication", existing_medication)
			if int(getattr(target, "docstatus", 0) or 0) == 1:
				target.flags.ignore_validate_update_after_submit = True
			if target.meta.has_field("khanza_fhir_fields"):
				target.set("khanza_fhir_fields", [])
		else:
			target = frappe.new_doc(target_doctype)
	else:
		target = frappe.new_doc(target_doctype)
	target = _fill_common_target_fields(target, fhir, queue_doc, external_id, khanza_function)
	target = _apply_resource_specific_fields(target, fhir, target_doctype)
	target.flags.ignore_mandatory = True
	if int(getattr(target, "docstatus", 0) or 0) == 1:
		target.flags.ignore_validate_update_after_submit = True
	return target

def import_fhir_to_healthcare_doc(queue_doc, fhir, external_id):
	ensure_khanza_custom_fields(sync_existing=False, ensure_submit=False)
	if not frappe.db.exists("DocType", FHIR_FIELD_DOCTYPE):
		frappe.throw(_("Run bench migrate first so Khanza SatuSehat DocTypes are installed"))
	known_resource_id = getattr(queue_doc, "satusehat_resource_id", None)
	if known_resource_id and not fhir.get("id"):
		fhir = dict(fhir)
		fhir["id"] = known_resource_id
	target_doctype = _target_for_fhir(fhir)
	khanza_function = _function_for_fhir(fhir)
	target = _new_target_doc(target_doctype, fhir, queue_doc, external_id, khanza_function)
	target.save(ignore_permissions=True)
	sync_queue_target_docstatus(target)
	return target
