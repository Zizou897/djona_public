from django import forms

from .models import AnnonceMirror

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
            'description',
        ]

    def clean(self):
        cleaned_data = super().clean()
        errors = []

        photos = self.files.getlist('photos')
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
