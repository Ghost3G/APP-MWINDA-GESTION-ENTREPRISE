from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from projects.models import AgentTimeEntry, ProjectTask
from .security import (
    clear_failed_attempts,
    get_client_ip,
    is_login_locked,
    record_login_attempt,
    write_audit_log,
)
from .permissions import is_admin_user, is_management_user, management_required
from .uploads import validate_avatar_upload, store_user_avatar

User = get_user_model()


def _format_seconds(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        client_ip = get_client_ip(request)

        if is_login_locked(username, client_ip):
            return render(
                request,
                'login.html',
                {'error': "Compte temporairement bloqué. Réessayez dans 15 minutes."}
            )

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Après la fin de service : les agents peuvent se reconnecter (consultation / urgente).
            # La présence du jour (arrivées + départ fin de service) reste intacte en base.
            record_login_attempt(username, client_ip, True)
            clear_failed_attempts(username, client_ip)
            login(request, user)
            write_audit_log(user, "login_success", path=request.path, method="POST")
            try:
                has_open_work = AgentTimeEntry.objects.filter(
                    user=user,
                    entry_type='work',
                    ended_at__isnull=True,
                ).exists()
                if not has_open_work:
                    AgentTimeEntry.objects.create(
                        user=user,
                        entry_type='work',
                        started_at=timezone.now(),
                    )
            except Exception:
                # Silently continue if AgentTimeEntry creation fails (e.g., migrations not run)
                pass
            return redirect('dashboard')
        else:
            record_login_attempt(username, client_ip, False)
            return render(request, 'login.html', {'error': 'Identifiants invalides'})
    
    return render(request, 'login.html')


@require_http_methods(["GET", "POST"])
def logout_view(request):
    # Préférer POST+CSRF ; GET conservé temporairement pour compatibilité liens anciens
    if request.user.is_authenticated:
        now = timezone.now()
        open_entries = AgentTimeEntry.objects.filter(
            user=request.user,
            entry_type__in=['work', 'pause', 'task'],
            ended_at__isnull=True,
        )
        for entry in open_entries:
            elapsed = int((now - entry.started_at).total_seconds())
            entry.duration_seconds = entry.duration_seconds + max(elapsed, 0)
            entry.ended_at = now
            entry.save(update_fields=['duration_seconds', 'ended_at'])

    write_audit_log(request.user, "logout", path=request.path, method=request.method)
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def profile_view(request):
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action', 'update')

        if action == 'remove_avatar':
            if user.avatar:
                try:
                    user.avatar.delete(save=False)
                except Exception:
                    # Cloudinary / stockage : ne pas bloquer la suppression en base
                    pass
                user.avatar = None
                user.save(update_fields=['avatar'])
            messages.success(request, 'Photo de profil supprimée.')
            return redirect('profile')

        if action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, 'Mot de passe actuel incorrect.')
                return redirect('profile')
            if len(new_password) < 10:
                messages.error(request, 'Le nouveau mot de passe doit contenir au moins 10 caractères.')
                return redirect('profile')
            if new_password != confirm_password:
                messages.error(request, 'La confirmation ne correspond pas.')
                return redirect('profile')
            try:
                validate_password(new_password, user)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                return redirect('profile')

            user.set_password(new_password)
            user.save(update_fields=['password'])
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            messages.success(request, 'Mot de passe mis à jour.')
            return redirect('profile')

        first_name = request.POST.get('first_name', '').strip()[:150]
        last_name = request.POST.get('last_name', '').strip()[:150]
        phone = request.POST.get('phone', '').strip()
        avatar_file = request.FILES.get('avatar')

        if len(phone) > 40:
            messages.error(request, 'Le numéro de téléphone est trop long (40 caractères max).')
            return redirect('profile')

        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone

        if avatar_file:
            avatar_error = validate_avatar_upload(avatar_file)
            if avatar_error:
                messages.error(request, avatar_error)
                return redirect('profile')

            # Sauver d'abord les champs texte, puis la photo
            try:
                user.save(update_fields=['first_name', 'last_name', 'phone'])
            except Exception:
                pass

            upload_error = store_user_avatar(user, avatar_file)
            if upload_error:
                messages.error(request, upload_error)
                return redirect('profile')

            messages.success(request, 'Profil et photo mis à jour avec succès.')
            return redirect('profile')

        try:
            user.save()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Échec enregistrement profil')
            messages.error(request, "Impossible d’enregistrer le profil. Réessayez.")
            return redirect('profile')

        messages.success(request, 'Profil mis à jour avec succès.')
        return redirect('profile')

    return render(request, 'profile.html', {
        'profile_user': user,
    })


