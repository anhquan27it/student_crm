frappe.ui.form.on('Class Session', {
    refresh(frm) {
        frm.set_intro(__('Only finalized attendance is counted. Each course has 20 slots; absence above 20% (5 slots) triggers a warning. Only Absent counts as absence; Late counts as attended.'));
        if (!frm.is_new() && !frm.doc.attendance_finalized && !['Cancelled', 'Postponed'].includes(frm.doc.status)) {
            frm.add_custom_button(__('Finalize Attendance'), async () => {
                await frm.set_value('status', 'Completed');
                await frm.set_value('attendance_finalized', 1);
                await frm.save();
            });
        }
    }
});
