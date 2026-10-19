frappe.ui.form.on('Student Course Enrollment', {
    refresh(frm) {
        frm.set_intro(__('Standing and remaining absences are calculated from CRM Settings and finalized attendance. Barred requires absence strictly above the barred percentage.'), ['Critical','Barred'].includes(frm.doc.attendance_standing) ? 'red' : 'blue');
    }
});
