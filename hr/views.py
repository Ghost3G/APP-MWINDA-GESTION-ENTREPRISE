from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.uploads import safe_filename, validate_attachment_upload

from .models import HRDocument, LeaveRequest
from .permissions import can_manage_hr_documents, can_review_leaves
from .services import build_hr_dashboard_stats, leave_balance_for, leave_queryset_for

User = get_user_model()


def _parse_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


@login_required(login_url='login')
def hr_dashboard(request):
    stats = build_hr_dashboard_stats()
    can_review = can_review_leaves(request.user)
    dept_labels = dict(User.DEPARTMENT_CHOICES)
    by_department = [
        {
            'org_group': row['org_group'],
            'label': dept_labels.get(row['org_group'], row['org_group'] or '—'),
            'total': row['total'],
        }
        for row in stats['by_department']
    ]
    return render(request, 'hr/dashboard.html', {
        **stats,
        'by_department': by_department,
        'can_review_leaves': can_review,
        'can_manage_hr_documents': can_manage_hr_documents(request.user),
    })


@login_required(login_url='login')
def hr_staff(request):
    q = request.GET.get('q', '').strip()
    org_group = request.GET.get('org_group', '').strip()
    users = User.objects.filter(is_active=True).order_by('org_group', 'first_name', 'username')
    if q:
        users = users.filter(
            models_q_name(q)
        )
    if org_group:
        users = users.filter(org_group=org_group)

    return render(request, 'hr/staff.html', {
        'staff_users': users,
        'search_q': q,
        'selected_org_group': org_group,
        'org_group_choices': User.DEPARTMENT_CHOICES,
        'total_staff': users.count(),
    })


def models_q_name(q):
    from django.db.models import Q
    return (
        Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(username__icontains=q)
        | Q(job_title__icontains=q)
        | Q(grade__icontains=q)
    )


@login_required(login_url='login')
def hr_leaves(request):
    can_review = can_review_leaves(request.user)
    status_filter = request.GET.get('status', '').strip()

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        if action == 'create':
            start = _parse_date(request.POST.get('start_date'))
            end = _parse_date(request.POST.get('end_date'))
            leave_type = request.POST.get('leave_type', LeaveRequest.TYPE_ANNUAL).strip()
            reason = request.POST.get('reason', '').strip()
            valid_types = {value for value, _ in LeaveRequest.TYPE_CHOICES}
            if leave_type not in valid_types:
                leave_type = LeaveRequest.TYPE_ANNUAL
            if not start or not end:
                messages.error(request, 'Indiquez les dates de début et de fin.')
            elif end < start:
                messages.error(request, 'La date de fin doit être après la date de début.')
            else:
                days = max((end - start).days + 1, 0)
                if leave_type == LeaveRequest.TYPE_ANNUAL:
                    balance = leave_balance_for(request.user, year=start.year)
                    if days > balance['remaining']:
                        messages.error(
                            request,
                            f'Solde insuffisant : {balance["remaining"]} j restant(s) '
                            f'sur {balance["allowance"]} j ({start.year}).',
                        )
                        return redirect('hr_leaves')
                LeaveRequest.objects.create(
                    user=request.user,
                    leave_type=leave_type,
                    start_date=start,
                    end_date=end,
                    reason=reason,
                )
                messages.success(request, 'Demande de congé envoyée.')
            return redirect('hr_leaves')

        if action in {'approve', 'reject'} and can_review:
            leave_id = request.POST.get('leave_id', '').strip()
            note = request.POST.get('review_note', '').strip()
            leave = get_object_or_404(LeaveRequest, id=leave_id)
            if leave.status != LeaveRequest.STATUS_PENDING:
                messages.error(request, 'Cette demande a déjà été traitée.')
            else:
                status = (
                    LeaveRequest.STATUS_APPROVED
                    if action == 'approve'
                    else LeaveRequest.STATUS_REJECTED
                )
                leave.mark_reviewed(request.user, status, note)
                messages.success(
                    request,
                    'Demande approuvée.' if action == 'approve' else 'Demande refusée.',
                )
            return redirect('hr_leaves')

        if action == 'cancel':
            leave_id = request.POST.get('leave_id', '').strip()
            leave = get_object_or_404(LeaveRequest, id=leave_id)
            if leave.user_id != request.user.id and not can_review:
                messages.error(request, 'Action non autorisée.')
            elif leave.status != LeaveRequest.STATUS_PENDING:
                messages.error(request, 'Seule une demande en attente peut être annulée.')
            else:
                leave.status = LeaveRequest.STATUS_CANCELLED
                leave.save(update_fields=['status', 'updated_at'])
                messages.success(request, 'Demande annulée.')
            return redirect('hr_leaves')

    leaves = leave_queryset_for(request.user, can_review=can_review)
    if status_filter in {value for value, _ in LeaveRequest.STATUS_CHOICES}:
        leaves = leaves.filter(status=status_filter)

    return render(request, 'hr/leaves.html', {
        'leaves': leaves[:100],
        'can_review_leaves': can_review,
        'leave_type_choices': LeaveRequest.TYPE_CHOICES,
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'selected_status': status_filter,
        'leave_balance': leave_balance_for(request.user),
    })


@login_required(login_url='login')
def hr_documents(request):
    can_manage = can_manage_hr_documents(request.user)

    if request.method == 'POST':
        if not can_manage:
            messages.error(request, 'Seul le DRH / admin peut gérer les documents RH.')
            return redirect('hr_documents')

        action = request.POST.get('action', '').strip()
        if action == 'upload':
            user_id = request.POST.get('user_id', '').strip()
            title = request.POST.get('title', '').strip()
            kind = request.POST.get('kind', HRDocument.KIND_OTHER).strip()
            notes = request.POST.get('notes', '').strip()
            upload = request.FILES.get('file')
            valid_kinds = {value for value, _ in HRDocument.KIND_CHOICES}
            if kind not in valid_kinds:
                kind = HRDocument.KIND_OTHER
            target = User.objects.filter(id=user_id, is_active=True).first() if user_id.isdigit() else None
            if not target:
                messages.error(request, 'Sélectionnez un collaborateur.')
            elif not title:
                messages.error(request, 'Indiquez un titre de document.')
            elif not upload:
                messages.error(request, 'Ajoutez un fichier.')
            else:
                error = validate_attachment_upload(upload)
                if error:
                    messages.error(request, error)
                else:
                    upload.name = safe_filename(getattr(upload, 'name', '') or 'document.pdf')
                    HRDocument.objects.create(
                        user=target,
                        title=title,
                        kind=kind,
                        file=upload,
                        notes=notes[:255],
                        uploaded_by=request.user,
                    )
                    messages.success(request, 'Document enregistré.')
            return redirect('hr_documents')

        if action == 'delete':
            doc_id = request.POST.get('document_id', '').strip()
            doc = get_object_or_404(HRDocument, id=doc_id)
            if doc.file:
                doc.file.delete(save=False)
            doc.delete()
            messages.success(request, 'Document supprimé.')
            return redirect('hr_documents')

    if can_manage:
        documents = HRDocument.objects.select_related('user', 'uploaded_by')
        staff_choices = User.objects.filter(is_active=True).order_by('first_name', 'username')
    else:
        documents = HRDocument.objects.filter(user=request.user).select_related('user', 'uploaded_by')
        staff_choices = []

    return render(request, 'hr/documents.html', {
        'documents': documents[:100],
        'can_manage_hr_documents': can_manage,
        'staff_choices': staff_choices,
        'kind_choices': HRDocument.KIND_CHOICES,
    })
