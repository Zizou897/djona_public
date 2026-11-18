from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connections
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analytics_live import alerts, stats
from analytics_live.models import AlertState, EventMirror, PresenceMirror

User = get_user_model()
DB = 'public_db'

# Les tables analytics_* appartiennent au projet public (jamais migrées ici) : les tests les créent eux-mêmes dans la
# base de test `public_db`, pour ne dépendre ni d'un `migrate` préalable du projet public ni de son état.


def setUpModule():
    with connections[DB].cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS analytics_event')
        cursor.execute('DROP TABLE IF EXISTS analytics_presence')
    with connections[DB].schema_editor() as editor:
        editor.create_model(EventMirror)
        editor.create_model(PresenceMirror)


def tearDownModule():
    with connections[DB].cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS analytics_event')
        cursor.execute('DROP TABLE IF EXISTS analytics_presence')


def event(type_='pageview', ago=timedelta(seconds=5), **fields):
    fields.setdefault('site', 'public')
    return EventMirror.objects.using(DB).create(type=type_, created_at=timezone.now() - ago, **fields)


def request_event(status=200, duration=100, ago=timedelta(seconds=5), **fields):
    return event('request', ago=ago, status_code=status, duration_ms=duration, path='/x/', **fields)


class StatsTests(TestCase):
    databases = {'default', DB}

    def test_visiteurs_en_ligne_dans_les_60_dernieres_secondes(self):
        now = timezone.now()
        PresenceMirror.objects.using(DB).create(session_id='recent-1', site='public', last_seen=now - timedelta(seconds=20))
        PresenceMirror.objects.using(DB).create(session_id='recent-2', site='public', last_seen=now - timedelta(seconds=59))
        PresenceMirror.objects.using(DB).create(session_id='ancien-1', site='public', last_seen=now - timedelta(seconds=90))
        self.assertEqual(stats.online_count(DB, now), 2)

    def test_pages_vues_par_minute(self):
        now = timezone.now().replace(second=30, microsecond=0)
        event(ago=timedelta(seconds=5))
        event(ago=timedelta(seconds=10))
        event(ago=timedelta(minutes=3))
        event(ago=timedelta(minutes=45))   # hors fenêtre
        event('request', ago=timedelta(seconds=5))   # pas une page vue
        points = stats.pageviews_by_minute(DB, now)
        self.assertEqual(len(points), stats.CHART_MINUTES)
        self.assertEqual(points[-1]['count'] + points[-2]['count'], 2)   # minute en cours (ou précédente selon l'horloge)
        self.assertEqual(sum(p['count'] for p in points), 3)

    def test_sante_des_requetes(self):
        for status, duration in [(200, 100), (200, 200), (200, 300), (404, 400), (500, 1000)]:
            request_event(status, duration)
        request_event(500, 9999, ago=timedelta(hours=1))   # hors fenêtre
        health = stats.request_health(DB)
        self.assertEqual((health['total'], health['errors_4xx'], health['errors_5xx']), (5, 1, 1))
        self.assertEqual((health['rate_4xx'], health['rate_5xx']), (20.0, 20.0))
        self.assertEqual((health['avg_ms'], health['p95_ms']), (400, 1000))

    def test_sante_sans_requete(self):
        self.assertEqual(stats.request_health(DB)['total'], 0)
        self.assertEqual(stats.request_health(DB)['p95_ms'], 0)

    def test_snapshot(self):
        event(session_id='s1' * 6, path='/vehicules/', device='mobile')
        event(session_id='s1' * 6, path='/vehicules/', device='mobile')
        event(session_id='s2' * 6, path='/', device='desktop', country='CI')
        event('action', name='commande_piece')
        event('action', name='commande_piece')
        event('action', name='clic_whatsapp')
        data = stats.snapshot('public')
        self.assertEqual((data['pageviews_today'], data['visitors_today'], data['actions_today']), (3, 2, 3))
        self.assertEqual(data['top_pages'][0], {'path': '/vehicules/', 'count': 2})
        self.assertEqual(data['actions'][0], {'name': 'commande_piece', 'label': 'Commande de pièces', 'count': 2})
        self.assertEqual({d['name']: d['count'] for d in data['devices']}, {'Mobile': 2, 'Ordinateur': 1})
        self.assertEqual(data['countries'], [{'name': 'CI', 'count': 1}])

    def test_flux_garde_les_actions_pages_vues_et_erreurs_seulement(self):
        request_event(200)
        error = request_event(500)
        action = event('action', name='message_contact', meta={'sujet': 'achat'})
        view = event('pageview', path='/a/')
        items = stats.feed('public')
        self.assertEqual({item['id'] for item in items}, {error.id, action.id, view.id})
        by_id = {item['id']: item for item in items}
        self.assertEqual(by_id[error.id]['kind'], 'error5xx')
        self.assertEqual(by_id[error.id]['label'], 'Erreur 500')
        self.assertEqual(by_id[action.id]['label'], 'Message de contact')
        self.assertIn('sujet : achat', by_id[action.id]['detail'])
        self.assertEqual([item['id'] for item in items], sorted(by_id, reverse=True))

    def test_flux_ne_renvoie_que_les_nouveautes(self):
        first = event('action', name='message_contact')
        newer = event('action', name='commande_piece')
        self.assertEqual([i['id'] for i in stats.feed('public', since=first.id)], [newer.id])
        self.assertEqual(stats.feed('public', since=newer.id), [])


