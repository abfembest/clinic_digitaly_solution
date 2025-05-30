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
        transaction_type = request.POST.get('type')
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        description = request.POST.get('description')

        try:
            amount = Decimal(amount)
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()

            # Only allow Expenditure input from the form
            if transaction_type == 'Expenditure':
                category, _ = ExpenseCategory.objects.get_or_create(name="General")
                Expense.objects.create(
                    category=category,
                    description=description,
                    amount=amount,
                    expense_date=date_obj,
                    status='paid',
                    requested_by=request.user,
                    approved_by=request.user
                )
                messages.success(request, 'Expenditure transaction saved successfully.')
            else:
                messages.error(request, 'Only expenditure can be recorded through this form.')

        except Exception as e:
            messages.error(request, f"Error: {e}")

    # Get all income payments and expenditure expenses
    payments = Payment.objects.filter(status='completed').values(
        'payment_date', 'amount', 'notes'
    )
    expenses = Expense.objects.filter(status='paid').values(
        'expense_date', 'amount', 'description'
    )

    transactions = []

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
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Render only the transactions table + pagination part
        html = render_to_string('accounts/financials.html', context, request=request, using=None)
        # We want to extract only the relevant block to send back — we can use a dedicated block for this (see next)
        return JsonResponse({'html': html})

    return render(request, 'accounts/financials.html', context)