@login_required(login_url='login')
def users_directory(request):
    is_management = is_management_user(request.user)
    is_admin = is_admin_user(request.user)

    if request.method == 'POST':
        if not is_admin:
            messages.error(request, "Vous n'avez pas la permission de gérer les utilisateurs.")
            return redirect('users_list')

        action = request.POST.get('action', 'create').strip()

        if action == 'delete':
            user_id = request.POST.get('user_id', '').strip()
            delete_confirm = request.POST.get('delete_confirm', '').strip().upper()

            if delete_confirm != 'SUPPRIMER':
                messages.error(request, "Confirmation invalide. Tapez SUPPRIMER pour confirmer.")
                return redirect('users_list')

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                messages.error(request, "Utilisateur introuvable.")
                return redirect('users_list')

            if user.id == request.user.id:
                messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
                return redirect('users_list')

            if user.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
                messages.error(request, "Impossible de supprimer le dernier administrateur.")
                return redirect('users_list')

            username = user.username
            user.delete()
            messages.success(request, f"Utilisateur « {username} » supprimé.")
            write_audit_log(
                request.user,
                'user_delete',
                path=request.path,
                method='POST',
                metadata={'target_username': username, 'target_user_id': user_id},
            )
            return redirect('users_list')

        if action == 'update':
            user_id = request.POST.get('user_id', '').strip()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                messages.error(request, "Utilisateur introuvable.")
                return redirect('users_list')

            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            role = request.POST.get('role', user.role).strip() or user.role
            org_group = (
                request.POST.get('department', '').strip()
                or request.POST.get('org_group', user.org_group).strip()
                or user.org_group
            )
            direction = request.POST.get('direction', user.direction).strip() or user.direction
            competency_profile = (
                request.POST.get('competency_profile', user.competency_profile).strip()
                or user.competency_profile
            )
            password = request.POST.get('password', '')
            is_active = request.POST.get('is_active') == 'on'

            errors = []
            if not email:
                errors.append("L'email est requis.")
            elif User.objects.filter(email=email).exclude(id=user.id).exists():
                errors.append("Cet email est déjà utilisé.")

            valid_roles = [value for value, _ in User.ROLE_CHOICES]
            valid_departments = [value for value, _ in User.DEPARTMENT_CHOICES]
            valid_directions = [value for value, _ in User.DIRECTION_CHOICES]
            valid_competencies = [value for value, _ in User.COMPETENCY_PROFILE_CHOICES]
            if role not in valid_roles:
                errors.append("Le rôle sélectionné est invalide.")
            if org_group not in valid_departments:
                errors.append("Le département sélectionné est invalide.")
            if direction not in valid_directions:
                errors.append("La branche sélectionnée est invalide.")
            if competency_profile not in valid_competencies:
                errors.append("La compétence principale sélectionnée est invalide.")

            if user.id == request.user.id and role != 'admin':
                errors.append("Vous ne pouvez pas retirer votre propre rôle administrateur.")

            if password and len(password) < 10:
                errors.append("Le mot de passe doit contenir au moins 10 caractères.")

            if password:
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    errors.extend(exc.messages)

            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect('users_list')

            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.role = role
            user.org_group = org_group
            user.direction = direction
            user.competency_profile = competency_profile
            user.is_active = is_active
            if password:
                user.set_password(password)
            user.save()
            messages.success(request, f"Utilisateur « {user.username} » mis à jour.")
            return redirect('users_list')

        # action == 'create'
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'agent').strip() or 'agent'
        org_group = (
            request.POST.get('department', '').strip()
            or request.POST.get('org_group', 'technique').strip()
            or 'technique'
        )
        direction = request.POST.get('direction', 'metal_design').strip() or 'metal_design'
        competency_profile = request.POST.get('competency_profile', 'auto').strip() or 'auto'

        errors = []
        if not username:
            errors.append("Le nom d'utilisateur est requis.")
        elif User.objects.filter(username=username).exists():
            errors.append("Ce nom d'utilisateur existe déjà.")

        if not email:
            errors.append("L'email est requis.")
        elif User.objects.filter(email=email).exists():
            errors.append("Cet email existe déjà.")

        valid_roles = [value for value, _ in User.ROLE_CHOICES]
        valid_departments = [value for value, _ in User.DEPARTMENT_CHOICES]
        valid_directions = [value for value, _ in User.DIRECTION_CHOICES]
        valid_competencies = [value for value, _ in User.COMPETENCY_PROFILE_CHOICES]
        if role not in valid_roles:
            errors.append("Le rôle sélectionné est invalide.")
        if org_group not in valid_departments:
            errors.append("Le département sélectionné est invalide.")
        if direction not in valid_directions:
            errors.append("La branche sélectionnée est invalide.")
        if competency_profile not in valid_competencies:
            errors.append("La compétence principale sélectionnée est invalide.")
        if not password:
            errors.append("Le mot de passe est requis.")
        elif len(password) < 10:
            errors.append("Le mot de passe doit contenir au moins 10 caractères.")
        else:
            try:
                # validate against configured Django validators
                pseudo_user = User(username=username, email=email, first_name=first_name, last_name=last_name)
                validate_password(password, pseudo_user)
            except ValidationError as exc:
                errors.extend(exc.messages)

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('users_list')

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
            org_group=org_group,
            direction=direction,
            competency_profile=competency_profile,
        )
        messages.success(request, "Utilisateur créé avec succès.")
        write_audit_log(
            request.user,
            'user_create',
            path=request.path,
            method='POST',
            metadata={'username': username, 'role': role},
        )
        return redirect('users_list')

    users = User.objects.all().order_by('username')

    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    org_group = (
        request.GET.get('department', '').strip()
        or request.GET.get('org_group', '').strip()
    )
    direction = request.GET.get('direction', '').strip()

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    if role:
        users = users.filter(role=role)

    if org_group:
        users = users.filter(org_group=org_group)

    if direction:
        users = users.filter(direction=direction)

    count_qs = User.objects.all().order_by()
    if query:
        count_qs = count_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )
    if role:
        count_qs = count_qs.filter(role=role)
    if direction:
        count_qs = count_qs.filter(direction=direction)

    department_counts = dict(
        count_qs.values('org_group').annotate(total=Count('id')).values_list('org_group', 'total')
    )
    department_tabs = [
        {
            'value': value,
            'label': label,
            'count': department_counts.get(value, 0),
        }
        for value, label in User.DEPARTMENT_CHOICES
    ]
    total_agents_count = count_qs.count()

    now = timezone.now()
    for user in users:
        entries = AgentTimeEntry.objects.filter(user=user)

        task_entries = entries.filter(entry_type='task', ended_at__isnull=False)
        task_durations = [entry.duration_seconds for entry in task_entries]
        avg_task_seconds = int(sum(task_durations) / len(task_durations)) if task_durations else 0
        total_task_seconds = sum(task_durations)

        work_entries = entries.filter(entry_type='work')
        work_seconds = sum(
            (entry.duration_seconds + max(int((now - entry.started_at).total_seconds()), 0))
            if entry.ended_at is None else entry.duration_seconds
            for entry in work_entries
        )
        pause_entries = entries.filter(entry_type='pause')
        pause_seconds = sum(
            (entry.duration_seconds + max(int((now - entry.started_at).total_seconds()), 0))
            if entry.ended_at is None else entry.duration_seconds
            for entry in pause_entries
        )

        performance = int(min(100, round((total_task_seconds / work_seconds) * 100))) if work_seconds else 0

        user.performance_score = performance
        user.avg_task_time = _format_seconds(avg_task_seconds)
        user.work_time_total = _format_seconds(work_seconds)
        user.pause_time_total = _format_seconds(pause_seconds)

        user_tasks = ProjectTask.objects.filter(assigned_to=user)
        user.task_pending = user_tasks.filter(status='pending').count()
        user.task_in_progress = user_tasks.filter(status='in_progress').count()
        user.task_done = user_tasks.filter(status='done').count()
        user.task_total = user_tasks.count()
        user.current_task = user_tasks.filter(status='in_progress').order_by('-updated_at').first()

    full_name = request.user.get_display_name()
    profile_progress = 75
    current_project = {
        'title': 'Conception logo 3D',
        'description': 'Aperçu sur la description du projet en cours',
        'button_text': 'OUVRIR',
    }
    tasks = [
        {'label': 'Conception du logo', 'active': True},
        {'label': 'Préparation du fichier de découpe', 'active': False},
        {'label': 'Relecture du brief', 'active': False},
    ]
    time_stats = [
        {'label': 'T. sur une tâche', 'value': '00:01:54', 'highlight': True},
        {'label': 'Temps de travail', 'value': '04:01:54'},
        {'label': 'Temps de pause', 'value': '00:00:00'},
    ]

    context = {
        'users': users,
        'query': query,
        'selected_role': role,
        'selected_department': org_group,
        'selected_org_group': org_group,
        'selected_direction': direction,
        'role_choices': User.ROLE_CHOICES,
        'department_choices': User.DEPARTMENT_CHOICES,
        'org_group_choices': User.DEPARTMENT_CHOICES,
        'department_tabs': department_tabs,
        'org_group_tabs': department_tabs,
        'total_agents_count': total_agents_count,
        'direction_choices': User.DIRECTION_CHOICES,
        'competency_profile_choices': User.COMPETENCY_PROFILE_CHOICES,
        'full_name': full_name,
        'profile_progress': profile_progress,
        'current_project': current_project,
        'tasks': tasks,
        'time_stats': time_stats,
        'is_admin': is_admin,
        'is_management': is_management,
    }
    return render(request, 'users.html', context)


