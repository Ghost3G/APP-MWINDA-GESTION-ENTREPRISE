"""
Setup initialization for first admin user creation.
Accessible only if no superusers exist.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings

User = get_user_model()


def setup_view(request):
    """Initialize admin user if none exists."""
    
    # Check if any superuser exists
    has_admin = User.objects.filter(is_superuser=True).exists()
    
    if has_admin:
        # Redirect to login if admin already exists
        return redirect('login')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        
        errors = []
        
        # Validation
        if not username:
            errors.append("Le nom d'utilisateur est requis")
        elif len(username) < 3:
            errors.append("Le nom d'utilisateur doit contenir au moins 3 caractères")
        elif User.objects.filter(username=username).exists():
            errors.append("Ce nom d'utilisateur existe déjà")

        if not email:
            errors.append("Le courriel est requis")
        elif '@' not in email:
            errors.append("Format de courriel invalide")

        if not password:
            errors.append("Le mot de passe est requis")
        elif len(password) < 10:
            errors.append("Le mot de passe doit contenir au moins 10 caractères")
        else:
            try:
                pseudo_user = User(username=username, email=email)
                validate_password(password, pseudo_user)
            except ValidationError as exc:
                errors.extend(exc.messages)

        if password != password_confirm:
            errors.append("Les mots de passe ne correspondent pas")
        
        if not errors:
            # Create admin user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='admin',
                org_group='direction',
                direction='metal_design',
            )
            user.is_superuser = True
            user.is_staff = True
            user.save()
            
            return render(request, 'setup_success.html', {
                'username': username,
                'email': email,
            })
        
        context = {
            'errors': errors,
            'form_data': request.POST,
        }
        return render(request, 'setup.html', context)
    
    return render(request, 'setup.html')


def quick_admin_create(request):
    """Quick admin creation endpoint for debugging/emergency setup.
    
    POST with: username, email, password
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode POST uniquement'}, status=400)

    if not settings.DEBUG:
        return JsonResponse({'error': 'Endpoint indisponible en production'}, status=403)
    
    # Check if admin already exists
    if User.objects.filter(is_superuser=True).exists():
        return JsonResponse({
            'error': 'Un compte administrateur existe déjà',
            'admin_count': User.objects.filter(is_superuser=True).count()
        }, status=400)
    
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '').strip()
    
    # Basic validation
    if not all([username, email, password]):
        return JsonResponse({'error': 'Nom d\'utilisateur, courriel ou mot de passe manquant'}, status=400)

    if len(username) < 3:
        return JsonResponse({'error': 'Nom d\'utilisateur trop court (min. 3 caractères)'}, status=400)

    if len(password) < 10:
        return JsonResponse({'error': 'Mot de passe trop court (min. 10 caractères)'}, status=400)
    
    try:
        # Create the admin user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='admin',
            org_group='direction',
            direction='metal_design',
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Compte administrateur « {username} » créé avec succès',
            'username': username,
            'email': email,
            'redirect': '/login/'
        })
    except Exception as e:
        return JsonResponse({'error': f'Échec de la création : {str(e)}'}, status=500)
