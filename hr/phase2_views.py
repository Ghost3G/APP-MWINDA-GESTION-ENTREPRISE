from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from users.uploads import safe_filename, validate_attachment_upload

from .models import DisciplinaryAction, JobApplication, PerformanceReview, TrainingRecord
from .permissions import is_hr_manager

User = get_user_model()


def _parse_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _staff_choices():
    return User.objects.filter(is_active=True).order_by('first_name', 'username')


@login_required(login_url='login')
def hr_recruitment(request):
    can_manage = is_hr_manager(request.user)
    if not can_manage:
        from django.contrib import messages as django_messages
        django_messages.error(request, 'Le recrutement est réservé au DRH / administration.')
        return redirect('hr_dashboard')

    if request.method == 'POST' and can_manage:
        action = request.POST.get('action', '').strip()
        if action == 'create':
            full_name = request.POST.get('full_name', '').strip()
            position = request.POST.get('position', '').strip()
            if not full_name or not position:
                messages.error(request, 'Nom et poste sont requis.')
            else:
                upload = request.FILES.get('cv_file')
                if upload:
                    err = validate_attachment_upload(upload)
                    if err:
                        messages.error(request, err)
                        return redirect('hr_recruitment')
                    upload.name = safe_filename(getattr(upload, 'name', '') or 'cv.pdf')
                status = request.POST.get('status', JobApplication.STATUS_RECEIVED).strip()
                valid = {v for v, _ in JobApplication.STATUS_CHOICES}
                if status not in valid:
                    status = JobApplication.STATUS_RECEIVED
                JobApplication.objects.create(
                    full_name=full_name,
                    email=request.POST.get('email', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    position=position,
                    department=request.POST.get('department', '').strip(),
                    status=status,
                    source=request.POST.get('source', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    cv_file=upload if upload else None,
                    created_by=request.user,
                )
                messages.success(request, 'Candidature enregistrée.')
            return redirect('hr_recruitment')

        if action == 'update_status':
            app = get_object_or_404(JobApplication, id=request.POST.get('application_id'))
            status = request.POST.get('status', '').strip()
            valid = {v for v, _ in JobApplication.STATUS_CHOICES}
            if status in valid:
                app.status = status
                app.save(update_fields=['status', 'updated_at'])
                messages.success(request, 'Statut mis à jour.')
            return redirect('hr_recruitment')

        if action == 'delete':
            app = get_object_or_404(JobApplication, id=request.POST.get('application_id'))
            if app.cv_file:
                app.cv_file.delete(save=False)
            app.delete()
            messages.success(request, 'Candidature supprimée.')
            return redirect('hr_recruitment')

    status_filter = request.GET.get('status', '').strip()
    apps = JobApplication.objects.all()
    if status_filter in {v for v, _ in JobApplication.STATUS_CHOICES}:
        apps = apps.filter(status=status_filter)

    return render(request, 'hr/recruitment.html', {
        'applications': apps[:100],
        'can_manage': can_manage,
        'status_choices': JobApplication.STATUS_CHOICES,
        'selected_status': status_filter,
        'department_choices': User.DEPARTMENT_CHOICES,
    })


@login_required(login_url='login')
def hr_reviews(request):
    can_manage = is_hr_manager(request.user)

    if request.method == 'POST' and can_manage:
        action = request.POST.get('action', '').strip()
        if action == 'create':
            user_id = request.POST.get('user_id', '').strip()
            review_date = _parse_date(request.POST.get('review_date'))
            target = User.objects.filter(id=user_id, is_active=True).first() if user_id.isdigit() else None
            rating_raw = request.POST.get('rating', '3').strip()
            try:
                rating = int(rating_raw)
            except ValueError:
                rating = 3
            if rating not in {1, 2, 3, 4, 5}:
                rating = 3
            if not target or not review_date:
                messages.error(request, 'Collaborateur et date sont requis.')
            else:
                PerformanceReview.objects.create(
                    user=target,
                    review_date=review_date,
                    period_label=request.POST.get('period_label', '').strip(),
                    rating=rating,
                    strengths=request.POST.get('strengths', '').strip(),
                    improvements=request.POST.get('improvements', '').strip(),
                    goals=request.POST.get('goals', '').strip(),
                    reviewer=request.user,
                )
                messages.success(request, 'Évaluation enregistrée.')
            return redirect('hr_reviews')

        if action == 'delete':
            review = get_object_or_404(PerformanceReview, id=request.POST.get('review_id'))
            review.delete()
            messages.success(request, 'Évaluation supprimée.')
            return redirect('hr_reviews')

    if can_manage:
        reviews = PerformanceReview.objects.select_related('user', 'reviewer')
    else:
        reviews = PerformanceReview.objects.filter(user=request.user).select_related('user', 'reviewer')

    return render(request, 'hr/reviews.html', {
        'reviews': reviews[:100],
        'can_manage': can_manage,
        'staff_choices': _staff_choices() if can_manage else [],
        'rating_choices': PerformanceReview.RATING_CHOICES,
    })


@login_required(login_url='login')
def hr_trainings(request):
    can_manage = is_hr_manager(request.user)

    if request.method == 'POST' and can_manage:
        action = request.POST.get('action', '').strip()
        if action == 'create':
            user_id = request.POST.get('user_id', '').strip()
            title = request.POST.get('title', '').strip()
            target = User.objects.filter(id=user_id, is_active=True).first() if user_id.isdigit() else None
            status = request.POST.get('status', TrainingRecord.STATUS_PLANNED).strip()
            valid = {v for v, _ in TrainingRecord.STATUS_CHOICES}
            if status not in valid:
                status = TrainingRecord.STATUS_PLANNED
            if not target or not title:
                messages.error(request, 'Collaborateur et intitulé sont requis.')
            else:
                TrainingRecord.objects.create(
                    user=target,
                    title=title,
                    provider=request.POST.get('provider', '').strip(),
                    start_date=_parse_date(request.POST.get('start_date')),
                    end_date=_parse_date(request.POST.get('end_date')),
                    status=status,
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.user,
                )
                messages.success(request, 'Formation enregistrée.')
            return redirect('hr_trainings')

        if action == 'update_status':
            record = get_object_or_404(TrainingRecord, id=request.POST.get('training_id'))
            status = request.POST.get('status', '').strip()
            valid = {v for v, _ in TrainingRecord.STATUS_CHOICES}
            if status in valid:
                record.status = status
                record.save(update_fields=['status'])
                messages.success(request, 'Statut formation mis à jour.')
            return redirect('hr_trainings')

        if action == 'delete':
            record = get_object_or_404(TrainingRecord, id=request.POST.get('training_id'))
            record.delete()
            messages.success(request, 'Formation supprimée.')
            return redirect('hr_trainings')

    if can_manage:
        records = TrainingRecord.objects.select_related('user', 'created_by')
    else:
        records = TrainingRecord.objects.filter(user=request.user).select_related('user', 'created_by')

    return render(request, 'hr/trainings.html', {
        'trainings': records[:100],
        'can_manage': can_manage,
        'staff_choices': _staff_choices() if can_manage else [],
        'status_choices': TrainingRecord.STATUS_CHOICES,
    })


@login_required(login_url='login')
def hr_sanctions(request):
    can_manage = is_hr_manager(request.user)

    if request.method == 'POST' and can_manage:
        action = request.POST.get('action', '').strip()
        if action == 'create':
            user_id = request.POST.get('user_id', '').strip()
            action_date = _parse_date(request.POST.get('action_date'))
            reason = request.POST.get('reason', '').strip()
            kind = request.POST.get('kind', DisciplinaryAction.KIND_WARNING).strip()
            valid = {v for v, _ in DisciplinaryAction.KIND_CHOICES}
            if kind not in valid:
                kind = DisciplinaryAction.KIND_WARNING
            target = User.objects.filter(id=user_id, is_active=True).first() if user_id.isdigit() else None
            if not target or not action_date or not reason:
                messages.error(request, 'Collaborateur, date et motif sont requis.')
            else:
                DisciplinaryAction.objects.create(
                    user=target,
                    kind=kind,
                    action_date=action_date,
                    reason=reason,
                    decision=request.POST.get('decision', '').strip(),
                    recorded_by=request.user,
                )
                messages.success(request, 'Sanction / avertissement enregistré.')
            return redirect('hr_sanctions')

        if action == 'delete':
            item = get_object_or_404(DisciplinaryAction, id=request.POST.get('sanction_id'))
            item.delete()
            messages.success(request, 'Enregistrement supprimé.')
            return redirect('hr_sanctions')

    if can_manage:
        items = DisciplinaryAction.objects.select_related('user', 'recorded_by')
    else:
        items = DisciplinaryAction.objects.filter(user=request.user).select_related('user', 'recorded_by')

    return render(request, 'hr/sanctions.html', {
        'sanctions': items[:100],
        'can_manage': can_manage,
        'staff_choices': _staff_choices() if can_manage else [],
        'kind_choices': DisciplinaryAction.KIND_CHOICES,
    })