@login_required(login_url='login')
def presence_dashboard(request):
    """Présence : direction voit tout le monde ; agent voit uniquement sa fiche."""
    from .presence import (
        SCHEDULE_SUMMARY_LABEL,
        build_agent_login_chart,
        build_agent_presence_summary,
        build_agent_rhythm_charts,
        build_presence_sessions,
        parse_presence_date,
        work_schedule_for_day,
    )

    can_view_all = is_management_user(request.user)
    selected_date = parse_presence_date(request.GET.get('date', '').strip())
    selected_month = selected_date.strftime('%Y-%m')

    if can_view_all:
        visible_users = list(
            User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        )
        agent_id_raw = request.GET.get('agent', '').strip()
        selected_agent = None
        if agent_id_raw.isdigit():
            selected_agent = next((u for u in visible_users if u.id == int(agent_id_raw)), None)
        # Pas de fiche par défaut : on ouvre uniquement après clic sur un nom.
        agent_explicit = selected_agent is not None
    else:
        visible_users = [request.user]
        selected_agent = request.user
        agent_explicit = True

    sessions = build_presence_sessions(selected_date)
    summary = build_agent_presence_summary(selected_date, visible_users)
    present_count = sum(1 for row in summary if row['present_today'])
    absent_count = sum(1 for row in summary if not row['present_today'])
    late_count = sum(1 for row in summary if row.get('arrival_status') == 'late')
    online_count = sum(
        1 for row in summary
        if row['present_today'] and row.get('departure_status') == 'online'
    )

    agent_day_sessions = []
    agent_day_summary = None
    if selected_agent:
        agent_day_sessions = [row for row in sessions if row['user'].id == selected_agent.id]
        agent_day_summary = next(
            (row for row in summary if row['user'].id == selected_agent.id),
            None,
        )

    chart_data = {'labels': [], 'counts': [], 'total': 0}
    day_schedule = work_schedule_for_day(selected_date)
    rhythm_data = {
        'labels': [],
        'arrival_hours': [],
        'departure_hours': [],
        'arrival_ref': [],
        'departure_ref': [],
        'presence_flags': [],
        'work_start': day_schedule.start_hour if day_schedule.is_open else 8.5,
        'work_end': day_schedule.end_hour if day_schedule.is_open else 17.5,
        'work_start_label': day_schedule.start_label if day_schedule.is_open else '08:30',
        'work_end_label': day_schedule.end_label if day_schedule.is_open else '17:30',
        'stats': {},
        'absence_chart': {'labels': ['Présents', 'Absents'], 'values': [0, 0]},
    }
    if selected_agent:
        chart_data = build_agent_login_chart(selected_agent, selected_date, days=14)
        rhythm_data = build_agent_rhythm_charts(selected_agent, selected_date, days=14)

    return render(request, 'presence.html', {
        'selected_date': selected_date.isoformat(),
        'selected_month': selected_month,
        'is_today': selected_date == timezone.localdate(),
        'agents': visible_users,
        'selected_agent': selected_agent,
        'agent_explicit': agent_explicit,
        'agent_day_sessions': agent_day_sessions,
        'agent_day_summary': agent_day_summary,
        'summary': summary if can_view_all else [],
        'present_count': present_count,
        'online_count': online_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'chart_data': chart_data,
        'rhythm_data': rhythm_data,
        'work_start_label': day_schedule.start_label if day_schedule.is_open else '08:30',
        'work_end_label': day_schedule.end_label if day_schedule.is_open else '17:30',
        'day_schedule_open': day_schedule.is_open,
        'day_schedule_label': day_schedule.range_label,
        'schedule_summary_label': SCHEDULE_SUMMARY_LABEL,
        'can_view_all_presence': can_view_all,
    })


