// Copyright (c) 2025, Enfono Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Job", {
    refresh(frm) {
        if(!frm.is_new() && frm.doc.project){
            frappe.db.get_list("Timesheet", {
                filters: {
                    "parent_project": frm.doc.project,
                    "docstatus": 1
                },
                fields: ['name', 'start_date', 'total_hours', 'owner']
            }).then(r => {
                if(r && r.length > 0) {
                    frm.clear_table('job_timesheets');
                    
                    let total_hours = 0 | flt;
                    r.forEach(timesheet => {
                        let row = frm.add_child('job_timesheets');
                        row.timesheet = timesheet.name;
                        row.date = timesheet.start_date;
                        row.working_hours = timesheet.total_hours;
                        row.working_cost = timesheet.total_hours * frm.doc.unit_cost;
                        row.created_by = timesheet.owner;
                        total_hours += timesheet.total_hours;
                    });
                    frm.doc.working_hours = total_hours;
                    frm.doc.working_cost = total_hours * frm.doc.unit_cost;

                    frappe.db.get_value("Project", frm.doc.project, "total_billed_amount")
                    .then(r=>{
                        frm.doc.billed_invoice_amount = r.message.total_billed_amount;

                        frm.refresh_fields(['job_timesheets', 'working_hours', 'working_cost', 'billed_invoice_amount']);
                        frm.doc.__unsaved = 0;
                        frm.page.clear_indicator();
                    });
                }
            });
        }
    }
});
