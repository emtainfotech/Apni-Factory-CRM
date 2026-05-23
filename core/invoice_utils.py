import datetime
from decimal import Decimal
from django.db.models import Max
from .models import Invoice

def calculate_gst_values(total_amount, is_gst_inclusive, client_state_code, our_state_code="23"):
    """
    Calculates taxable value and GST split based on total amount and GST type.
    """
    total_amount = Decimal(str(total_amount))
    
    if is_gst_inclusive:
        taxable_value = round(total_amount / Decimal('1.18'), 2)
        gst_total = round(total_amount - taxable_value, 2)
    else:
        taxable_value = total_amount
        gst_total = round(taxable_value * Decimal('0.18'), 2)
        total_amount = round(taxable_value + gst_total, 2)

    # GST Split Logic
    if client_state_code == our_state_code:
        cgst = round(gst_total / 2, 2)
        sgst = round(gst_total / 2, 2)
        igst = Decimal('0')
    else:
        igst = gst_total
        cgst = Decimal('0')
        sgst = Decimal('0')

    # Line Item Logic (As per requirements: 5000 for listing, rest for marketing)
    listing_taxable = Decimal('5000')
    if taxable_value < listing_taxable:
        listing_taxable = taxable_value
    
    marketing_taxable = round(taxable_value - listing_taxable, 2)

    return {
        'taxable_value': taxable_value,
        'gst_total': gst_total,
        'cgst': cgst,
        'sgst': sgst,
        'igst': igst,
        'total_amount': total_amount,
        'listing_taxable': listing_taxable,
        'marketing_taxable': marketing_taxable
    }

def get_next_invoice_number():
    """
    Generates the next sequential invoice number in AF/YY-YY/XXXX format.
    """
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    
    # Financial Year Calculation (Starts April)
    if month >= 4:
        fy_start = year % 100
        fy_end = (year + 1) % 100
    else:
        fy_start = (year - 1) % 100
        fy_end = year % 100
    
    fy_str = f"{fy_start:02d}-{fy_end:02d}"
    prefix = f"AF/{fy_str}/"
    
    # Get last invoice for this FY
    last_invoice = Invoice.objects.filter(invoice_no__startswith=prefix).aggregate(Max('invoice_no'))['invoice_no__max']
    
    if last_invoice:
        try:
            last_seq = int(last_invoice.split('/')[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1
        
    return f"{prefix}{new_seq:04d}"