def _presence_can_access_agent(request, agent_id):
    """Direction : tout le monde. Agent : uniquement son propre dossier."""
    if is_management_user(request.user):
        return True
    return int(agent_id) == request.user.id


def _presence_monthly_payload(request, agent_id):
    from .presence import build_agent_monthly_sessions, parse_presence_date, parse_presence_month

    if not _presence_can_access_agent(request, agent_id):
        return None

    try:
        agent = User.objects.get(pk=agent_id, is_active=True)
    except User.DoesNotExist:
        return None

    fallback = parse_presence_date(request.GET.get('date', '').strip())
    year, month = parse_presence_month(request.GET.get('month', '').strip(), fallback)
    return build_agent_monthly_sessions(agent, year, month)


@login_required(login_url='login')
def presence_pdf(request, agent_id):
    from django.http import HttpResponse, HttpResponseForbidden
    from .pdf import build_presence_monthly_pdf

    if not _presence_can_access_agent(request, agent_id):
        return HttpResponseForbidden("Vous ne pouvez consulter que votre propre présence.")

    payload = _presence_monthly_payload(request, agent_id)
    if not payload:
        return HttpResponseForbidden('Agent introuvable')

    pdf_bytes = build_presence_monthly_pdf(payload)
    filename = f"presence_{payload['agent'].username}_{payload['year']}{payload['month']:02d}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
def presence_a4_view(request, agent_id):
    from django.http import HttpResponseForbidden

    if not _presence_can_access_agent(request, agent_id):
        return HttpResponseForbidden("Vous ne pouvez consulter que votre propre présence.")

    payload = _presence_monthly_payload(request, agent_id)
    if not payload:
        return HttpResponseForbidden('Agent introuvable')

    return render(request, 'presence_a4.html', {
        **payload,
        'selected_month': f"{payload['year']}-{payload['month']:02d}",
    })