class ViewsTests(TestCase):
    databases = {'default', DB}

    def setUp(self):
        self.staff = User.objects.create_user(username='staff-live', password='x', is_staff=True)
        self.client_user = User.objects.create_user(username='simple-live', password='x')

    def test_page_reservee_au_staff(self):
        for name in ('live_dashboard', 'live_stats', 'live_events'):
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('connexion_admin')}?next={url}")
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse('live_stats')).status_code, 302)

    def test_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('live_dashboard'))
        self.assertContains(response, 'Temps réel')
        self.assertContains(response, 'Espace vendeur')
        self.assertContains(response, 'temps_reel.js')

    def test_stats_json(self):
        event(path='/vehicules/', session_id='s1' * 6)
        self.client.force_login(self.staff)
        data = self.client.get(reverse('live_stats')).json()
        self.assertEqual(data['pageviews_today'], 1)
        self.assertEqual(len(data['chart']), stats.CHART_MINUTES)

    def test_site_inconnu(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('live_stats'), {'site': 'autre'}).status_code, 404)

    def test_base_indisponible_renvoie_503_sans_planter(self):
        self.client.force_login(self.staff)
        with mock.patch('analytics_live.stats.snapshot', side_effect=RuntimeError('table absente')):
            response = self.client.get(reverse('live_stats'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'unavailable': True})

    def test_evenements_json_et_parametre_since_invalide(self):
        item = event('action', name='commande_piece')
        self.client.force_login(self.staff)
        events = self.client.get(reverse('live_events'), {'since': 'abc'}).json()['events']
        self.assertEqual([e['id'] for e in events], [item.id])
        self.assertEqual(self.client.get(reverse('live_events'), {'since': item.id}).json()['events'], [])

    def test_lien_dans_la_navigation(self):
        self.client.force_login(self.staff)
        # Le tableau de bord principal interroge vendor_db ; la page « Temps réel » embarque la même navigation.
        response = self.client.get(reverse('live_dashboard'))
        self.assertContains(response, 'sensors</span>Temps réel')
        self.assertContains(response, 'aria-current="page"')


