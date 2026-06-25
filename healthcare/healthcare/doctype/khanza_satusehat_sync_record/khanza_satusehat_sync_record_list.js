frappe.listview_settings["Khanza SatuSehat Sync Record"] = {
	onload(listview) {
		const escape_html = (value) =>
			String(value || "").replace(/[&<>"']/g, (character) => ({
				"&": "&amp;",
				"<": "&lt;",
				">": "&gt;",
				'"': "&quot;",
				"'": "&#39;",
			}[character]));

		const render_queue_result = (summary) => {
			if (!summary.queued) {
				return "";
			}
			return `<br><br>${__("Enqueued for background processing")}: ${escape_html(summary.queued_count || 0)}`;
		};

		const render_target_status = (summary) => {
			const statuses = summary.by_target_docstatus || {};
			if (!Object.keys(statuses).length) {
				return "";
			}
			return `<br>${__("ERPNext document status")}: ${escape_html(JSON.stringify(statuses))}`;
		};

		const render_queue_errors = (summary) => {
			const items = (summary.items || [])
				.filter((item) => item.error_message)
				.slice(0, 10);
			if (!items.length) {
				return "";
			}
			const details = items
				.map((item) => `${escape_html(item.name)} (${escape_html(item.resource_type)}): ${escape_html(item.error_message)}`)
				.join("<br>");
			return `<br><br>${__("Sync messages")}:<br>${details}`;
		};

		listview.page.add_menu_item(__("Approve Pending & Enqueue Send"), () => {
			frappe.confirm(
				__("Approve and enqueue up to 200 pending item(s) for SatuSehat background processing?"),
				() => {
					frappe.call({
						method: "healthcare.healthcare.khanza_main.approve_pending_and_process",
						args: { limit: 200 },
						freeze: true,
						freeze_message: __("Approving and enqueueing SatuSehat jobs..."),
						callback(r) {
							const data = r.message || {};
							const summary = data.send_summary || {};
							const skipped = data.skipped || [];
							let message = __("Approved/enqueued: {0}. Skipped: {1}. Sync status: {2}", [
								data.count || 0,
								data.skipped_count || 0,
								JSON.stringify(summary.by_sync_status || {}),
							]);
							message += render_target_status(summary);
							if (summary.send_error) {
								message += `<br><br>${__("Send error")}: ${escape_html(summary.send_error)}`;
							}
							message += render_queue_result(summary);
							message += render_queue_errors(summary);
							if (skipped.length) {
								const details = skipped
									.slice(0, 10)
									.map((item) => {
										const reason = item.error_message || item.import_status || item.reason;
										return `${escape_html(item.queue_name)}: ${escape_html(reason || "")}`;
									})
									.join("<br>");
								message += `<br><br>${details}`;
								if (skipped.length > 10) {
									message += `<br>${__("and {0} more...", [skipped.length - 10])}`;
								}
							}
							frappe.msgprint(message);
							listview.refresh();
						},
					});
				}
			);
		});

		listview.page.add_menu_item(__("Enqueue Approved Pending Send"), () => {
			frappe.call({
				method: "healthcare.healthcare.khanza_main.process_approved",
				args: { limit: 200 },
				freeze: true,
				freeze_message: __("Enqueueing approved items for SatuSehat..."),
				callback(r) {
					const data = r.message || {};
					const summary = data.send_summary || {};
					frappe.msgprint(__("Enqueued {0} approved pending item(s). Sync status: {1}", [
						data.count || 0,
						JSON.stringify(summary.by_sync_status || {}),
					]) + render_target_status(summary) + (summary.send_error ? `<br><br>${__("Send error")}: ${escape_html(summary.send_error)}` : "") + render_queue_result(summary) + render_queue_errors(summary));
					listview.refresh();
				},
			});
		});

		listview.page.add_actions_menu_item(__("Approve & Enqueue Selected"), () => {
			const items = listview.get_checked_items();
			const queue_names = items.map((item) => item.name);

			if (!queue_names.length) {
				frappe.msgprint(__("Select at least one sync record."));
				return;
			}

			frappe.confirm(
				__("Approve and enqueue {0} selected item(s) for SatuSehat?", [queue_names.length]),
				() => {
					frappe.call({
						method: "healthcare.healthcare.khanza_main.approve_many",
						args: { queue_names },
						freeze: true,
						freeze_message: __("Approving and enqueueing SatuSehat jobs..."),
						callback(r) {
							const data = r.message || {};
							const summary = data.send_summary || {};
							const skipped = data.skipped || [];
							let message = __("Approved: {0}. Skipped: {1}. Sync status: {2}", [
								data.approved_count || 0,
								data.skipped_count || 0,
								JSON.stringify(summary.by_sync_status || {}),
							]);
							message += render_target_status(summary);
							if (summary.send_error) {
								message += `<br><br>${__("Send error")}: ${escape_html(summary.send_error)}`;
							}
							message += render_queue_result(summary);
							message += render_queue_errors(summary);
							if (skipped.length) {
								const details = skipped
									.slice(0, 10)
									.map((item) => {
										const reason = item.error_message || item.import_status || item.reason;
										return `${escape_html(item.queue_name)}: ${escape_html(reason || "")}`;
									})
									.join("<br>");
								message += `<br><br>${details}`;
								if (skipped.length > 10) {
									message += `<br>${__("and {0} more...", [skipped.length - 10])}`;
								}
							}
							frappe.msgprint(message);
							listview.refresh();
						},
					});
				}
			);
		});
	},
};
