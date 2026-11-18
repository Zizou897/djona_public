import json
from datetime import date, datetime, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.models import Utilisateur

from . import utils
from .aggregates import aggregate_day, percentile
from .models import DailyStat, Event, Presence

BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'
PHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1'
SID = 'abcdef0123456789abcdef'
KEY = 'cle-de-test'

enabled = override_settings(ANALYTICS_SITE_KEY=KEY, ANALYTICS_ASYNC=False)


class UtilsTests(TestCase):
    def test_anonymize_ip_v4_tronque_le_dernier_octet(self):
        self.assertEqual(utils.anonymize_ip('41.202.219.77'), '41.202.219.0')

    def test_anonymize_ip_v6_garde_le_prefixe_48(self):
        self.assertEqual(utils.anonymize_ip('2001:db8:abcd:1234:5678::1'), '2001:db8:abcd::/48')

    def test_anonymize_ip_illisible(self):
        self.assertEqual(utils.anonymize_ip('pas-une-ip'), '')
        self.assertEqual(utils.anonymize_ip(''), '')

    def test_appareil(self):
        self.assertEqual(utils.device_from_user_agent(BROWSER), 'desktop')
        self.assertEqual(utils.device_from_user_agent(PHONE), 'mobile')
        self.assertEqual(utils.device_from_user_agent('Mozilla/5.0 (iPad; CPU OS 17_0)'), 'tablet')

    def test_robots(self):
        for ua in ('', 'Googlebot/2.1', 'curl/8.4.0', 'python-requests/2.31', 'UptimeRobot/2.0'):
            self.assertTrue(utils.is_bot(ua), ua)
        self.assertFalse(utils.is_bot(BROWSER))

    def test_meta_ecarte_les_cles_personnelles_et_borne_les_valeurs(self):
        meta = utils.clean_meta({
            'slug': 'toyota-yaris', 'phone': '0700000000', 'email': 'a@b.c', 'password': 'x', 'nom_client': 'Koffi',
            'total': 12000, 'long': 'x' * 500, 'objet': {'imbrique': 1}, 'ok': True,
        })
        self.assertEqual(set(meta), {'slug', 'total', 'long', 'ok'})
        self.assertEqual(len(meta['long']), utils.MAX_META_VALUE_LENGTH)

    def test_meta_limitee_a_dix_cles(self):
        self.assertEqual(len(utils.clean_meta({f'k{i}': i for i in range(30)})), utils.MAX_META_KEYS)

    def test_chemin_sans_parametres(self):
        self.assertEqual(utils.clean_path('/vehicules/?q=toyota#haut'), '/vehicules/')

    def test_percentile(self):
        self.assertEqual(percentile([], 95), 0)
        self.assertEqual(percentile(list(range(1, 101)), 95), 95)
        self.assertEqual(percentile([7], 95), 7)


@enabled
class MiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()

    def get(self, url, ua=BROWSER, **extra):
        return self.client.get(url, HTTP_USER_AGENT=ua, **extra)

    def test_enregistre_statut_et_duree(self):
        self.client.cookies['djona_sid'] = SID
        self.get(reverse('connexion_vendeur'))
        event = Event.objects.get(type='request')
        self.assertEqual(event.path, reverse('connexion_vendeur'))
        self.assertEqual(event.status_code, 200)
        self.assertIsNotNone(event.duration_ms)
        self.assertEqual(event.session_id, SID)
        self.assertEqual(event.device, 'desktop')
        self.assertEqual(event.site, 'vendor')

    def test_404_enregistre_avec_son_statut(self):
        self.get('/page-qui-nexiste-pas/')
        self.assertEqual(Event.objects.get(type='request').status_code, 404)

    def test_ip_anonymisee(self):
        self.get(reverse('connexion_vendeur'), REMOTE_ADDR='41.202.219.77')
        self.assertEqual(Event.objects.get(type='request').ip_anon, '41.202.219.0')

    def test_ignore_statiques_admin_et_collecte(self):
        for url in ('/static/js/analytics.js', '/admin/login/', '/robots.txt', '/analytics/collect/'):
            self.get(url)
        self.assertEqual(Event.objects.count(), 0)

    def test_ignore_les_robots(self):
        self.get(reverse('connexion_vendeur'), ua='Googlebot/2.1 (+http://www.google.com/bot.html)')
        self.client.get(reverse('connexion_vendeur'))  # sans User-Agent
        self.assertEqual(Event.objects.count(), 0)

    def test_inactif_sans_cle_de_site(self):
        with override_settings(ANALYTICS_SITE_KEY=''):
            self.get(reverse('connexion_vendeur'))
        self.assertEqual(Event.objects.count(), 0)

    def test_une_panne_du_suivi_ne_casse_pas_la_page(self):
        with mock.patch('analytics.buffer.EventBuffer.add_event', side_effect=RuntimeError('base HS')):
            response = self.get(reverse('connexion_vendeur'))
        self.assertEqual(response.status_code, 200)

    def test_une_panne_dbase_pendant_lecriture_ne_casse_pas_la_page(self):
        with mock.patch('analytics.models.Event.objects') as manager:
            manager.bulk_create.side_effect = RuntimeError('MySQL has gone away')
            response = self.get(reverse('connexion_vendeur'))
        self.assertEqual(response.status_code, 200)


