import json
import pandas as pd
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from datetime import datetime, date
from io import BytesIO

# Import your models (adjust the import path as needed)
from .models import (
    Patient, PatientBill, Payment, ServiceType, 
    ExpenseCategory, Expense, Budget, PaymentUpload
)
from .models import Patient  # Adjust import path as needed


@login_required(login_url='home')
def payment_tracker_view(request):
    """Main payment tracker view handling all submission types"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'bulk_payment':
            return handle_traditional_bulk_payment(request)
        elif action == 'smart_bulk_payment':
            return handle_smart_bulk_payment(request)
        elif action == 'excel_upload':
            return handle_excel_upload(request)
    
    # GET request - display the page with data
    context = get_payment_tracker_context()
    return render(request, 'accounts/payment_tracker.html', context)

def patient_list_api(request):
    """Return patient list for frontend autocomplete"""
    patients = Patient.objects.all().values('id', 'full_name', 'phone')
    return JsonResponse(list(patients), safe=False)


def get_payment_tracker_context():
    """Get context data for the payment tracker page"""
    # Get recent payments (last 50)
    recent_payments = Payment.objects.select_related(
        'patient', 'bill', 'processed_by'
    ).order_by('-payment_date')[:50]
    
    # Get patient balances - patients with bills
    balance_list = []
    patients_with_bills = Patient.objects.filter(bills__isnull=False).distinct()
    
    for patient in patients_with_bills:
        total_billed = patient.bills.aggregate(
            total=Sum('final_amount')
        )['total'] or Decimal('0.00')
        
        total_paid = patient.payments.filter(
            status='completed'
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        outstanding = total_billed - total_paid
        
        balance_list.append({
            'patient': patient,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'outstanding': outstanding
        })
    
    # Sort by outstanding amount (highest first)
    balance_list.sort(key=lambda x: x['outstanding'], reverse=True)
    
    return {
        'recent_payments': recent_payments,
        'balance_list': balance_list,
    }


@transaction.atomic
def handle_traditional_bulk_payment(request):
    """Handle traditional bulk payment form submission"""
    try:
        payments_data = []
        successful_count = 0
        errors = []
        
        # Extract payment data from form
        form_data = request.POST
        payment_indices = set()
        
        # Find all payment indices
        for key in form_data.keys():
            if key.startswith('payments[') and '][' in key:
                index = key.split('[')[1].split(']')[0]
                payment_indices.add(int(index))
        
        # Process each payment
        for index in sorted(payment_indices):
            try:
                payment_data = extract_payment_data(form_data, index)
                if payment_data:
                    payments_data.append(payment_data)
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        # Save valid payments
        for payment_data in payments_data:
            try:
                payment = create_payment_record(payment_data, request.user)
                if payment:
                    successful_count += 1
            except Exception as e:
                errors.append(f"Failed to save payment for {payment_data.get('patient_name', 'Unknown')}: {str(e)}")
        
        if successful_count > 0:
            messages.success(request, f"Successfully recorded {successful_count} payment(s).")
        
        if errors:
            messages.warning(request, f"Some payments failed: {'; '.join(errors[:3])}")
        
        return JsonResponse({
            'success': True,
            'count': successful_count,
            'errors': errors
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@transaction.atomic
def handle_smart_bulk_payment(request):
    """Handle smart bulk payment submission from the UI"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})

    try:
        if request.POST.get('action') != 'smart_bulk_payment':
            return JsonResponse({'success': False, 'error': 'Invalid action specified.'})

        payments_json = request.POST.get('payments')
        if not payments_json:
            return JsonResponse({'success': False, 'error': 'No payment data received.'})

        payments_data = json.loads(payments_json)
        successful_count = 0
        errors = []

        for entry in payments_data:
            try:
                if not entry.get('isValid'):
                    continue

                patient_id = entry.get('patient_id')
                if not patient_id:
                    raise ValueError("Missing patient_id.")

                patient = Patient.objects.get(id=patient_id)

                amount = Decimal(str(entry.get('amount', '0.00')))
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0.")

                method = entry.get('method', 'cash').lower()
                reference = entry.get('reference', '')
                notes = entry.get('notes', '')

                Payment.objects.create(
                    bill=None,
                    patient=patient,
                    amount=amount,
                    payment_method=method,
                    payment_reference=reference,
                    status='completed',
                    processed_by=request.user,
                    notes=notes
                )
                successful_count += 1

            except Patient.DoesNotExist:
                errors.append(f"Line {entry.get('lineNumber', '?')}: Patient not found.")
            except Exception as e:
                errors.append(f"Line {entry.get('lineNumber', '?')}: {str(e)}")

        return JsonResponse({
            'success': True,
            'count': successful_count,
            'errors': errors
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@transaction.atomic
def handle_excel_upload(request):
    """Handle Excel file upload for bulk payments"""
    try:
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            return JsonResponse({
                'success': False,
                'error': 'No file uploaded'
            })
        
        # Create upload record
        upload_record = PaymentUpload.objects.create(
            uploaded_by=request.user,
            file_name=excel_file.name,
            status='processing'
        )
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Standardize column names
            df.columns = df.columns.str.lower().str.strip()
            column_mapping = {
                'patient name': 'patient_name',
                'patient_name': 'patient_name',
                'name': 'patient_name',
                'amount': 'amount',
                'payment method': 'method',
                'method': 'method',
                'payment_method': 'method',
                'reference': 'reference',
                'payment reference': 'reference',
                'payment_reference': 'reference',
                'notes': 'notes',
                'note': 'notes',
                'description': 'notes'
            }
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            
            # Validate required columns
            required_columns = ['patient_name', 'amount']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
            
            # Process each row
            successful_count = 0
            failed_count = 0
            error_log = []
            
            for index, row in df.iterrows():
                try:
                    # Clean and validate data
                    payment_data = {
                        'patient_name': str(row['patient_name']).strip(),
                        'amount': float(row['amount']),
                        'method': str(row.get('method', 'cash')).lower().strip(),
                        'reference': str(row.get('reference', '')).strip(),
                        'notes': str(row.get('notes', '')).strip()
                    }
                    
                    # Skip empty rows
                    if not payment_data['patient_name'] or payment_data['patient_name'].lower() in ['nan', 'none']:
                        continue
                    
                    if payment_data['amount'] <= 0:
                        error_log.append(f"Row {index + 2}: Invalid amount")
                        failed_count += 1
                        continue
                    
                    # Create payment record
                    payment = create_payment_record(payment_data, request.user)
                    if payment:
                        successful_count += 1
                    else:
                        failed_count += 1
                        error_log.append(f"Row {index + 2}: Failed to create payment")
                        
                except Exception as e:
                    failed_count += 1
                    error_log.append(f"Row {index + 2}: {str(e)}")
            
            # Update upload record
            upload_record.total_records = len(df)
            upload_record.successful_records = successful_count
            upload_record.failed_records = failed_count
            upload_record.status = 'completed'
            upload_record.error_log = '\n'.join(error_log) if error_log else None
            upload_record.save()
            
            return JsonResponse({
                'success': True,
                'count': successful_count,
                'failed': failed_count,
                'errors': error_log[:10]  # Return first 10 errors
            })
            
        except Exception as e:
            upload_record.status = 'failed'
            upload_record.error_log = str(e)
            upload_record.save()
            raise e
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def extract_payment_data(form_data, index):
    """Extract payment data for a specific index from form data"""
    patient_name = form_data.get(f'payments[{index}][patient_name]', '').strip()
    patient_id = form_data.get(f'payments[{index}][patient_id]', '').strip()
    amount_str = form_data.get(f'payments[{index}][amount]', '0')
    method = form_data.get(f'payments[{index}][method]', 'cash')
    reference = form_data.get(f'payments[{index}][reference]', '').strip()
    notes = form_data.get(f'payments[{index}][notes]', '').strip()
    
    if not patient_name:
        return None
    
    try:
        amount = Decimal(str(amount_str))
    except (ValueError, TypeError):
        raise ValueError("Invalid amount format")
    
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")
    
    return {
        'patient_name': patient_name,
        'patient_id': patient_id if patient_id else None,
        'amount': amount,
        'method': method,
        'reference': reference,
        'notes': notes
    }


def create_payment_record(payment_data, user):
    """Create a payment record from payment data"""
    try:
        # Find or get patient
        patient = None
        if payment_data.get('patient_id'):
            try:
                patient = Patient.objects.get(id=payment_data['patient_id'])
            except Patient.DoesNotExist:
                pass
        
        if not patient:
            # Try to find by name
            patient_name = payment_data['patient_name']
            patients = Patient.objects.filter(
                Q(full_name__iexact=patient_name) |
                Q(full_name__icontains=patient_name)
            )
            
            if patients.count() == 1:
                patient = patients.first()
            elif patients.count() > 1:
                # Try exact match first
                exact_matches = patients.filter(full_name__iexact=patient_name)
                if exact_matches.count() == 1:
                    patient = exact_matches.first()
                else:
                    raise ValueError(f"Multiple patients found with name '{patient_name}'. Please be more specific.")
            else:
                raise ValueError(f"Patient '{patient_name}' not found in system")
        
        # Create or get a bill for this patient
        # For payments without specific bills, create a general bill
        bill = get_or_create_patient_bill(patient, payment_data['amount'], user)
        
        # Create the payment record
        payment = Payment.objects.create(
            bill=bill,
            patient=patient,
            amount=payment_data['amount'],
            payment_method=payment_data['method'],
            payment_reference=payment_data.get('reference', ''),
            status='completed',
            processed_by=user,
            notes=payment_data.get('notes', '')
        )
        
        # Update bill status based on payments
        update_bill_status(bill)
        
        return payment
        
    except Exception as e:
        raise Exception(f"Failed to create payment: {str(e)}")


def get_or_create_patient_bill(patient, amount, user):
    """Get existing unpaid bill or create a new one"""
    # Try to find an existing unpaid bill
    existing_bill = PatientBill.objects.filter(
        patient=patient,
        status__in=['pending', 'partial']
    ).order_by('-created_at').first()
    
    if existing_bill and existing_bill.outstanding_amount() > 0:
        return existing_bill
    
    # Create new bill for this payment
    # This assumes the payment is for general services
    # You might want to modify this based on your business logic
    service_type, created = ServiceType.objects.get_or_create(
        name='General Payment',
        defaults={
            'description': 'General payment without specific service',
            'default_price': amount
        }
    )
    
    bill = PatientBill.objects.create(
        patient=patient,
        total_amount=amount,
        final_amount=amount,
        status='pending',
        created_by=user,
        notes='Created from payment tracker'
    )
    
    # Create bill item
    from .models import BillItem
    BillItem.objects.create(
        bill=bill,
        service_type=service_type,
        description='General Payment',
        quantity=1,
        unit_price=amount,
        total_price=amount
    )
    
    return bill


def update_bill_status(bill):
    """Update bill status based on payment amount"""
    total_paid = bill.amount_paid()
    
    if total_paid >= bill.final_amount:
        bill.status = 'paid'
    elif total_paid > 0:
        bill.status = 'partial'
    else:
        bill.status = 'pending'
    
    bill.save()


# API endpoints for AJAX calls
@login_required(login_url='home')
def get_patients_api(request):
    """API endpoint to get patients for autocomplete"""
    query = request.GET.get('q', '')
    patients = Patient.objects.all()
    
    if query:
        patients = patients.filter(
            Q(full_name__icontains=query) |
            Q(phone__icontains=query)
        )
    
    patients_data = [
        {
            'id': patient.id,
            'full_name': patient.full_name,
            'phone': patient.phone or '',
        }
        for patient in patients[:20]  # Limit to 20 results
    ]
    
    return JsonResponse(patients_data, safe=False)


@login_required(login_url='home')
def get_patient_financial_details(request, patient_id):
    """Get detailed financial information for a patient"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Get all bills
        bills = PatientBill.objects.filter(patient=patient).order_by('-created_at')
        
        # Get all payments
        payments = Payment.objects.filter(patient=patient).order_by('-payment_date')
        
        # Calculate totals
        total_billed = bills.aggregate(total=Sum('final_amount'))['total'] or Decimal('0.00')
        total_paid = payments.filter(status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        outstanding = total_billed - total_paid
        
        context = {
            'patient': patient,
            'bills': bills,
            'payments': payments,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'outstanding': outstanding
        }
        
        return render(request, 'accounts/patient_financial_details_modal.html', context)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)