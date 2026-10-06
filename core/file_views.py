import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.core.files.storage import FileSystemStorage
from .models import CustomerFolder, CustomerFile, Customer
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from django.core.paginator import Paginator

@login_required
def file_manager_view(request):
    """
    Renders the global file manager UI.
    Admins can see all customers.
    Employees see only their assigned customers.
    """
    customers = Customer.objects.all().order_by('-created_at')
    if request.user.role == 'employee' and not request.user.is_superuser:
        customers = customers.filter(assigned_to=request.user)

    search_query = request.GET.get('q', '')
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) | 
            Q(phone__icontains=search_query) | 
            Q(company_name__icontains=search_query)
        )

    paginator = Paginator(customers, 10) # Show 10 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/file_manager.html', {'page_obj': page_obj, 'search_query': search_query})

@login_required
@require_GET
def get_customer_folders_api(request, customer_id):
    """
    Returns the folder structure and files for a specific customer.
    If parent_id is provided, returns contents of that subfolder.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    if request.user.role == 'employee' and not request.user.is_superuser and customer.assigned_to != request.user:
        raise PermissionDenied("You do not have access to this customer.")

    parent_id = request.GET.get('parent_id')

    if parent_id:
        parent_folder = get_object_or_404(CustomerFolder, id=parent_id, customer=customer)
        folders = parent_folder.subfolders.all()
        files = parent_folder.files.all()
    else:
        folders = CustomerFolder.objects.filter(customer=customer, parent=None)
        # Files at root level (should generally be none, but just in case)
        # Actually, let's just return folders at root level.
        files = []

    folder_data = [{'id': f.id, 'name': f.name, 'is_system': f.is_system_folder} for f in folders]
    file_data = []
    for f in files:
        file_data.append({
            'id': f.id,
            'name': f.name,
            'url': f.file.url if f.file else '',
            'size': f.size,
            'type': f.file_type,
            'uploaded_at': f.uploaded_at.strftime('%Y-%m-%d %H:%M')
        })

    return JsonResponse({'folders': folder_data, 'files': file_data})

@login_required
@require_POST
def create_folder_api(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.user.role == 'employee' and not request.user.is_superuser and customer.assigned_to != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    parent_id = request.POST.get('parent_id')
    name = request.POST.get('name')

    if not name:
        return JsonResponse({'error': 'Folder name is required'}, status=400)

    parent_folder = None
    if parent_id:
        parent_folder = get_object_or_404(CustomerFolder, id=parent_id, customer=customer)

    folder, created = CustomerFolder.objects.get_or_create(
        customer=customer,
        parent=parent_folder,
        name=name,
        defaults={'created_by': request.user}
    )

    if not created:
        return JsonResponse({'error': 'Folder already exists'}, status=400)

    return JsonResponse({'success': True, 'folder': {'id': folder.id, 'name': folder.name, 'is_system': folder.is_system_folder}})

@login_required
@require_POST
def upload_file_api(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.user.role == 'employee' and not request.user.is_superuser and customer.assigned_to != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    folder_id = request.POST.get('folder_id')
    
    if not folder_id:
        return JsonResponse({'error': 'Folder ID is required'}, status=400)
        
    folder = get_object_or_404(CustomerFolder, id=folder_id, customer=customer)
    files = request.FILES.getlist('file')

    if not files:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    uploaded_data = []
    for uploaded_file in files:
        size = uploaded_file.size
        mime_type = uploaded_file.content_type

        customer_file = CustomerFile.objects.create(
            folder=folder,
            file=uploaded_file,
            name=uploaded_file.name,
            file_type=mime_type,
            size=size,
            uploaded_by=request.user
        )
        uploaded_data.append({
            'id': customer_file.id,
            'name': customer_file.name,
            'url': customer_file.file.url,
            'size': customer_file.size,
            'type': customer_file.file_type,
            'uploaded_at': customer_file.uploaded_at.strftime('%Y-%m-%d %H:%M')
        })

    return JsonResponse({
        'success': True, 
        'files': uploaded_data
    })

@login_required
@require_POST
def rename_file_api(request, file_id):
    customer_file = get_object_or_404(CustomerFile, id=file_id)
    if request.user.role == 'employee' and not request.user.is_superuser and customer_file.folder.customer.assigned_to != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    new_name = request.POST.get('name')
    if not new_name:
        return JsonResponse({'error': 'Name is required'}, status=400)
        
    customer_file.name = new_name
    customer_file.save()
    return JsonResponse({'success': True})

@login_required
@require_POST
def delete_file_api(request, file_id):
    customer_file = get_object_or_404(CustomerFile, id=file_id)
    if request.user.role == 'employee' and not request.user.is_superuser and customer_file.folder.customer.assigned_to != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    customer_file.file.delete() # Deletes actual file from storage
    customer_file.delete()
    return JsonResponse({'success': True})