@enabled
class CollectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('analytics:collect')

    def post(self, payload, ua=BROWSER, **extra):
        body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        return self.client.post(self.url, data=body, content_type='text/plain', HTTP_USER_AGENT=ua, **extra)

    def payload(self, **overrides):
        data = {'k': KEY, 'sid': SID, 't': 'pageview', 'p': '/vehicules/'}
        data.update(overrides)
        return data

    def test_page_vue_enregistree_avec_presence(self):
        response = self.post(self.payload(r='https://www.google.com/search?q=djona'), REMOTE_ADDR='41.202.219.77')
        self.assertEqual(response.status_code, 204)
        event = Event.objects.get(type='pageview')
        self.assertEqual((event.path, event.session_id, event.ip_anon), ('/vehicules/', SID, '41.202.219.0'))
        self.assertEqual(event.meta, {'ref': 'www.google.com'})
        self.assertEqual(Presence.objects.get(session_id=SID).path, '/vehicules/')

    def test_heartbeat_met_a_jour_la_presence_sans_creer_devenement(self):
        self.post(self.payload(t='heartbeat', p='/a/'))
        self.post(self.payload(t='heartbeat', p='/b/'))
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Presence.objects.count(), 1)
        self.assertEqual(Presence.objects.get().path, '/b/')

    def test_action_metier(self):
        self.post(self.payload(t='action', n='clic_whatsapp', m={'phone': '0700000000', 'page': 'detail'}))
        action = Event.objects.get(type='action')
        self.assertEqual(action.name, 'clic_whatsapp')
        self.assertEqual(action.meta, {'page': 'detail'})

    def test_nom_daction_invalide_ignore(self):
        for name in ('Nom Avec Espaces', '', None, 'x' * 80, '<script>'):
            self.post(self.payload(t='action', n=name))
        self.assertEqual(Event.objects.count(), 0)

    def test_mauvaise_cle_refusee(self):
        self.assertEqual(self.post(self.payload(k='autre')).status_code, 403)
        self.assertEqual(self.post({'sid': SID, 't': 'pageview', 'p': '/'}).status_code, 403)
        self.assertEqual(Event.objects.count(), 0)

    def test_get_refuse(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_json_invalide(self):
        self.assertEqual(self.post('{pas du json').status_code, 400)
        self.assertEqual(self.post('[1, 2]').status_code, 400)

    def test_corps_trop_gros(self):
        self.assertEqual(self.post(self.payload(m={'a': 'x' * 3000})).status_code, 413)

    def test_robot_ignore(self):
        self.assertEqual(self.post(self.payload(), ua='Googlebot/2.1').status_code, 204)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Presence.objects.count(), 0)

    def test_session_ou_chemin_invalides_ignores(self):
        self.post(self.payload(sid='court'))
        self.post(self.payload(p='http://evil.example/'))
        self.post(self.payload(p='/admin/'))
        self.post(self.payload(t='inconnu'))
        self.assertEqual(Event.objects.count(), 0)

    def test_limitation_de_debit(self):
        with mock.patch('analytics.views.RATE_LIMIT', 3):
            codes = [self.post(self.payload()).status_code for _ in range(5)]
        self.assertEqual(codes, [204, 204, 204, 429, 429])

    def test_inactif_sans_cle_de_site(self):
        with override_settings(ANALYTICS_SITE_KEY=''):
            self.assertEqual(self.post(self.payload()).status_code, 404)

    def test_sans_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, data=json.dumps(self.payload()), content_type='text/plain', HTTP_USER_AGENT=BROWSER)
        self.assertEqual(response.status_code, 204)


