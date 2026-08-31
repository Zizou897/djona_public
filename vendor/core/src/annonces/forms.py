from django import forms

from .models import Annonce

MAX_PHOTOS = 4
# Doit rester alignée avec DATA_UPLOAD_MAX_MEMORY_SIZE/FILE_UPLOAD_MAX_MEMORY_SIZE
# (core/settings.py) et client_max_body_size (nginx, site vendor.djona.tech) —
# ces deux-là bornent la taille TOTALE de la requête (MAX_PHOTOS * MAX_PHOTO_SIZE
# + marge), pas la taille par fichier. La limite par image, elle, ne vit qu'ici.
MAX_PHOTO_SIZE = 4 * 1024 * 1024  # 4 Mo par image


class AnnonceForm(forms.ModelForm):
    class Meta:
        model = Annonce
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
            # AnnoncePhoto est créé directement par la vue via .objects.create(),
            # sans passer par un ModelForm — donc sans la validation Pillow que
            # forms.ImageField apporte normalement. On la déclenche ici pour
            # rejeter les fichiers non-image avant la sauvegarde.
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
