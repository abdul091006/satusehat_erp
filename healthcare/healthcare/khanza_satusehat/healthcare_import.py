import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from .constants import (
    CUSTOM_FIELD_TARGET_DOCTYPES,
    FHIR_FIELD_DOCTYPE,
    QUEUE_DOCTYPE,
    RESOURCE_TARGETS,
)
from .utils import _as_dict, _json_dumps


def ensure_khanza_custom_fields():
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
			"label": "Source Queue",
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
	create_custom_fields(
		{
			doctype: common_fields
			for doctype in CUSTOM_FIELD_TARGET_DOCTYPES
			if frappe.db.exists("DocType", doctype)
		}
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
				return "Vital Signs"
		return "Observation"
	return RESOURCE_TARGETS.get(resource_type, "Clinical Note")

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
	if field.fieldtype == "Link" and field.options and not frappe.db.exists(field.options, value):
		return
	if field.fieldtype == "Select" and field.options:
		options = [option for option in field.options.split("\n") if option]
		if options and value not in options:
			return
	doc.set(fieldname, value)

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
		target.observation_category = _observation_category(fhir)
		target.result_data = _observation_result(fhir)
		target.preferred_display_name = _coding_text(fhir.get("code"))
		target.description = target.description or _coding_text(fhir.get("code"))

	if target_doctype == "Diagnosis":
		target.diagnosis = _coding_text(fhir.get("code")) or _coding_code(fhir.get("code")) or target.khanza_external_id

	if target_doctype == "Medication":
		target.generic_name = _coding_text(fhir.get("code")) or target.khanza_external_id
		target.national_drug_code = _coding_code(fhir.get("code"))

	if target_doctype == "Clinical Note":
		target.note = target.note or _json_dumps(fhir)

	if target_doctype == "Questionnaire Response":
		target.questionnaire = fhir.get("questionnaire") or target.khanza_external_id
		target.note = target.note or _json_dumps(fhir.get("item") or [])

	return target

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
		target.set("khanza_fhir_fields", [])
	else:
		target = frappe.new_doc(target_doctype)
	target = _fill_common_target_fields(target, fhir, queue_doc, external_id, khanza_function)
	target = _apply_resource_specific_fields(target, fhir, target_doctype)
	target.flags.ignore_mandatory = True
	return target

def import_fhir_to_healthcare_doc(queue_doc, fhir, external_id):
	ensure_khanza_custom_fields()
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
	return target