@enabled
class SignalTests(TestCase):
    def test_inscription_vendeur_enregistree_sans_donnee_personnelle(self):
        Utilisateur.objects.create_user(
            email='koffi@example.ci', password='motdepasse-solide', nom='Yao', prenom='Koffi', telephone='0700000000',
        )
        action = Event.objects.get(name='inscription_vendeur')
        self.assertEqual((action.type, action.meta), ('action', {'type_compte': 'particulier'}))
        dumped = json.dumps(list(Event.objects.values('path', 'meta')))
        for secret in ('koffi', 'Yao', '0700000000'):
            self.assertNotIn(secret, dumped)

    def test_modification_nest_pas_une_creation(self):
        user = Utilisateur.objects.create_user(
            email='a@example.ci', password='motdepasse-solide', nom='A', prenom='B', telephone='0700000001',
        )
        user.nom = 'Autre'
        user.save()
        self.assertEqual(Event.objects.filter(name='inscription_vendeur').count(), 1)

    @override_settings(ANALYTICS_SITE_KEY='')
    def test_inactif_sans_cle_de_site(self):
        Utilisateur.objects.create_user(
            email='b@example.ci', password='motdepasse-solide', nom='A', prenom='B', telephone='0700000002',
        )
        self.assertEqual(Event.objects.count(), 0)


@enabled
class AggregateAndPurgeTests(TestCase):
    def event(self, when, type_='request', status=200, duration=100, session='', name=''):
        return Event.objects.create(
            type=type_, status_code=status if type_ == 'request' else None,
            duration_ms=duration if type_ == 'request' else None, session_id=session, name=name,
            path='/x/', created_at=when,
        )

    def noon(self, day):
        return timezone.make_aware(datetime.combine(day, datetime.min.time())) + timedelta(hours=12)

    def test_aggregate_day(self):
        day = date(2026, 3, 10)
        when = self.noon(day)
        self.event(when, 'pageview', session='s1' * 4)
        self.event(when, 'pageview', session='s1' * 4)
        self.event(when, 'pageview', session='s2' * 4)
        self.event(when, 'action', name='commande_piece')
        for index, (status, duration) in enumerate([(200, 100), (200, 200), (404, 300), (500, 400)]):
            self.event(when + timedelta(seconds=index), status=status, duration=duration)
        self.event(self.noon(day + timedelta(days=1)), 'pageview', session='autre-jour')

        stat = aggregate_day(day, 'vendor')
        self.assertEqual(
            (stat.pageviews, stat.visitors, stat.actions, stat.requests, stat.errors_4xx, stat.errors_5xx),
            (3, 2, 1, 4, 1, 1),
        )
        self.assertEqual((stat.avg_duration_ms, stat.p95_duration_ms), (250, 400))

    def test_aggregate_day_est_idempotent(self):
        day = date(2026, 3, 10)
        self.event(self.noon(day), 'pageview', session='s1' * 4)
        aggregate_day(day, 'vendor')
        aggregate_day(day, 'vendor')
        self.assertEqual(DailyStat.objects.count(), 1)

    def test_purge_agrege_puis_supprime_les_vieux_evenements(self):
        old_day = timezone.localdate() - timedelta(days=120)
        self.event(self.noon(old_day), 'pageview', session='s1' * 4)
        self.event(self.noon(old_day), 'pageview', session='s2' * 4)
        recent = self.event(timezone.now() - timedelta(days=2), 'pageview', session='s3' * 4)
        Presence.objects.create(session_id='viellesession', last_seen=timezone.now() - timedelta(hours=3))
        Presence.objects.create(session_id='sessionactive', last_seen=timezone.now())

        out = StringIO()
        call_command('purge_events', stdout=out)

        self.assertEqual(list(Event.objects.all()), [recent])
        self.assertEqual(DailyStat.objects.get(date=old_day).pageviews, 2)
        self.assertEqual(list(Presence.objects.values_list('session_id', flat=True)), ['sessionactive'])

    def test_purge_ne_recalcule_pas_un_jour_deja_fige(self):
        old_day = timezone.localdate() - timedelta(days=120)
        DailyStat.objects.create(site='vendor', date=old_day, pageviews=999)
        self.event(self.noon(old_day), 'pageview', session='s1' * 4)
        call_command('purge_events', stdout=StringIO())
        self.assertEqual(DailyStat.objects.get(date=old_day).pageviews, 999)
        self.assertEqual(Event.objects.count(), 0)

    def test_purge_respecte_l_option_days(self):
        self.event(timezone.now() - timedelta(days=10), 'pageview', session='s1' * 4)
        call_command('purge_events', '--days', '5', stdout=StringIO())
        self.assertEqual(Event.objects.count(), 0)
