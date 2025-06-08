import json
import pandas as pd
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q, Count
from datetime import datetime, date
from io import BytesIO
from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Sum, Q
from django.utils.timezone import now
from datetime import timedelta
from collections import OrderedDict
from decimal import Decimal
from django.template.loader import render_to_string

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, F, Case, When, DecimalField
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, date
import csv
from decimal import Decimal

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

        form_data = request.POST
        payment_indices = set()

        # Detect all indexed payment entries
        for key in form_data.keys():
            if key.startswith('payments[') and '][' in key:
                index = key.split('[')[1].split(']')[0]
                payment_indices.add(int(index))

        # Extract and process each entry
        for index in sorted(payment_indices):
            try:
                patient_id = form_data.get(f'payments[{index}][patient_id]')
                patient_name = form_data.get(f'payments[{index}][patient_name]')
                amount = form_data.get(f'payments[{index}][amount]')
                method = form_data.get(f'payments[{index}][method]', 'cash').lower()
                reference = form_data.get(f'payments[{index}][reference]', '')
                notes = form_data.get(f'payments[{index}][notes]', '')

                if not patient_id or not amount:
                    raise ValueError("Missing patient or amount.")

                patient = Patient.objects.get(id=patient_id)
                amount = Decimal(amount)
                if amount <= 0:
                    raise ValueError("Amount must be greater than zero.")

                # Save payment (no bill required)
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
                errors.append(f"Row {index + 1}: Patient not found.")
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")

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
        
        # Prepare data for JSON response
        data = {
            'patient': {
                'id': patient.id,
                'full_name': patient.full_name,
                'phone': patient.phone,
                'email': getattr(patient, 'email', ''),
                'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d') if hasattr(patient, 'date_of_birth') and patient.date_of_birth else '',
                'gender': getattr(patient, 'gender', ''),
            },
            'bills': [
                {
                    'id': bill.id,
                    'created_at': bill.created_at.isoformat(),
                    'description': getattr(bill, 'description', 'Medical Bill'),
                    'final_amount': str(bill.final_amount),
                    'status': getattr(bill, 'status', 'pending'),
                } for bill in bills
            ],
            'payments': [
                {
                    'id': payment.id,
                    'payment_date': payment.payment_date.isoformat(),
                    'amount': str(payment.amount),
                    'payment_method': payment.get_payment_method_display(),
                    'payment_reference': payment.payment_reference or '',
                    'status': payment.status,
                    'processed_by': payment.processed_by.get_full_name() if payment.processed_by else 'System',
                } for payment in payments
            ],
            'total_billed': str(total_billed),
            'total_paid': str(total_paid),
            'outstanding': str(outstanding),
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

def income_expenditure_view(request):
    if request.method == 'POST':
        # Handle expense approval/rejection/payment
        action = request.POST.get('action')
        if action in ['approve', 'reject', 'mark_paid']:
            expense_id = request.POST.get('expense_id')
            try:
                expense = Expense.objects.get(id=expense_id)
                
                # Only admins can approve/reject/mark as paid
                if hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
                    if action == 'approve':
                        expense.status = 'approved'
                        expense.approved_by = request.user
                        expense.approved_at = timezone.now()
                        expense.save()
                        messages.success(request, f'Expense request #{expense_id} has been approved.')
                    elif action == 'reject':
                        expense.status = 'rejected'
                        expense.approved_by = request.user
                        expense.approved_at = timezone.now()
                        expense.save()
                        messages.success(request, f'Expense request #{expense_id} has been rejected.')
                    elif action == 'mark_paid':
                        # Check if expense is in approved status
                        if expense.status != 'approved':
                            messages.error(request, f'Expense request #{expense_id} must be approved before it can be marked as paid.')
                        else:
                            expense.status = 'paid'
                            expense.paid_at = timezone.now()
                            expense.save()
                            messages.success(request, f'Expense request #{expense_id} has been marked as paid.')
                else:
                    messages.error(request, 'Only administrators can perform actions on expense requests.')
            except Expense.DoesNotExist:
                messages.error(request, f'Expense with ID {expense_id} not found.')
            except Exception as e:
                messages.error(request, f"Error processing request: {str(e)}")
            
            return redirect('income_expenditure')
        
        # Handle new expense request submission
        transaction_type = request.POST.get('type')
        amount = request.POST.get('amount')
        description = request.POST.get('description')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return redirect('income_expenditure')
                
            # Validate description
            if not description or not description.strip():
                messages.error(request, 'Description is required.')
                return redirect('income_expenditure')

            # Only allow Expenditure input from the form
            if transaction_type == 'Expenditure':
                category, _ = ExpenseCategory.objects.get_or_create(name="General")
                Expense.objects.create(
                    category=category,
                    description=description.strip(),
                    amount=amount,
                    expense_date=timezone.now().date(),
                    status='pending',
                    requested_by=request.user,
                    created_at=timezone.now()
                )
                messages.success(request, 'Expense request submitted successfully and is pending approval.')
            else:
                messages.error(request, 'Only expenditure can be requested through this form.')

        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
        except Exception as e:
            messages.error(request, f"Error submitting request: {str(e)}")

        return redirect('income_expenditure')

    # Get expense records with proper ordering (newest first)
    expenses_queryset = Expense.objects.select_related('requested_by', 'approved_by').order_by('-created_at', '-id')
    
    # Calculate summary statistics
    total_pending = expenses_queryset.filter(status='pending').aggregate(
        total=Sum('amount'))['total'] or 0
    total_approved = expenses_queryset.filter(status='approved').aggregate(
        total=Sum('amount'))['total'] or 0
    total_paid = expenses_queryset.filter(status='paid').aggregate(
        total=Sum('amount'))['total'] or 0
    rejected_count = expenses_queryset.filter(status='rejected').count()

