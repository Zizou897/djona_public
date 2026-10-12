from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from django import forms

from app.views import StaffRequisMixin

from .forms import (MAX_PHOTO_BYTES, MAX_PHOTOS, PartCategoryForm, PartForm, PartImportForm,
                    PartRequestFollowUpForm)
from .importer import COLUMNS, format_compatibilities, import_parts, replace_compatibilities, sample_csv
from .models import (PartCategoryMirror, PartImageMirror, PartMirror, PartRequestMirror)

DB = 'public_db'
PAGE_SIZE = 25


# ── Catalogue ────────────────────────────────────────────────────────────────

class PartListView(StaffRequisMixin, View):
    template_name = 'parts/part_liste.html'

    def get(self, request):
        qs = PartMirror.objects.using(DB).select_related('category')
        recherche = request.GET.get('q', '').strip()
        if recherche:
            qs = qs.filter(Q(name__icontains=recherche) | Q(reference__icontains=recherche)
                           | Q(manufacturer_reference__icontains=recherche) | Q(brand__icontains=recherche))
        categorie = request.GET.get('categorie', '')
        if categorie.isdigit():
            qs = qs.filter(category_id=int(categorie))
        visibilite = request.GET.get('visibilite', '')
        if visibilite == 'visibles':
            qs = qs.filter(is_active=True)
        elif visibilite == 'masquees':
            qs = qs.filter(is_active=False)
        page = Paginator(qs.order_by('name'), PAGE_SIZE).get_page(request.GET.get('page'))
        params = request.GET.copy()
        params.pop('page', None)
        return render(request, self.template_name, {
            'page_obj': page,
            'pieces': page.object_list,
            'categories': PartCategoryMirror.objects.using(DB).all(),
            'recherche': recherche,
            'categorie_active': categorie,
            'visibilite': visibilite,
            'querystring': params.urlencode(),
            'nb_total': PartMirror.objects.using(DB).count(),
        })


class PartFormMixin(StaffRequisMixin):
    template_name = 'parts/part_form.html'

    def render_form(self, request, form, part=None, errors_photos=None):
        return render(request, self.template_name, {
            'form': form, 'part': part, 'erreurs_photos': errors_photos or [],
            'images': list(PartImageMirror.objects.using(DB).filter(part=part)) if part else [],
            'max_photos': MAX_PHOTOS,
        })

    def clean_photos(self, request, part):
        """Valide les nouvelles photos ; retourne (fichiers, erreurs)."""
        files = request.FILES.getlist('photos')
        errors = []
        kept = 0
        if part:
            removed = set(request.POST.getlist('supprimer_photos'))
            kept = sum(1 for img in PartImageMirror.objects.using(DB).filter(part=part) if str(img.pk) not in removed)
        if kept + len(files) > MAX_PHOTOS:
            errors.append(f'{MAX_PHOTOS} photos maximum par pièce.')
        image_field = forms.ImageField()
        for upload in files:
            if upload.size > MAX_PHOTO_BYTES:
                errors.append(f'« {upload.name} » dépasse 4 Mo.')
                continue
            try:
                image_field.clean(upload)
            except ValidationError:
                errors.append(f'« {upload.name} » n\'est pas une image valide.')
        return files, errors

    def save_part(self, request, form, part=None):
        files, errors = self.clean_photos(request, part)
        if not form.is_valid() or errors:
            return None, errors
        new = form.save(commit=False)
        new.save(using=DB)
        replace_compatibilities(new, form.cleaned_data['compatibilities'])
        removed_ids = [int(i) for i in request.POST.getlist('supprimer_photos') if i.isdigit()]
        for img in PartImageMirror.objects.using(DB).filter(part=new, pk__in=removed_ids):
            img.image.delete(save=False)
            img.delete(using=DB)
        order = PartImageMirror.objects.using(DB).filter(part=new).count()
        for upload in files:
            PartImageMirror(part=new, image=upload, order=order).save(using=DB)
            order += 1
        return new, []


class PartCreateView(PartFormMixin, View):
    def get(self, request):
        return self.render_form(request, PartForm())

    def post(self, request):
        form = PartForm(request.POST)
        part, errors = self.save_part(request, form)
        if part is None:
            return self.render_form(request, form, errors_photos=errors)
        messages.success(request, f'Pièce « {part.name} » ajoutée.')
        return redirect('part_liste')


class PartUpdateView(PartFormMixin, View):
    def get_part(self, pk):
        return get_object_or_404(PartMirror.objects.using(DB).select_related('category'), pk=pk)

    def get(self, request, pk):
        part = self.get_part(pk)
        form = PartForm(instance=part, initial={
            'compatibilities': format_compatibilities(part.compatibilities.using(DB).all()),
        })
        return self.render_form(request, form, part)

    def post(self, request, pk):
        part = self.get_part(pk)
        form = PartForm(request.POST, instance=part)
        saved, errors = self.save_part(request, form, part)
        if saved is None:
            return self.render_form(request, form, part, errors)
        messages.success(request, f'Pièce « {saved.name} » mise à jour.')
        return redirect('part_liste')


class PostOnlyView(StaffRequisMixin, View):
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PartToggleView(PostOnlyView):
    def post(self, request, pk):
        part = get_object_or_404(PartMirror.objects.using(DB), pk=pk)
        part.is_active = not part.is_active
        part.save(using=DB, update_fields=['is_active', 'updated_at'])
        messages.success(request, f'« {part.name} » est désormais {"visible" if part.is_active else "masquée"} sur le site.')
        return redirect(request.POST.get('next') or 'part_liste')