def financial_reports(request):
    # Define date range (last 30 days)
    end_date = now().date()
    start_date = end_date - timedelta(days=29)

    print("="*50)
    print("FINANCIAL REPORTS DEBUG")
    print("="*50)
    print(f"Date range: {start_date} to {end_date}")

    # ===== EXPENSE DEBUGGING =====
    print("\n--- EXPENSE ANALYSIS ---")
    
    # 1. Check total expenses in database
    total_expenses_count = Expense.objects.count()
    print(f"Total expenses in database: {total_expenses_count}")
    
    if total_expenses_count == 0:
        print("❌ NO EXPENSES FOUND IN DATABASE!")
        total_expenditure = Decimal('0.00')
    else:
        # 2. Check all unique status values
        print("\nExpense status distribution:")
        status_counts = Expense.objects.values('status').annotate(count=Count('id'))
        for item in status_counts:
            print(f"  - Status '{item['status']}': {item['count']} records")
        
        # 3. Check expenses by date (all statuses)
        all_expenses_in_range = Expense.objects.filter(
            expense_date__range=(start_date, end_date)
        )
        print(f"\nExpenses in date range ({start_date} to {end_date}): {all_expenses_in_range.count()}")
        
        # 4. Show sample expense data
        print("\nSample expense records:")
        sample_expenses = Expense.objects.all()[:5]
        for expense in sample_expenses:
            print(f"  - {expense.description}: ₦{expense.amount}, Status: '{expense.status}', Date: {expense.expense_date}")
        
        # 5. Calculate different expenditure scenarios
        print("\n--- EXPENDITURE CALCULATIONS ---")
        
        # Scenario 1: Original filter (approved + paid)
        exp_approved_paid = Expense.objects.filter(
            status__in=['approved', 'paid'],
            expense_date__range=(start_date, end_date)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        print(f"Expenditure (approved + paid): ₦{exp_approved_paid}")
        
        # Scenario 2: All expenses in date range
        exp_all_in_range = Expense.objects.filter(
            expense_date__range=(start_date, end_date)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        print(f"Expenditure (all in date range): ₦{exp_all_in_range}")
        
        # Scenario 3: All expenses regardless of date
        exp_all_time = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        print(f"Expenditure (all time): ₦{exp_all_time}")
        
        # Scenario 4: Different status combinations
        for status_combo in [['pending'], ['approved'], ['paid'], ['pending', 'approved'], ['pending', 'paid']]:
            exp_combo = Expense.objects.filter(
                status__in=status_combo,
                expense_date__range=(start_date, end_date)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            print(f"Expenditure ({'+'.join(status_combo)}): ₦{exp_combo}")
        
        # Decide which expenditure to use
        if exp_approved_paid > 0:
            total_expenditure = exp_approved_paid
            print(f"\n✅ Using approved + paid expenditure: ₦{total_expenditure}")
        elif exp_all_in_range > 0:
            total_expenditure = exp_all_in_range
            print(f"\n⚠️  Using all expenses in range: ₦{total_expenditure}")
        else:
            total_expenditure = Decimal('0.00')
            print(f"\n❌ No expenses found - using ₦0.00")

    # ===== INCOME CALCULATION =====
    print("\n--- INCOME ANALYSIS ---")
    
    payment_count = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(start_date, end_date)
    ).count()
    print(f"Completed payments in range: {payment_count}")
    
    total_income_agg = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(start_date, end_date)
    ).aggregate(total=Sum('amount'))
    total_income = total_income_agg['total'] or Decimal('0.00')
    print(f"Total income: ₦{total_income}")

    # ===== FINAL CALCULATIONS =====
    net_balance = total_income - total_expenditure
    
    print("\n--- FINAL SUMMARY ---")
    print(f"Total Income: ₦{total_income}")
    print(f"Total Expenditure: ₦{total_expenditure}")
    print(f"Net Balance: ₦{net_balance}")
    
    if total_income == net_balance and total_expenditure == 0:
        print("❌ WARNING: Expenditure is zero - this suggests a data or filter issue!")
    
    print("="*50)

    # ===== CHART DATA =====
    # Prepare daily income chart data
    date_labels = [(start_date + timedelta(days=i)) for i in range(30)]
    daily_income_dict = OrderedDict((d.strftime('%Y-%m-%d'), 0) for d in date_labels)

    # Aggregate income grouped by day
    daily_income_qs = Payment.objects.filter(
        status='completed',
        payment_date__date__range=(start_date, end_date)
    ).values('payment_date__date').annotate(
        day_total=Sum('amount')
    ).order_by('payment_date__date')

    for entry in daily_income_qs:
        day_str = entry['payment_date__date'].strftime('%Y-%m-%d')
        daily_income_dict[day_str] = float(entry['day_total'])

    # Prepare daily expenditure chart data
    daily_expenditure_dict = OrderedDict((d.strftime('%Y-%m-%d'), 0) for d in date_labels)
    
    # Use broader filter for expenditure if needed
    if total_expenditure > 0:
        if exp_approved_paid > 0:
            expense_filter = {'status__in': ['approved', 'paid'], 'expense_date__range': (start_date, end_date)}
        else:
            expense_filter = {'expense_date__range': (start_date, end_date)}
        
        daily_expenditure_qs = Expense.objects.filter(
            **expense_filter
        ).values('expense_date').annotate(
            day_total=Sum('amount')
        ).order_by('expense_date')

        for entry in daily_expenditure_qs:
            day_str = entry['expense_date'].strftime('%Y-%m-%d')
            daily_expenditure_dict[day_str] = float(entry['day_total'])

    context = {
        'total_income': total_income,
        'total_expenditure': total_expenditure,
        'net_balance': net_balance,
        'chart_labels': list(daily_income_dict.keys()),
        'chart_data': list(daily_income_dict.values()),
        'expenditure_data': list(daily_expenditure_dict.values()),
        # Add debug info to template if needed
        'debug_info': {
            'total_expenses_in_db': total_expenses_count,
            'expenses_in_date_range': all_expenses_in_range.count() if total_expenses_count > 0 else 0,
            'date_range': f"{start_date} to {end_date}"
        }
    }

    return render(request, 'accounts/financial_reports.html', context)

def budget_planning(request):
    """
    Handle budget planning - display existing budgets and create new ones
    """
    if request.method == 'POST':
        try:
            # Get form data
            category_name = request.POST.get('category', '').strip()
            amount = request.POST.get('amount')
            period = request.POST.get('period')  # Format: YYYY-MM
            
            # Validate required fields
            if not category_name or not amount or not period:
                messages.error(request, 'All fields are required.')
                return redirect('budget_planning')
            
            # Parse period (YYYY-MM)
            try:
                year, month = map(int, period.split('-'))
            except ValueError:
                messages.error(request, 'Invalid period format.')
                return redirect('budget_planning')
            
            # Validate amount
            try:
                amount = float(amount)
                if amount <= 0:
                    messages.error(request, 'Amount must be greater than zero.')
                    return redirect('budget_planning')
            except ValueError:
                messages.error(request, 'Invalid amount format.')
                return redirect('budget_planning')
            
            # Get or create expense category
            expense_category, created = ExpenseCategory.objects.get_or_create(
                name=category_name,
                defaults={'description': f'Budget category for {category_name}'}
            )
            
            # Check if budget already exists for this category and period
            existing_budget = Budget.objects.filter(
                category=expense_category,
                year=year,
                month=month
            ).first()
            
            if existing_budget:
                # Update existing budget
                existing_budget.allocated_amount = amount
                existing_budget.save()
                messages.success(request, f'Budget for {category_name} updated successfully!')
            else:
                # Create new budget
                Budget.objects.create(
                    category=expense_category,
                    year=year,
                    month=month,
                    allocated_amount=amount,
                    created_by=request.user
                )
                messages.success(request, f'Budget for {category_name} created successfully!')
            
        except Exception as e:
            messages.error(request, f'Error creating budget: {str(e)}')
        
        return redirect('budget_planning')
    
    # GET request - display budgets
    budgets = Budget.objects.select_related('category').order_by('-year', '-month', 'category__name')
    
    # Calculate spent amounts for each budget
    for budget in budgets:
        # Calculate spent amount based on expenses in the same period
        spent_amount = Expense.objects.filter(
            category=budget.category,
            expense_date__year=budget.year,
            expense_date__month=budget.month if budget.month else None,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Update the budget's spent amount
        budget.spent_amount = spent_amount
        budget.save()
    
    # Add budget statistics
    total_allocated = budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
    total_spent = budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
    
    context = {
        'budgets': budgets,
        'total_allocated': total_allocated,
        'total_spent': total_spent,
        'total_remaining': total_allocated - total_spent,
        'current_year': datetime.now().year,
        'current_month': datetime.now().month,
    }
    
    return render(request, 'accounts/planning.html', context)

@login_required
def budget_analytics(request):
    """
    Provide budget analytics data for charts/graphs
    """
    # Monthly budget overview for current year
    current_year = datetime.now().year
    monthly_data = []
    
    for month in range(1, 13):
        month_budgets = Budget.objects.filter(year=current_year, month=month)
        allocated = month_budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        spent = month_budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        
        monthly_data.append({
            'month': month,
            'allocated': float(allocated),
            'spent': float(spent),
            'remaining': float(allocated - spent)
        })
    
    # Category-wise budget breakdown
    category_data = []
    categories = ExpenseCategory.objects.filter(budget__year=current_year).distinct()
    
    for category in categories:
        category_budgets = Budget.objects.filter(category=category, year=current_year)
        allocated = category_budgets.aggregate(total=Sum('allocated_amount'))['total'] or 0
        spent = category_budgets.aggregate(total=Sum('spent_amount'))['total'] or 0
        
        category_data.append({
            'category': category.name,
            'allocated': float(allocated),
            'spent': float(spent),
            'percentage_used': (float(spent) / float(allocated) * 100) if allocated > 0 else 0
        })
    
    return JsonResponse({
        'monthly_data': monthly_data,
        'category_data': category_data
    })

@login_required
def delete_budget(request, budget_id):
    """
    Delete a specific budget
    """
    if request.method == 'POST':
        try:
            budget = Budget.objects.get(id=budget_id)
            category_name = budget.category.name
            period = f"{budget.month}/{budget.year}" if budget.month else str(budget.year)
            budget.delete()
            messages.success(request, f'Budget for {category_name} ({period}) deleted successfully!')
        except Budget.DoesNotExist:
            messages.error(request, 'Budget not found.')
        except Exception as e:
            messages.error(request, f'Error deleting budget: {str(e)}')
    
    return redirect('budget_planning')