<<<<<<< Updated upstream
    # Pagination - 15 expenses per page
    paginator = Paginator(expenses_queryset, 15)
=======
    for p in payments:
        transactions.append({
            'date': p['payment_date'].date(),
            'type': 'Income',
            'description': p['notes'] or '',
            'amount': p['amount']
        })

    for e in expenses:
        transactions.append({
            'date': e['expense_date'],
            'type': 'Expenditure',
            'description': e['description'],
            'amount': e['amount']
        })

    transactions.sort(key=lambda x: x['date'], reverse=True)

    # Pagination - 10 transactions per page
    paginator = Paginator(transactions, 20)
>>>>>>> Stashed changes
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Format transactions for template compatibility
    transactions = []
    for expense in page_obj:
        transactions.append({
            'id': expense.id,
            'date': expense.expense_date,
            'created_at': expense.created_at,
            'description': expense.description,
            'amount': expense.amount,
            'status': expense.status,
            'requested_by': expense.requested_by,
            'approved_by': expense.approved_by,
        })

    context = {
        'page_obj': page_obj,
        'transactions': transactions,
        'total_pending': total_pending,
        'total_approved': total_approved,
        'total_paid': total_paid,
        'rejected_count': rejected_count,
    }

    # Handle AJAX requests
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Return only the table section for AJAX updates
        html = render_to_string('accounts/expense_table_partial.html', context, request=request)
        return JsonResponse({'html': html, 'success': True})

    return render(request, 'accounts/financials.html', context)

