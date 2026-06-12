frappe.ui.form.on("Khanza SatuSehat Queue", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) {
			return;
		}

		if (frm.doc.import_status === "imported" && frm.doc.approval_status !== "Approved") {
			frm.add_custom_button(__("Approve & Send"), () => {
				frappe.call({
					method: "healthcare.healthcare.khanza_main.approve",
					args: { queue_name: frm.doc.name },
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
					__("Reject SatuSehat Queue Item")
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
