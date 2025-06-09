from django.contrib import admin
from .models import (
    Admission, Appointment, Bed, CarePlan, Consultation, Department,
    EmergencyAlert, HandoverLog, LabResultFile, LabTest,
    MedicalRecord, NursingNote, Patient, Prescription, Staff,
    Referral, Shift, Attendance, ShiftAssignment, Vitals, Ward,TestCategory,
    TestSubcategory, StaffTransition, Payment, PatientBill, ServiceType, ExpenseCategory, Expense, Budget, PaymentUpload,DoctorComments
)

admin.site.register(Admission)
admin.site.register(Appointment)
admin.site.register(Bed)
admin.site.register(CarePlan)
admin.site.register(Consultation)
admin.site.register(Department)
admin.site.register(EmergencyAlert)
admin.site.register(HandoverLog)
admin.site.register(LabResultFile)
admin.site.register(LabTest)
admin.site.register(MedicalRecord)
admin.site.register(NursingNote)
admin.site.register(Patient)
admin.site.register(Prescription)
admin.site.register(Staff)
admin.site.register(Referral)
admin.site.register(Shift)
admin.site.register(ShiftAssignment)
admin.site.register(Attendance)
admin.site.register(Vitals)
admin.site.register(Ward)
admin.site.register(TestCategory)
admin.site.register(TestSubcategory)
admin.site.register(StaffTransition)
admin.site.register(Payment)
admin.site.register(PatientBill)
admin.site.register(ServiceType)
admin.site.register(ExpenseCategory)
admin.site.register(Expense)
admin.site.register(Budget)
admin.site.register(PaymentUpload)
admin.site.register(DoctorComments)