def financial_reports(request):
<<<<<<< Updated upstream
    # Define date ranges
    today = now().date()
    last_30_days_start = today - timedelta(days=29)
    last_7_days_start = today - timedelta(days=6)
    current_month_start = today.replace(day=1)
    current_year_start = today.replace(month=1, day=1)
    
    # ===== INCOME CALCULATIONS =====
    # Last 30 days income
    income_30_days = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(last_30_days_start, today)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Current month income
    income_current_month = Payment.objects.filter(
        status='completed',
        payment_date__date__gte=current_month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Current year income
    income_current_year = Payment.objects.filter(
        status='completed',
        payment_date__date__gte=current_year_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Today's income
    income_today = Payment.objects.filter(
        status='completed',
        payment_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ===== EXPENDITURE CALCULATIONS =====
    # Last 30 days expenditure
    expenditure_30_days = Expense.objects.filter(
        expense_date__range=(last_30_days_start, today)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Current month expenditure
    expenditure_current_month = Expense.objects.filter(
        expense_date__gte=current_month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Current year expenditure
    expenditure_current_year = Expense.objects.filter(
        expense_date__gte=current_year_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Today's expenditure
    expenditure_today = Expense.objects.filter(
        expense_date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ===== NET CALCULATIONS =====
    net_30_days = income_30_days - expenditure_30_days
    net_current_month = income_current_month - expenditure_current_month
    net_current_year = income_current_year - expenditure_current_year
    net_today = income_today - expenditure_today

    # ===== DAILY BREAKDOWN (Last 30 Days) =====
    date_labels = [(last_30_days_start + timedelta(days=i)) for i in range(30)]
    
    # Initialize daily data
    daily_income_dict = OrderedDict()
    daily_expenditure_dict = OrderedDict()
    daily_net_dict = OrderedDict()
    
    for date_obj in date_labels:
        date_str = date_obj.strftime('%Y-%m-%d')
        daily_income_dict[date_str] = 0
        daily_expenditure_dict[date_str] = 0
        daily_net_dict[date_str] = 0

    # Get daily income
=======
    # Define date range (last 30 days)
    end_date = now().date()
    start_date = end_date - timedelta(days=29)

    # ===== INCOME CALCULATION =====
    total_income = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(start_date, end_date)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ===== EXPENDITURE CALCULATION =====
    # Calculate all expenses regardless of status (all firm expenditures)
    total_expenditure = Expense.objects.filter(
        expense_date__range=(start_date, end_date)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ===== NET BALANCE =====
    net_balance = total_income - total_expenditure

    # ===== CHART DATA PREPARATION =====
    # Create date range for chart
    date_labels = [(start_date + timedelta(days=i)) for i in range(30)]
    
    # Initialize daily dictionaries
    daily_income_dict = OrderedDict()
    daily_expenditure_dict = OrderedDict()
    
    for date_obj in date_labels:
        date_str = date_obj.strftime('%Y-%m-%d')
        daily_income_dict[date_str] = 0
        daily_expenditure_dict[date_str] = 0

    # Get daily income data
>>>>>>> Stashed changes
    daily_income_qs = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(last_30_days_start, today)
    ).values('payment_date__date').annotate(
        day_total=Sum('amount')
    ).order_by('payment_date__date')

    for entry in daily_income_qs:
        day_str = entry['payment_date__date'].strftime('%Y-%m-%d')
        if day_str in daily_income_dict:
            daily_income_dict[day_str] = float(entry['day_total'])

<<<<<<< Updated upstream
    # Get daily expenditure
    daily_expenditure_qs = Expense.objects.filter(
        expense_date__range=(last_30_days_start, today)
=======
    # Get daily expenditure data (all expenses)
    daily_expenditure_qs = Expense.objects.filter(
        expense_date__range=(start_date, end_date)
>>>>>>> Stashed changes
    ).values('expense_date').annotate(
        day_total=Sum('amount')
    ).order_by('expense_date')

    for entry in daily_expenditure_qs:
        day_str = entry['expense_date'].strftime('%Y-%m-%d')
        if day_str in daily_expenditure_dict:
            daily_expenditure_dict[day_str] = float(entry['day_total'])

<<<<<<< Updated upstream
    # Calculate daily net
    for date_str in daily_income_dict.keys():
        daily_net_dict[date_str] = daily_income_dict[date_str] - daily_expenditure_dict[date_str]

    # ===== TOP EXPENSE CATEGORIES (Current Month) =====
    top_expense_categories = Expense.objects.filter(
        expense_date__gte=current_month_start
    ).values('category__name').annotate(
        total_amount=Sum('amount'),
        expense_count=Count('id')
    ).order_by('-total_amount')[:5]

    # ===== RECENT TRANSACTIONS =====
    recent_income = Payment.objects.filter(
        status='completed'
    ).select_related('patient').order_by('-payment_date')[:5]
    
    recent_expenses = Expense.objects.select_related('category').order_by('-expense_date')[:5]

    # ===== MONTHLY COMPARISON (Last 6 Months) =====
    monthly_data = []
    for i in range(6):
        month_start = (today.replace(day=1) - timedelta(days=32*i)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_income = Payment.objects.filter(
            status='completed',
            payment_date__date__gte=month_start,
            payment_date__date__lt=next_month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        month_expenditure = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lt=next_month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        monthly_data.insert(0, {
            'month': month_start.strftime('%b %Y'),
            'income': float(month_income),
            'expenditure': float(month_expenditure),
            'net': float(month_income - month_expenditure)
        })

    # Format chart labels
    chart_labels = [date_obj.strftime('%m-%d') for date_obj in date_labels]
    
    context = {
        # Summary totals
        'income_30_days': income_30_days,
        'expenditure_30_days': expenditure_30_days,
        'net_30_days': net_30_days,
        'income_current_month': income_current_month,
        'expenditure_current_month': expenditure_current_month,
        'net_current_month': net_current_month,
        'income_current_year': income_current_year,
        'expenditure_current_year': expenditure_current_year,
        'net_current_year': net_current_year,
        'income_today': income_today,
        'expenditure_today': expenditure_today,
        'net_today': net_today,
        
        # Chart data
        'chart_labels': json.dumps(chart_labels),
        'daily_income_data': json.dumps(list(daily_income_dict.values())),
        'daily_expenditure_data': json.dumps(list(daily_expenditure_dict.values())),
        'daily_net_data': json.dumps(list(daily_net_dict.values())),
        
        # Monthly comparison
        'monthly_labels': json.dumps([item['month'] for item in monthly_data]),
        'monthly_income': json.dumps([item['income'] for item in monthly_data]),
        'monthly_expenditure': json.dumps([item['expenditure'] for item in monthly_data]),
        'monthly_net': json.dumps([item['net'] for item in monthly_data]),
        
        # Additional data
        'top_expense_categories': top_expense_categories,
        'recent_income': recent_income,
        'recent_expenses': recent_expenses,
        'date_range': f"{last_30_days_start.strftime('%b %d')} - {today.strftime('%b %d, %Y')}",
=======
    # Prepare chart labels (format dates for display)
    chart_labels = [date_obj.strftime('%m-%d') for date_obj in date_labels]

    context = {
        'total_income': total_income,
        'total_expenditure': total_expenditure,
        'net_balance': net_balance,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(list(daily_income_dict.values())),
        'expenditure_data': json.dumps(list(daily_expenditure_dict.values())),
>>>>>>> Stashed changes
    }

    return render(request, 'accounts/financial_reports.html', context)

@login_required
def budget_planning(request):
    """Enhanced budget planning with proper calculations and error handling"""
    
    if request.method == 'POST':
        return handle_budget_creation(request)
    
    # Get current period for filtering
    current_year = timezone.now().year
    current_month = timezone.now().month
    
    # Fetch budgets with related data and computed fields
    budgets = Budget.objects.select_related('category', 'created_by').annotate(
        # Calculate spent amount directly in query
        actual_spent=Sum(
            Case(
                When(
                    Q(category__expense__expense_date__year=F('year')) &
                    Q(category__expense__expense_date__month=F('month')) &
                    Q(category__expense__status='paid'),
                    then='category__expense__amount'
                ),
                default=0,
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ),
        # Calculate percentage and remaining
        usage_percentage=Case(
            When(allocated_amount__gt=0, 
                 then=(F('actual_spent') * 100.0) / F('allocated_amount')),
            default=0,
            output_field=DecimalField(max_digits=5, decimal_places=2)
        ),
        remaining=F('allocated_amount') - F('actual_spent')
    ).order_by('-year', '-month', 'category__name')
    
    # Update spent amounts in bulk
    budget_updates = []
    for budget in budgets:
        if budget.spent_amount != (budget.actual_spent or 0):
            budget.spent_amount = budget.actual_spent or 0
            budget_updates.append(budget)
    
    if budget_updates:
        Budget.objects.bulk_update(budget_updates, ['spent_amount'])
    
    # Calculate totals efficiently
    totals = budgets.aggregate(
        total_allocated=Sum('allocated_amount'),
        total_spent=Sum('actual_spent')
    )
    
    # Get category suggestions for datalist
    categories = ExpenseCategory.objects.filter(is_active=True).values_list('name', flat=True)
    
    context = {
        'budgets': budgets,
        'total_allocated': totals['total_allocated'] or 0,
        'total_spent': totals['total_spent'] or 0,
        'total_remaining': (totals['total_allocated'] or 0) - (totals['total_spent'] or 0),
        'current_year': current_year,
        'current_month': current_month,
        'categories': categories,
        'budget_count': budgets.count(),
    }
    
    return render(request, 'accounts/planning.html', context)

def handle_budget_creation(request):
    """Handle budget creation/update with proper validation"""
    try:
        # Extract and validate form data
        category_name = request.POST.get('category', '').strip()
        amount_str = request.POST.get('amount', '').strip()
        period_str = request.POST.get('period', '').strip()
        
        # Validation
        if not all([category_name, amount_str, period_str]):
            messages.error(request, 'All fields are required.')
            return redirect('budget_planning')
        
        # Validate and parse amount
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return redirect('budget_planning')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect('budget_planning')
        
        # Validate and parse period
        try:
            year, month = map(int, period_str.split('-'))
            if not (1 <= month <= 12) or year < 2020 or year > 2030:
                raise ValueError("Invalid date range")
        except (ValueError, TypeError):
            messages.error(request, 'Please select a valid period.')
            return redirect('budget_planning')
        
        # Get or create category
        category, created = ExpenseCategory.objects.get_or_create(
            name=category_name,
            defaults={
                'description': f'Budget category for {category_name}',
                'is_active': True
            }
        )
        
        # Create or update budget
        budget, budget_created = Budget.objects.update_or_create(
            category=category,
            year=year,
            month=month,
            defaults={
                'allocated_amount': amount,
                'created_by': request.user
            }
        )
        
        action = 'created' if budget_created else 'updated'
        messages.success(request, f'Budget for {category_name} ({month:02d}/{year}) {action} successfully!')
        
    except Exception as e:
        messages.error(request, f'Error processing budget: {str(e)}')
    
    return redirect('budget_planning')

@login_required
def delete_budget(request, budget_id):
    """Delete budget with proper error handling"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('budget_planning')
    
    try:
        budget = get_object_or_404(Budget, id=budget_id)
        category_name = budget.category.name
        period = f"{budget.month:02d}/{budget.year}"
        budget.delete()
        messages.success(request, f'Budget for {category_name} ({period}) deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting budget: {str(e)}')
    
    return redirect('budget_planning')

@login_required
def budget_analytics(request):
    """Provide budget analytics data"""
    current_year = timezone.now().year
    
    # Monthly overview
    monthly_data = []
    for month in range(1, 13):
        month_budgets = Budget.objects.filter(year=current_year, month=month)
        allocated = month_budgets.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
        spent = month_budgets.aggregate(Sum('spent_amount'))['spent_amount__sum'] or 0
        
        monthly_data.append({
            'month': month,
            'month_name': date(current_year, month, 1).strftime('%b'),
            'allocated': float(allocated),
            'spent': float(spent),
            'remaining': float(allocated - spent),
            'usage_percent': round((float(spent) / float(allocated) * 100) if allocated > 0 else 0, 1)
        })
    
    # Category breakdown
    category_data = Budget.objects.filter(year=current_year)\
        .values('category__name')\
        .annotate(
            allocated=Sum('allocated_amount'),
            spent=Sum('spent_amount')
        )\
        .order_by('-allocated')
    
    category_list = []
    for item in category_data:
        allocated = float(item['allocated'])
        spent = float(item['spent'])
        category_list.append({
            'category': item['category__name'],
            'allocated': allocated,
            'spent': spent,
            'remaining': allocated - spent,
            'usage_percent': round((spent / allocated * 100) if allocated > 0 else 0, 1)
        })
    
    return JsonResponse({
        'monthly_data': monthly_data,
        'category_data': category_list,
        'year': current_year
    })

@login_required
def export_budget_data(request):
    """Export budget data to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="budget_data_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Category', 'Period', 'Allocated Amount', 'Spent Amount', 'Remaining', 'Usage %', 'Status'])
    
    budgets = Budget.objects.select_related('category').order_by('-year', '-month', 'category__name')
    
    for budget in budgets:
        usage_percent = budget.percentage_used()
        status = 'Over Budget' if usage_percent > 100 else 'High Usage' if usage_percent > 80 else 'Caution' if usage_percent > 50 else 'Good'
        
        writer.writerow([
            budget.category.name,
            f"{budget.month:02d}/{budget.year}",
            float(budget.allocated_amount),
            float(budget.spent_amount),
            float(budget.remaining_amount()),
            f"{usage_percent:.1f}%",
            status
        ])
    
    return response