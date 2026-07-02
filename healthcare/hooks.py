from . import __version__ as app_version  # noqa

app_name = "healthcare"
app_title = "Marley Health"
app_publisher = "earthians Health Informatics Pvt. Ltd."
app_description = "Modern, Open Source HIS built on Frappe and ERPNext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@earthianslive.com"
app_license = "GNU GPL V3"
required_apps = ["frappe/erpnext"]

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "like", "%-khanza_%"]],
	},
	{
		"dt": "Property Setter",
		"filters": [["doc_type", "in", ["Khanza SatuSehat Sync Record"]]],
	},
	{
		"dt": "Clinical Procedure Template",
		"filters": [["name", "=", "Imported Khanza Procedure"]],
	},
	{
		"dt": "Therapy Type",
		"filters": [["name", "=", "Imported Khanza Therapy"]],
	},
	{
		"dt": "Item",
		"filters": [["name", "in", ["Imported Khanza Procedure"]]],
	},
	{
		"dt": "Customer",
		"filters": [["name", "in", ["ARDIANTO PUTRA"]]],
	},
	{
		"dt": "Khanza SatuSehat Sync Record",
		"filters": [["source_system", "=", "Khanza"]],
	},
	{
		"dt": "Patient",
		"filters": [["khanza_external_id", "is", "set"]],
	},
	{
		"dt": "Healthcare Practitioner",
		"filters": [["khanza_external_id", "is", "set"]],
	},
	{
		"dt": "Patient Encounter",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Vital Signs",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Diagnosis",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Clinical Procedure",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Service Request",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Specimen",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Observation",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Diagnostic Report",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Medication",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Medication Request",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Patient Assessment",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Clinical Note",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Therapy Plan",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Immunization",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Medication Dispense",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Medication Statement",
		"filters": [["khanza_queue", "is", "set"]],
	},
	{
		"dt": "Questionnaire Response",
		"filters": [["khanza_queue", "is", "set"]],
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/healthcare/css/healthcare.css"
app_include_js = "healthcare.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/healthcare/css/healthcare.css"
# web_include_js = "/assets/healthcare/js/healthcare.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "healthcare/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Sales Invoice": "public/js/sales_invoice.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"healthcare.healthcare.doctype.diagnostic_report.diagnostic_report.diagnostic_report_print",
		"healthcare.healthcare.utils.generate_barcodes",
		"healthcare.healthcare.doctype.observation.observation.get_observations_for_medical_record",
	]
}

# Installation
# ------------

# before_install = "healthcare.install.before_install"
after_install = "healthcare.setup.setup_healthcare"
after_migrate = "healthcare.healthcare.khanza_main.ensure_khanza_custom_fields"

# Uninstallation
# ------------

before_uninstall = "healthcare.uninstall.before_uninstall"
after_uninstall = "healthcare.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "healthcare.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Sales Invoice": "healthcare.healthcare.custom_doctype.sales_invoice.HealthcareSalesInvoice",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"*": {
		"on_submit": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.create_medical_record",
		"on_cancel": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.delete_medical_record",
		"on_update_after_submit": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.update_medical_record",
	},
	"Sales Invoice": {
		"on_submit": "healthcare.healthcare.utils.manage_invoice_submit_cancel",
		"on_cancel": "healthcare.healthcare.utils.manage_invoice_submit_cancel",
		"validate": "healthcare.healthcare.utils.manage_invoice_validate",
	},
	"Company": {
		"after_insert": "healthcare.healthcare.utils.create_healthcare_service_unit_tree_root",
		"on_trash": "healthcare.healthcare.utils.company_on_trash",
	},
	"Patient": {
		"after_insert": "healthcare.regional.india.abdm.utils.set_consent_attachment_details"
	},
	"Patient Encounter": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Vital Signs": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Diagnosis": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Clinical Procedure": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Service Request": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Specimen": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Observation": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Diagnostic Report": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Medication": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Medication Request": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Patient Assessment": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Clinical Note": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Therapy Plan": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Immunization": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Medication Dispense": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Medication Statement": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
	"Questionnaire Response": {
		"on_update": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_cancel": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
		"on_update_after_submit": "healthcare.healthcare.khanza_satusehat.document_events.sync_queue_target_docstatus",
	},
}

