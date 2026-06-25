import json
import time
from urllib.parse import quote, urlencode

import frappe
import requests
from frappe import _

from .constants import SATUSEHAT_HTTP_TIMEOUT_SECONDS, TOKEN_EXPIRY_SAFETY_SECONDS

_cached_satusehat_token = None
_cached_satusehat_token_expired_at = 0


def _satusehat_base_url():
	base_url = (
		frappe.conf.get("satusehat_fhir_base_url")
		or frappe.conf.get("satusehat_base_url")
		or frappe.conf.get("url_fhir_satusehat")
	)
	if not base_url:
		frappe.throw(_("satusehat_fhir_base_url is not configured in site_config.json"))
	return base_url.rstrip("/")

def _satusehat_auth_url():
	auth_url = (
		frappe.conf.get("satusehat_auth_url")
		or frappe.conf.get("url_auth_satusehat")
		or frappe.conf.get("urlauth_satusehat")
	)
	if not auth_url:
		frappe.throw(_("satusehat_auth_url is not configured in site_config.json"))
	return auth_url.rstrip("/")

def _satusehat_credentials():
	client_id = (
		frappe.conf.get("satusehat_client_id")
		or frappe.conf.get("client_id_satusehat")
		or frappe.conf.get("clientidsatusehat")
	)
	client_secret = (
		frappe.conf.get("satusehat_client_secret")
		or frappe.conf.get("secret_key_satusehat")
		or frappe.conf.get("secretkeysatusehat")
	)

	if not client_id or not client_secret:
		frappe.throw(_("satusehat_client_id and satusehat_client_secret are required"))

	return client_id, client_secret

def _get_satusehat_token():
	global _cached_satusehat_token, _cached_satusehat_token_expired_at

	now = int(time.time())
	if (
		_cached_satusehat_token
		and _cached_satusehat_token_expired_at > now + TOKEN_EXPIRY_SAFETY_SECONDS
	):
		return _cached_satusehat_token

	client_id, client_secret = _satusehat_credentials()
	response = requests.post(
		f"{_satusehat_auth_url()}/accesstoken?grant_type=client_credentials",
		data={
			"client_id": client_id,
			"client_secret": client_secret,
		},
		headers={
			"Content-Type": "application/x-www-form-urlencoded",
			"Accept": "application/json",
		},
		timeout=SATUSEHAT_HTTP_TIMEOUT_SECONDS,
	)
	response_text = response.text or ""
	if not response.ok:
		raise frappe.ValidationError(f"SatuSehat OAuth HTTP {response.status_code}: {response_text}")

	token_response = response.json()
	token = token_response.get("access_token")
	if not token:
		raise frappe.ValidationError(f"SatuSehat OAuth response does not contain access_token: {response_text}")

	expires_in = int(token_response.get("expires_in") or 3000)
	_cached_satusehat_token = token
	_cached_satusehat_token_expired_at = now + expires_in
	return token

def _satusehat_headers():
	authorization = frappe.conf.get("satusehat_authorization_header")
	if not authorization:
		token = frappe.conf.get("satusehat_bearer_token")
		if token:
			authorization = f"Bearer {token}"
	if not authorization:
		authorization = f"Bearer {_get_satusehat_token()}"
	return {
		"Authorization": authorization,
		"Content-Type": "application/fhir+json",
		"Accept": "application/fhir+json, application/json",
	}

def _endpoint_for(doc, fhir):
	if doc.method == "PUT" and fhir.get("id"):
		path = f"/{doc.resource_type}/{fhir.get('id')}"
	elif doc.method == "POST" and doc.endpoint_path:
		path = doc.endpoint_path
	else:
		path = f"/{doc.resource_type}"
	return f"{_satusehat_base_url()}/{path.lstrip('/')}"

def _identifier_search_url(resource_type, fhir):
	identifier = fhir.get("identifier")
	if isinstance(identifier, list) and identifier:
		identifier = identifier[0]
	if not isinstance(identifier, dict):
		return None

	system = identifier.get("system")
	value = identifier.get("value")
	if not system or not value:
		return None

	identifier_value = quote(f"{system}|{value}", safe="")
	return f"{_satusehat_base_url()}/{resource_type}?identifier={identifier_value}"

def _reference_search_value(value):
	if isinstance(value, dict):
		reference = value.get("reference")
	else:
		reference = value
	if isinstance(reference, str) and "/" in reference:
		return reference
	return None

def _coding_search_value(codeable):
	if not isinstance(codeable, dict):
		return None
	coding = codeable.get("coding") or []
	if not coding:
		return None
	first = coding[0] or {}
	system = first.get("system")
	code = first.get("code")
	if system and code:
		return f"{system}|{code}"
	return code

