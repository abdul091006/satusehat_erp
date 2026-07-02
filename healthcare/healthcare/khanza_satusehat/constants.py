SYNC_RECORD_DOCTYPE = "Khanza SatuSehat Sync Record"
QUEUE_DOCTYPE = SYNC_RECORD_DOCTYPE
LOG_DOCTYPE = "Khanza SatuSehat Sync Log"
FHIR_FIELD_DOCTYPE = "FHIR Field"
MAX_ATTEMPTS = 10
SEND_BATCH_LIMIT = 50
SEND_TIME_BUDGET_SECONDS = 0
SATUSEHAT_HTTP_TIMEOUT_SECONDS = 15
TOKEN_EXPIRY_SAFETY_SECONDS = 120
IMPORT_STATUS_PENDING = "pending"
IMPORT_STATUS_PROCESSING = "processing"
IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_FAILED = "failed"
IMPORT_STATUS_FAILED_PERMANENT = "failed_permanent"
SYNC_STATUS_WAITING = "waiting"
REVIEW_STATUS_PENDING = "Pending"
REVIEW_STATUS_NEEDS_CORRECTION = "Needs Correction"
REVIEW_STATUS_APPROVED = "Approved"
REVIEW_STATUS_REJECTED = "Rejected"
VALIDATION_STATUS_UNCHECKED = "unchecked"
VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_WARNING = "warning"
VALIDATION_STATUS_ERROR = "error"

TARGET_DOCTYPES = (
	"Patient",
	"Healthcare Practitioner",
	"Patient Encounter",
	"Vital Signs",
	"Diagnosis",
	"Clinical Procedure",
	"Service Request",
	"Specimen",
	"Observation",
	"Diagnostic Report",
	"Medication",
	"Medication Request",
	"Patient Assessment",
	"Clinical Note",
	"Therapy Plan",
	"Immunization",
	"Medication Dispense",
	"Medication Statement",
	"Questionnaire Response",
)

CUSTOM_FIELD_TARGET_DOCTYPES = TARGET_DOCTYPES

RESOURCE_TARGETS = {
	"Encounter": "Patient Encounter",
	"Condition": "Diagnosis",
	"Procedure": "Clinical Procedure",
	"ClinicalImpression": "Patient Assessment",
	"Immunization": "Immunization",
	"Composition": "Clinical Note",
	"Medication": "Medication",
	"MedicationRequest": "Medication Request",
	"MedicationDispense": "Medication Dispense",
	"ServiceRequest": "Service Request",
	"Specimen": "Specimen",
	"DiagnosticReport": "Diagnostic Report",
	"CarePlan": "Therapy Plan",
	"MedicationStatement": "Medication Statement",
	"QuestionnaireResponse": "Questionnaire Response",
	"AllergyIntolerance": "Clinical Note",
}