scheduler_events = {
	"all": [
		"healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_appointment_reminder",
		"healthcare.healthcare.khanza_main.process_queue",
		"healthcare.healthcare.khanza_main.send_approved_queue",
	],
	"daily": [
		"healthcare.healthcare.doctype.patient_appointment.patient_appointment.update_appointment_status",
		"healthcare.healthcare.doctype.fee_validity.fee_validity.update_validity_status",
	],
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"healthcare.tasks.all"
# 	],
# 	"daily": [
# 		"healthcare.tasks.daily"
# 	],
# 	"hourly": [
# 		"healthcare.tasks.hourly"
# 	],
# 	"weekly": [
# 		"healthcare.tasks.weekly"
# 	],
# 	"monthly": [
# 		"healthcare.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "healthcare.healthcare.utils.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "healthcare.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "healthcare.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
auto_cancel_exempted_doctypes = [
	"Inpatient Medication Entry",
]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"healthcare.auth.validate"
# ]

global_search_doctypes = {
	"Healthcare": [
		{"doctype": "Patient", "index": 1},
		{"doctype": "Medical Department", "index": 2},
		{"doctype": "Vital Signs", "index": 3},
		{"doctype": "Healthcare Practitioner", "index": 4},
		{"doctype": "Patient Appointment", "index": 5},
		{"doctype": "Healthcare Service Unit", "index": 6},
		{"doctype": "Patient Encounter", "index": 7},
		{"doctype": "Antibiotic", "index": 8},
		{"doctype": "Diagnosis", "index": 9},
		{"doctype": "Lab Test", "index": 10},
		{"doctype": "Clinical Procedure", "index": 11},
		{"doctype": "Inpatient Record", "index": 12},
		{"doctype": "Sample Collection", "index": 13},
		{"doctype": "Patient Medical Record", "index": 14},
		{"doctype": "Appointment Type", "index": 15},
		{"doctype": "Fee Validity", "index": 16},
		{"doctype": "Practitioner Schedule", "index": 17},
		{"doctype": "Dosage Form", "index": 18},
		{"doctype": "Lab Test Sample", "index": 19},
		{"doctype": "Prescription Duration", "index": 20},
		{"doctype": "Prescription Dosage", "index": 21},
		{"doctype": "Sensitivity", "index": 22},
		{"doctype": "Complaint", "index": 23},
		{"doctype": "Medical Code", "index": 24},
	]
}

domains = {
	"Healthcare": "healthcare.setup",
}

# nosemgrep
standard_portal_menu_items = [
	{
		"title": "Personal Details",
		"route": "/personal-details",
		"reference_doctype": "Patient",
		"role": "Patient",
	},
	{
		"title": "Lab Test",
		"route": "/lab-test",
		"reference_doctype": "Lab Test",
		"role": "Patient",
	},
	{
		"title": "Prescription",
		"route": "/prescription",
		"reference_doctype": "Patient Encounter",
		"role": "Patient",
	},
	{
		"title": "Patient Appointment",
		"route": "/patient-appointments",
		"reference_doctype": "Patient Appointment",
		"role": "Patient",
	},
]

has_website_permission = {
	"Lab Test": "healthcare.healthcare.web_form.lab_test.lab_test.has_website_permission",
	"Patient Encounter": "healthcare.healthcare.web_form.prescription.prescription.has_website_permission",
	"Patient Appointment": "healthcare.healthcare.web_form.patient_appointments.patient_appointments.has_website_permission",
	"Patient": "healthcare.healthcare.web_form.personal_details.personal_details.has_website_permission",
}

standard_queries = {
	"Healthcare Practitioner": "healthcare.healthcare.doctype.healthcare_practitioner.healthcare_practitioner.get_practitioner_list"
}

treeviews = [
	"Healthcare Service Unit",
]

company_data_to_be_ignored = [
	"Healthcare Service Unit",
]
