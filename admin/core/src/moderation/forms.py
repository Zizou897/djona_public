from django import forms

from .models import AnnonceMirror

MIN_PHOTOS = 3
MAX_PHOTOS = 4
# Doit rester cohérent avec la limite appliquée côté vendor
# (annonces/forms.py::MAX_PHOTO_SIZE) pour les annonces soumises par les
# vendeurs — mêmes règles ici pour celles créées directement par l'admin.
MAX_PHOTO_SIZE = 4 * 1024 * 1024  # 4 Mo par image


class AnnonceAdminForm(forms.ModelForm):
    class Meta:
        model = AnnonceMirror
        fields = [
            'marque', 'modele', 'annee', 'prix',
            'kilometrage', 'carburant', 'boite_vitesses', 'couleur',
            'etat', 'ville', 'description',
        ]

    def __init__(self, *args, exiger_photos_minimum=False, **kwargs):
        # True à la création : l'annonce est publiée tout de suite, elle doit donc
        # respecter le même minimum de photos qu'une annonce soumise par un vendeur
        # (vendor annonces/forms.py::MIN_PHOTOS).
        self.exiger_photos_minimum = exiger_photos_minimum
        super().__init__(*args, **kwargs)
        self.fields['etat'].required = True
        self.fields['ville'].required = True

    def clean(self):
        cleaned_data = super().clean()
        errors = []

        photos = self.files.getlist('photos')
        if self.exiger_photos_minimum and len(photos) < MIN_PHOTOS:
            errors.append(f"Ajoutez au moins {MIN_PHOTOS} photos pour publier l'annonce.")
        if len(photos) > MAX_PHOTOS:
            errors.append(f"Vous ne pouvez pas ajouter plus de {MAX_PHOTOS} photos.")
        else:
            image_field = forms.ImageField()
            for photo in photos:
                try:
                    image_field.clean(photo)
                except forms.ValidationError:
                    errors.append(f"« {photo.name} » n'est pas une image valide.")
                    continue

                if photo.size > MAX_PHOTO_SIZE:
                    taille_mo = photo.size / (1024 * 1024)
                    errors.append(
                        f"« {photo.name} » fait {taille_mo:.1f} Mo — chaque image doit faire 4 Mo maximum."
                    )

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_data
