frappe.ui.form.on("Khanza SatuSehat Sync Record", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) {
			return;
		}

		if (frm.doc.target_doctype && frm.doc.target_docname) {
			frm.add_custom_button(__("Open Target Document"), () => {
				frappe.set_route("Form", frm.doc.target_doctype, frm.doc.target_docname);
			});
		}

		const target_is_submitted = frm.doc.target_docstatus === "Submitted";

		if (frm.doc.import_status === "imported" && frm.doc.approval_status !== "Approved" && target_is_submitted) {
			frm.add_custom_button(__("Approve & Enqueue Send"), () => {
				frappe.call({
					method: "healthcare.healthcare.khanza_main.approve",
					args: { queue_name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}

		if (frm.doc.import_status === "imported" && frm.doc.approval_status === "Approved" && target_is_submitted && ["pending", "waiting", "failed"].includes(frm.doc.sync_status)) {
			frm.add_custom_button(__("Enqueue Send"), () => {
				frappe.call({
					method: "healthcare.healthcare.khanza_main.retry",
					args: { queue_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Enqueueing SatuSehat job..."),
					callback: () => frm.reload_doc(),
				});
			});
		}

		if (frm.doc.import_status === "imported" && frm.doc.approval_status !== "Rejected" && frm.doc.sync_status !== "sent") {
			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Reason"),
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "healthcare.healthcare.khanza_main.reject",
							args: { queue_name: frm.doc.name, reason: values.reason },
							callback: () => frm.reload_doc(),
						});
					},
					__("Reject SatuSehat Sync Record")
				);
			});
		}

		if (
			["failed", "failed_permanent"].includes(frm.doc.import_status) ||
			(frm.doc.approval_status === "Approved" && ["failed", "failed_permanent"].includes(frm.doc.sync_status))
		) {
			frm.add_custom_button(__("Retry"), () => {
				frappe.call({
					method: "healthcare.healthcare.khanza_main.retry",
					args: { queue_name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
