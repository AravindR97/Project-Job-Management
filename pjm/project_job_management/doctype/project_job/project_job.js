// Copyright (c) 2025, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Job", {
    _recalculating_costs: false,
    
    async refresh(frm) {
        // Skip cost recalculation if we're already reloading after save
        if (frm._just_saved) {
            delete frm._just_saved;
            return;
        }
        
        if (!frm.is_new() && frm.doc.project) {

            // ---- Fetch Timesheets ----
            const timesheets = await frappe.db.get_list("Timesheet", {
                filters: {
                    "parent_project": frm.doc.project,
                    "docstatus": 1
                },
                fields: ["name", "start_date", "total_hours", "employee"]
            });

            if (timesheets && timesheets.length > 0) {
                frm.clear_table("job_timesheets");

                let total_hours = 0.0;
                let total_working_cost = 0.0;

                timesheets.forEach(ts => {
                    let row = frm.add_child("job_timesheets");
                    row.timesheet = ts.name;
                    row.date = ts.start_date;
                    row.working_hours = ts.total_hours;
                    row.employee = ts.employee;

                    // find cost per hour from assigned_employees table
                    let emp_row = frm.doc.assigned_employees?.find(e => e.employee === ts.employee);
                    row.hourly_cost = emp_row ? flt(emp_row.cost_per_hour) : 0.0;
                    row.working_cost = flt(row.hourly_cost) * flt(row.working_hours);

                    total_hours += flt(ts.total_hours);
                    total_working_cost += row.working_cost;
                });

                frm.doc.working_hours = total_hours;
                frm.doc.working_cost = total_working_cost;

                const billed = await frappe.db.get_value("Project", frm.doc.project, "total_billed_amount");
                if (billed && billed.message) {
                    frm.doc.billed_invoice_amount = billed.message.total_billed_amount;
                }

                frm.refresh_fields(["job_timesheets", "working_hours", "working_cost", "billed_invoice_amount"]);
                frm.doc.__unsaved = 0;
                frm.page.clear_indicator();
            }

            // Task costs are automatically calculated in before_save hook and saved to database
            // After save, the document is reloaded to display the updated costs
            // On refresh, costs are already loaded from the database, no action needed
        }
    },
    
    after_save(frm) {
        // After save, mark that we just saved and reload to show updated costs
        // This ensures costs calculated in before_save are displayed without triggering unsaved state
        frm._just_saved = true;
        setTimeout(() => {
            frm.reload_doc();
        }, 100);
    }
});