ALERT_SETTINGS = dict(
    ALERT_EMAILS=['equipe@djona.tech'], TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='',
    ALERT_COOLDOWN_MINUTES=60, ALERT_5XX_MIN_COUNT=3, ALERT_SLOW_P95_MS=2000, ALERT_MIN_REQUESTS=5,
    ALERT_TRAFFIC_DROP_PCT=80, ALERT_TRAFFIC_MIN_BASELINE=20, ALERT_HEALTH_FAILURES=2,
    ALERT_HEALTH_URLS={}, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)


@override_settings(**ALERT_SETTINGS)
class AlertTests(TestCase):
    databases = {'default', DB}

    def run_alerts(self, now=None):
        return alerts.run(now=now, sites=['public'])

    def spike(self, count=3):
        for _ in range(count):
            request_event(500, ago=timedelta(seconds=30))

    def actions(self, results, key):
        return [action for _, condition, action in results if condition.key == key]

    def test_aucune_alerte_sans_probleme(self):
        request_event(200)
        self.run_alerts()
        self.assertEqual(mail.outbox, [])
        self.assertFalse(AlertState.objects.filter(active=True).exists())

    def test_pic_derreurs_5xx_envoie_un_seul_email_puis_respecte_le_delai(self):
        self.spike()
        now = timezone.now()
        self.assertEqual(self.actions(self.run_alerts(now), 'erreurs_5xx'), ['ouverte'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pic d\'erreurs serveur', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['equipe@djona.tech'])

        # Même incident 10 minutes plus tard : pas de nouveau message (anti-spam).
        self.assertEqual(self.actions(self.run_alerts(now + timedelta(seconds=40)), 'erreurs_5xx'), [''])
        self.assertEqual(len(mail.outbox), 1)

    def test_rappel_apres_le_delai(self):
        self.spike()
        self.run_alerts()
        state = AlertState.objects.get(key='public:erreurs_5xx')
        state.last_sent_at = timezone.now() - timedelta(minutes=61)
        state.save()
        self.assertEqual(self.actions(self.run_alerts(), 'erreurs_5xx'), ['rappel'])
        self.assertEqual(len(mail.outbox), 2)

    def test_message_de_resolution_quand_tout_redevient_normal(self):
        self.spike()
        self.run_alerts()
        EventMirror.objects.using(DB).all().delete()
        self.assertEqual(self.actions(self.run_alerts(), 'erreurs_5xx'), ['resolue'])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('rétabli', mail.outbox[1].subject)
        state = AlertState.objects.get(key='public:erreurs_5xx')
        self.assertFalse(state.active)
        # Un nouvel incident est de nouveau signalé.
        self.spike()
        self.assertEqual(self.actions(self.run_alerts(), 'erreurs_5xx'), ['ouverte'])

    @override_settings(ALERT_EMAILS=[])
    def test_rien_nest_envoye_sans_canal_configure(self):
        self.spike()
        self.assertEqual(self.actions(self.run_alerts(), 'erreurs_5xx'), ['ouverte'])
        self.assertEqual(mail.outbox, [])
        self.assertEqual(alerts.channels(), [])

    @override_settings(TELEGRAM_BOT_TOKEN='123:secret', TELEGRAM_CHAT_ID='42')
    def test_telegram_et_email_ensemble(self):
        self.spike()
        with mock.patch('analytics_live.alerts._send_telegram') as telegram:
            self.run_alerts()
        telegram.assert_called_once()
        self.assertIn('Pic d\'erreurs', telegram.call_args.args[0])
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(TELEGRAM_BOT_TOKEN='123:secret', TELEGRAM_CHAT_ID='42')
    def test_un_canal_en_panne_nempeche_pas_lautre_et_ne_fuite_pas_le_jeton(self):
        self.spike()
        with mock.patch('analytics_live.alerts._send_telegram', side_effect=OSError('https://api.telegram.org/bot123:secret/…')):
            with self.assertLogs('analytics_live.alerts', level='ERROR') as logs:
                self.run_alerts()
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('123:secret', '\n'.join(logs.output))

    def test_dry_run_ninscrit_ni_nenvoie_rien(self):
        self.spike()
        results = alerts.run(sites=['public'], dry_run=True)
        self.assertEqual(self.actions(results, 'erreurs_5xx'), ['ouverte'])
        self.assertEqual(mail.outbox, [])
        self.assertEqual(AlertState.objects.count(), 0)

    def test_lenteur_necessite_un_volume_minimal(self):
        for _ in range(3):
            request_event(200, duration=9000)
        self.assertEqual(self.actions(self.run_alerts(), 'lenteur'), [''])
        for _ in range(3):
            request_event(200, duration=9000)
        self.assertEqual(self.actions(self.run_alerts(), 'lenteur'), ['ouverte'])

    def test_chute_de_trafic(self):
        # ~60 pages vues dans l'heure précédente (≈ 15 attendues par quart d'heure) : sous le plancher de 20.
        for minute in range(20, 70):
            event(ago=timedelta(minutes=minute))
        self.assertEqual(self.actions(self.run_alerts(), 'chute_trafic'), [''])

    @override_settings(ALERT_TRAFFIC_MIN_BASELINE=10)
    def test_chute_de_trafic_declenchee(self):
        for minute in range(20, 70):
            event(ago=timedelta(minutes=minute))
        # Rien sur les 15 dernières minutes alors que ~12 étaient attendues.
        self.assertEqual(self.actions(self.run_alerts(), 'chute_trafic'), ['ouverte'])

    @override_settings(ALERT_TRAFFIC_MIN_BASELINE=10)
    def test_pas_de_chute_si_le_trafic_continue(self):
        for minute in range(0, 70):
            event(ago=timedelta(minutes=minute, seconds=1))
        self.assertEqual(self.actions(self.run_alerts(), 'chute_trafic'), [''])

    @override_settings(ALERT_HEALTH_URLS={'public': 'https://djona.tech/'})
    def test_site_inaccessible_apres_deux_echecs_consecutifs(self):
        with mock.patch('analytics_live.alerts.ping', return_value=(False, 'timeout')):
            self.assertEqual(self.actions(self.run_alerts(), 'site_inaccessible'), [''])
            self.assertEqual(mail.outbox, [])
            self.assertEqual(self.actions(self.run_alerts(), 'site_inaccessible'), ['ouverte'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Site inaccessible', mail.outbox[0].subject)
        with mock.patch('analytics_live.alerts.ping', return_value=(True, 'HTTP 200')):
            self.assertEqual(self.actions(self.run_alerts(), 'site_inaccessible'), ['resolue'])

    @override_settings(ALERT_HEALTH_URLS={'public': 'https://djona.tech/'})
    def test_un_echec_isole_est_oublie(self):
        with mock.patch('analytics_live.alerts.ping', return_value=(False, 'timeout')):
            self.run_alerts()
        with mock.patch('analytics_live.alerts.ping', return_value=(True, 'HTTP 200')):
            self.run_alerts()
        with mock.patch('analytics_live.alerts.ping', return_value=(False, 'timeout')):
            self.assertEqual(self.actions(self.run_alerts(), 'site_inaccessible'), [''])
        self.assertEqual(mail.outbox, [])

    def test_ping_statut(self):
        class Response:
            status = 503
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch('urllib.request.urlopen', return_value=Response()):
            self.assertEqual(alerts.ping('https://x.test/'), (False, 'HTTP 503'))
        with mock.patch('urllib.request.urlopen', side_effect=OSError('refusé')):
            ok, detail = alerts.ping('https://x.test/')
        self.assertFalse(ok)
        self.assertIn('refusé', detail)

    def test_statistiques_indisponibles_ne_plante_pas(self):
        with mock.patch('analytics_live.stats.request_health', side_effect=RuntimeError('table absente')):
            with self.assertLogs('analytics_live.alerts', level='WARNING'):
                self.assertEqual(self.run_alerts(), [])
