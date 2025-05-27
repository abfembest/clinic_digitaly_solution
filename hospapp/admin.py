from django.contrib import admin
from .models import (
    Admission, Appointment, Bed, CarePlan, Consultation, Department,
    EmergencyAlert, HandoverLog, LabResultFile, LabTest, LabTestType,
    MedicalRecord, NursingNote, Patient, Prescription, Profile,
    Referral, Shift, Attendance, ShiftAssignment, TestRequest, TestSelection, Vitals, Ward, LabTestField,TestCategory,
    TestSubcategory
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
admin.site.register(LabTestType)
admin.site.register(MedicalRecord)
admin.site.register(NursingNote)
admin.site.register(Patient)
admin.site.register(Prescription)
admin.site.register(Profile)
admin.site.register(Referral)
admin.site.register(Shift)
admin.site.register(ShiftAssignment)
admin.site.register(Attendance)
admin.site.register(TestRequest)
admin.site.register(Vitals)
admin.site.register(Ward)
admin.site.register(LabTestField)
admin.site.register(TestCategory)
admin.site.register(TestSubcategory)
admin.site.register(TestSelection)