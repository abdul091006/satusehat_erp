frappe.listview_settings["Khanza SatuSehat Queue"] = {
	onload(listview) {
		listview.page.add_actions_menu_item(__("Approve & Send Selected"), () => {
			const items = listview.get_checked_items();
			const queue_names = items.map((item) => item.name);

			if (!queue_names.length) {
				frappe.msgprint(__("Select at least one queue item."));
				return;
			}

			frappe.confirm(
				__("Approve and send {0} selected queue item(s) to SatuSehat?", [queue_names.length]),
				() => {
					frappe.call({
						method: "healthcare.healthcare.khanza_main.approve_many",
						args: { queue_names },
						freeze: true,
						freeze_message: __("Queueing SatuSehat send jobs..."),
						callback(r) {
							const data = r.message || {};
							frappe.msgprint(
								__("Approved: {0}. Skipped: {1}.", [
									data.approved_count || 0,
									data.skipped_count || 0,
								])
							);
							listview.refresh();
						},
					});
				}
			);
		});
	},
};