def _business_search_url(resource_type, fhir):
	params = {}

	if resource_type in (
		"Observation",
		"Condition",
		"Procedure",
		"DiagnosticReport",
		"ServiceRequest",
		"MedicationRequest",
		"MedicationDispense",
		"MedicationStatement",
		"ClinicalImpression",
		"QuestionnaireResponse",
		"AllergyIntolerance",
		"Immunization",
		"CarePlan",
		"Composition",
		"Medication",
	):
		subject = _reference_search_value(fhir.get("subject") or fhir.get("patient"))
		encounter = _reference_search_value(fhir.get("encounter"))
		code = _coding_search_value(
			fhir.get("code")
			or fhir.get("vaccineCode")
			or fhir.get("medicationCodeableConcept")
		)
		if subject:
			params["subject"] = subject
		if encounter:
			params["encounter"] = encounter
		if code:
			params["code"] = code

	if not params:
		return None

	return f"{_satusehat_base_url()}/{resource_type}?{urlencode(params)}"

def _find_existing_satusehat_resource(resource_type, fhir):
	search_urls = [
		url for url in (
			_identifier_search_url(resource_type, fhir),
			_business_search_url(resource_type, fhir),
		)
		if url
	]
	if not search_urls:
		return None

	last_error = None
	successful_lookup = False
	for search_url in search_urls:
		found = _find_existing_satusehat_resource_at_url(resource_type, search_url)
		if isinstance(found, Exception):
			last_error = found
			continue
		successful_lookup = True
		if found:
			return found

	if last_error and not successful_lookup:
		if "Invalid query" in str(last_error):
			return None
		raise last_error
	return None

def _find_existing_satusehat_resource_at_url(resource_type, search_url):
	if not search_url:
		return None

	response = requests.get(
		search_url,
		headers=_satusehat_headers(),
		timeout=SATUSEHAT_HTTP_TIMEOUT_SECONDS,
	)
	response_text = response.text or ""
	if not response.ok:
		if response.status_code == 400 and "Invalid query" in response_text:
			return frappe.ValidationError(
				f"Preflight duplicate check HTTP {response.status_code}: {response_text}"
			)
		raise frappe.ValidationError(f"Preflight duplicate check HTTP {response.status_code}: {response_text}")

	try:
		bundle = response.json()
	except Exception:
		return None

	if int(bundle.get("total") or 0) <= 0:
		return None

	for entry in bundle.get("entry") or []:
		resource = entry.get("resource") or {}
		if resource.get("resourceType") == resource_type and resource.get("id"):
			return resource

	return None

def _resource_url(resource_type, resource_id):
	return f"{_satusehat_base_url()}/{resource_type}/{resource_id}"

def _response_resource_id(response_text):
	try:
		payload = json.loads(response_text or "{}")
	except Exception:
		return None

	if isinstance(payload, dict):
		return payload.get("id")
	return None

def _is_duplicate_response(response_text):
	try:
		payload = json.loads(response_text or "{}")
	except Exception:
		return "Found duplicate" in (response_text or "")

	issues = []
	if isinstance(payload, list):
		issues = payload
	elif isinstance(payload, dict):
		issues = (payload.get("issue") or payload.get("details") or [])

	for issue in issues:
		message = ""
		if isinstance(issue, dict):
			message = (
				issue.get("message")
				or (issue.get("details") or {}).get("text")
				or issue.get("diagnostics")
				or ""
			)
		if "Found duplicate" in message:
			return True

	return False

def _normalize_coding_system(system):
	if not isinstance(system, str):
		return system

	system = system.strip()
	replacements = {
		"https://loinc.org": "http://loinc.org",
		"http://loinc.org/": "http://loinc.org",
		# "http://snomed.info/sct": "https://snomed.info/sct",
		# "http://snomed.info/sct/": "https://snomed.info/sct",
		# "https://snomed.info/sct/": "https://snomed.info/sct",
		"https://terminology.hl7.org/CodeSystem/v2-0074": "http://terminology.hl7.org/CodeSystem/v2-0074",
		"https://terminology.hl7.org/CodeSystem/v3-ActCode": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
	}
	return replacements.get(system, system)

def _normalize_fhir_for_satusehat(value):
	if isinstance(value, dict):
		for key, child in list(value.items()):
			if key == "system" and isinstance(child, str):
				value[key] = _normalize_coding_system(child)
			else:
				_normalize_fhir_for_satusehat(child)
	elif isinstance(value, list):
		for child in value:
			_normalize_fhir_for_satusehat(child)
	return value
