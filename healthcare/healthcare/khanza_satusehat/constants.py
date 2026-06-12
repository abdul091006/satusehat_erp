QUEUE_DOCTYPE = "Khanza SatuSehat Queue"
LOG_DOCTYPE = "Khanza SatuSehat Sync Log"
FHIR_FIELD_DOCTYPE = "FHIR Field"
MAX_ATTEMPTS = 10
TOKEN_EXPIRY_SAFETY_SECONDS = 120
IMPORT_STATUS_PENDING = "pending"
IMPORT_STATUS_PROCESSING = "processing"
IMPORT_STATUS_IMPORTED = "imported"
IMPORT_STATUS_FAILED = "failed"
IMPORT_STATUS_FAILED_PERMANENT = "failed_permanent"

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
	"Allergy",
	"Immunization",
	"Medication Dispense",
	"Medication Statement",
	"Questionnaire Response",
)

CUSTOM_FIELD_TARGET_DOCTYPES = (
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
	"Allergy",
)

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
	"AllergyIntolerance": "Allergy",
}
