from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from parts.importer import import_parts, parse_compatibility, sample_csv
from parts.models import PartCategoryMirror, PartCompatibilityMirror, PartMirror

User = get_user_model()
DB = 'public_db'
HEADER = 'reference;designation;categorie;marque_piece;reference_fabricant;etat;prix;disponibilite;garantie;delai;description;compatibilites;visible;populaire'


class ParseTests(TestCase):
    def test_parse_compatibility(self):
        self.assertEqual(parse_compatibility('Toyota / Corolla / 2014 / 2019 / 1.6'),
                         {'make': 'Toyota', 'model': 'Corolla', 'year_from': 2014, 'year_to': 2019, 'engine': '1.6'})
        self.assertEqual(parse_compatibility('Peugeot')['model'], '')
        for bad in ('/Corolla', 'Toyota/Corolla/abcd', 'Toyota/Corolla/2020/2010', 'Toyota/Corolla/1800'):
            with self.assertRaises(ValueError):
                parse_compatibility(bad)

    def test_sample_file_is_importable_header(self):
        self.assertTrue(sample_csv().startswith('﻿reference;designation;categorie'))


class ImportTests(TestCase):
    databases = {'default', DB}

    def setUp(self):
        self.brake = PartCategoryMirror.objects.using(DB).create(name='Freinage import', order=90)
        self.filter = PartCategoryMirror.objects.using(DB).create(name='Filtration import', order=91)

    def tearDown(self):
        PartCompatibilityMirror.objects.using(DB).all().delete()
        PartMirror.objects.using(DB).filter(reference__startswith='IMP-').delete()
        PartCategoryMirror.objects.using(DB).filter(pk__in=[self.brake.pk, self.filter.pk]).delete()

    def csv(self, *rows, header=HEADER):
        return ('\n'.join([header, *rows]) + '\n').encode('utf-8')

    def test_creates_and_updates_with_tolerant_values(self):
        data = self.csv(
            'IMP-1;Plaquettes;freinage IMPORT;Bosch;04465-33450;Neuf;25 000 FCFA;à confirmer;;;;Toyota/Corolla/2014/2019|Toyota/Yaris;oui;non',
            'IMP-2;Filtre à huile;Filtration import;;;;;;;;;;;oui',
        )
        report = import_parts(data)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual((report.created, report.updated), (2, 0))
        part = PartMirror.objects.using(DB).get(reference='IMP-1')
        self.assertEqual((part.condition, part.price, part.availability), ('neuf', 25000, 'a_confirmer'))
        self.assertEqual(part.compatibilities.using(DB).count(), 2)
        bare = PartMirror.objects.using(DB).get(reference='IMP-2')
        self.assertEqual((bare.condition, bare.price, bare.availability), ('', None, 'a_confirmer'))
        self.assertTrue(bare.is_featured)

        again = import_parts(self.csv('imp-1;Plaquettes v2;Freinage import;;;occasion;18000;disponible;;;;;non;'))
        self.assertEqual((again.created, again.updated), (0, 1))
        part.refresh_from_db(using=DB)
        self.assertEqual((part.name, part.condition, part.price, part.is_active), ('Plaquettes v2', 'occasion', 18000, False))
        # Colonne compatibilités vide : les compatibilités existantes sont conservées.
        self.assertEqual(part.compatibilities.using(DB).count(), 2)

    def test_all_or_nothing_with_line_numbers(self):
        data = self.csv(
            'IMP-10;Valide;Freinage import;;;;;;;;;;;',
            'IMP-11;Mauvaise catégorie;Inconnue;;;;;;;;;;;',
            'IMP-12;Prix absurde;Freinage import;;;;beaucoup;;;;;;;',
            'IMP-10;Doublon;Freinage import;;;;;;;;;;;',
        )
        report = import_parts(data)
        self.assertFalse(report.ok)
        self.assertEqual(sorted(line for line, _ in report.errors), [3, 4, 5])
        self.assertFalse(PartMirror.objects.using(DB).filter(reference__startswith='IMP-').exists())

    def test_missing_required_column_and_encoding_and_delimiter(self):
        report = import_parts(b'reference;designation\nIMP-1;X\n')
        self.assertIn('categorie', report.errors[0][1])
        # Fichier Excel : virgule + Windows-1252.
        data = ('reference,designation,categorie\r\nIMP-20,Sélecteur,Freinage import\r\n').encode('cp1252')
        report = import_parts(data)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(PartMirror.objects.using(DB).get(reference='IMP-20').name, 'Sélecteur')

    def test_import_view_and_sample_download(self):
        admin = User.objects.create_user(username='admin-import', password='x', is_staff=True)
        self.client.force_login(admin)
        sample = self.client.get(reverse('part_import_modele'))
        self.assertEqual(sample['Content-Disposition'].split('=')[0], 'attachment; filename')
        upload = SimpleUploadedFile('pieces.csv', self.csv('IMP-30;Disque;Freinage import;;;;;;;;;;;'), content_type='text/csv')
        response = self.client.post(reverse('part_import'), {'file': upload})
        self.assertContains(response, 'Import terminé')
        self.assertTrue(PartMirror.objects.using(DB).filter(reference='IMP-30').exists())
        not_csv = SimpleUploadedFile('pieces.xlsx', b'x', content_type='application/vnd.ms-excel')
        response = self.client.post(reverse('part_import'), {'file': not_csv})
        self.assertContains(response, 'format CSV')