class PartDeleteView(PostOnlyView):
    def post(self, request, pk):
        part = get_object_or_404(PartMirror.objects.using(DB), pk=pk)
        for img in PartImageMirror.objects.using(DB).filter(part=part):
            img.image.delete(save=False)
        name = part.name
        part.delete(using=DB)
        messages.success(request, f'Pièce « {name} » supprimée.')
        return redirect('part_liste')


# ── Catégories ───────────────────────────────────────────────────────────────

class PartCategoryListView(StaffRequisMixin, View):
    template_name = 'parts/categorie_liste.html'

    def render_page(self, request, form, erreurs=None):
        categories = PartCategoryMirror.objects.using(DB).annotate(nb=Count('parts'))
        return render(request, self.template_name, {'categories': categories, 'form': form, 'erreurs': erreurs or {}})

    def get(self, request):
        return self.render_page(request, PartCategoryForm())

    def post(self, request):
        form = PartCategoryForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, form)
        form.save(commit=False).save(using=DB)
        messages.success(request, 'Catégorie ajoutée.')
        return redirect('part_categorie_liste')


class PartCategoryUpdateView(PostOnlyView):
    def post(self, request, pk):
        category = get_object_or_404(PartCategoryMirror.objects.using(DB), pk=pk)
        form = PartCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save(commit=False).save(using=DB)
            messages.success(request, f'Catégorie « {category.name} » mise à jour.')
        else:
            erreur = ' '.join(e for errs in form.errors.values() for e in errs)
            messages.error(request, f'Catégorie non modifiée : {erreur}')
        return redirect('part_categorie_liste')


class PartCategoryToggleView(PostOnlyView):
    def post(self, request, pk):
        category = get_object_or_404(PartCategoryMirror.objects.using(DB), pk=pk)
        category.is_active = not category.is_active
        category.save(using=DB, update_fields=['is_active'])
        messages.success(request, f'« {category.name} » est désormais {"visible" if category.is_active else "masquée"} sur le site.')
        return redirect('part_categorie_liste')


# ── Demandes « pièce introuvable » ───────────────────────────────────────────

class PartRequestListView(StaffRequisMixin, View):
    template_name = 'parts/demande_liste.html'

    def get(self, request):
        qs = PartRequestMirror.objects.using(DB).select_related('part')
        statut = request.GET.get('statut', '')
        if statut in PartRequestMirror.Status.values:
            qs = qs.filter(status=statut)
        recherche = request.GET.get('q', '').strip()
        if recherche:
            qs = qs.filter(Q(reference__icontains=recherche) | Q(full_name__icontains=recherche)
                           | Q(phone__icontains=recherche) | Q(part_name__icontains=recherche)
                           | Q(make__icontains=recherche) | Q(model__icontains=recherche))
        rows = PartRequestMirror.objects.using(DB).values('status').annotate(n=Count('id'))
        counts = {row['status']: row['n'] for row in rows}
        return render(request, self.template_name, {
            'demandes': qs,
            'statuts': [{'value': v, 'label': l, 'count': counts.get(v, 0)} for v, l in PartRequestMirror.Status.choices],
            'statut_actif': statut,
            'recherche': recherche,
            'nb_total': sum(counts.values()),
        })


class PartRequestDetailView(StaffRequisMixin, View):
    template_name = 'parts/demande_detail.html'

    def get_demande(self, pk):
        return get_object_or_404(PartRequestMirror.objects.using(DB).select_related('part'), pk=pk)

    def get(self, request, pk):
        demande = self.get_demande(pk)
        return render(request, self.template_name, {'demande': demande, 'form': PartRequestFollowUpForm(instance=demande)})

    def post(self, request, pk):
        demande = self.get_demande(pk)
        form = PartRequestFollowUpForm(request.POST, instance=demande)
        if not form.is_valid():
            return render(request, self.template_name, {'demande': demande, 'form': form})
        form.save(commit=False).save(using=DB, update_fields=['status', 'proposed_price', 'proposed_lead_time',
                                                              'internal_note', 'updated_at'])
        messages.success(request, f'Demande {demande.reference} mise à jour.')
        return redirect('part_demande_detail', pk=pk)


# ── Import CSV ───────────────────────────────────────────────────────────────

class PartImportView(StaffRequisMixin, View):
    template_name = 'parts/import.html'

    def render_page(self, request, form, report=None):
        return render(request, self.template_name, {
            'form': form, 'report': report, 'colonnes': COLUMNS,
            'categories': PartCategoryMirror.objects.using(DB).all(),
        })

    def get(self, request):
        return self.render_page(request, PartImportForm())

    def post(self, request):
        form = PartImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_page(request, form)
        report = import_parts(form.cleaned_data['file'].read())
        if report.ok:
            messages.success(request, f'Import terminé : {report.created} pièce(s) créée(s), {report.updated} mise(s) à jour.')
        return self.render_page(request, PartImportForm(), report)


class PartImportSampleView(StaffRequisMixin, View):
    def get(self, request):
        response = HttpResponse(sample_csv(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="modele-import-pieces-djona.csv"'
        return response
