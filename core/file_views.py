import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.core.files.storage import FileSystemStorage
from .models import CustomerFolder, CustomerFile, Customer
from django.db.models import Q
from django.core.exceptions import PermissionDenied

@login_required
def file_manager_view(request):
    """
    Renders the global file manager UI.
    Admins can see all customers.
    Employees see only their assigned customers.
    """
    customers = Customer.objects.all()
    if request.user.role == 'employee' and not request.user.is_superuser:
        customers = customers.filter(assigned_to=request.user)

    return render(request, 'core/file_manager.html', {'customers': customers})

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
    uploaded_file = request.FILES.get('file')

    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

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

    return JsonResponse({
        'success': True, 
        'file': {
            'id': customer_file.id,
            'name': customer_file.name,
            'url': customer_file.file.url,
            'size': customer_file.size,
            'type': customer_file.file_type,
            'uploaded_at': customer_file.uploaded_at.strftime('%Y-%m-%d %H:%M')
        }
    })
