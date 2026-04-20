from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage
from schedule.forms import ScheduleRequestForm
from schedule.models import ScheduleRequest
from schedule.services import build_pointage_feedback, get_schedule_settings, sync_schedule_alerts


class ScheduleFeatureTests(TestCase):
    def setUp(self):
        self.role_employee = Role.objects.create(nom='employé')
        self.role_admin = Role.objects.create(nom='admin')

        self.employee = Utilisateur.objects.create_user(
            username='employe1',
            email='emp@example.com',
            password='test-pass-123',
            first_name='Alice',
            last_name='Martin',
        )
        self.admin = Utilisateur.objects.create_user(
            username='rh1',
            email='rh@example.com',
            password='test-pass-123',
            first_name='Rita',
            last_name='HR',
        )

        RoleUtilisateur.objects.create(role=self.role_employee, utilisateur=self.employee)
        RoleUtilisateur.objects.create(role=self.role_admin, utilisateur=self.admin)

    def _weekday_in_past(self):
        target_day = timezone.localdate() - timedelta(days=1)
        while target_day.weekday() >= 5:
            target_day -= timedelta(days=1)
        return target_day

    def test_employee_submission_creates_pending_request(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse('schedule:submit'),
            {
                'start_at': '2026-04-20T09:00',
                'end_at': '2026-04-20T17:00',
                'category': ScheduleRequest.CATEGORY_CONGE,
                'description': 'Congé familial',
            },
        )

        self.assertEqual(response.status_code, 302)
        request_obj = ScheduleRequest.objects.get(utilisateur=self.employee)
        self.assertEqual(request_obj.status, ScheduleRequest.STATUS_PENDING)
        self.assertEqual(request_obj.category, ScheduleRequest.CATEGORY_CONGE)

    def test_schedule_home_displays_global_switch_status(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('schedule:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activation du module absences et retards')

    def test_admin_schedule_home_displays_settings_button(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['active_dashboard_space'] = 'admin'
        session.save()

        response = self.client.get(reverse('schedule:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configurer les seuils')

    def test_admin_settings_page_is_accessible(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['active_dashboard_space'] = 'admin'
        session.save()

        response = self.client.get(reverse('schedule:settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paramètres de contrôle')
        self.assertContains(response, 'Retard après')

    def test_retard_is_not_available_in_manual_form_choices(self):
        form = ScheduleRequestForm(actor=self.employee, is_admin=False)
        choice_values = {value for value, _ in form.fields['category'].choices}

        self.assertNotIn(ScheduleRequest.CATEGORY_RETARD, choice_values)

    def test_sync_schedule_alerts_creates_absence_for_unjustified_day(self):
        target_day = self._weekday_in_past()

        sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[self.employee])

        self.assertTrue(Alerte.objects.filter(utilisateur=self.employee, type='ABSENCE').exists())

    def test_approved_leave_prevents_absence_alert(self):
        target_day = self._weekday_in_past()
        start_at = timezone.make_aware(datetime.combine(target_day, time(9, 0)))
        end_at = timezone.make_aware(datetime.combine(target_day, time(17, 0)))
        ScheduleRequest.objects.create(
            utilisateur=self.employee,
            created_by=self.admin,
            reviewed_by=self.admin,
            status=ScheduleRequest.STATUS_APPROVED,
            category=ScheduleRequest.CATEGORY_CONGE,
            start_at=start_at,
            end_at=end_at,
        )

        sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[self.employee])

        self.assertFalse(Alerte.objects.filter(utilisateur=self.employee, type='ABSENCE').exists())

    def test_build_pointage_feedback_marks_short_day_and_early_departure(self):
        target_day = self._weekday_in_past()
        entry = Pointage.objects.create(
            utilisateur=self.employee,
            statut='VALIDE',
            horodatage=timezone.make_aware(datetime.combine(target_day, time(10, 30))),
            type='ENTREE',
            score_confiance=0.95,
        )
        exit_pointage = Pointage.objects.create(
            utilisateur=self.employee,
            statut='VALIDE',
            horodatage=timezone.make_aware(datetime.combine(target_day, time(15, 0))),
            type='SORTIE',
            score_confiance=0.96,
        )

        build_pointage_feedback(entry)
        feedback = build_pointage_feedback(exit_pointage)

        self.assertIn('DEPART_ANTICIPE', feedback['flags'])
        self.assertIn('JOURNEE_COURTE', feedback['flags'])
        self.assertTrue(Alerte.objects.filter(utilisateur=self.employee, type='RETARD').exists())

    def test_zero_worked_hours_is_classified_as_absence(self):
        target_day = self._weekday_in_past()
        Pointage.objects.create(
            utilisateur=self.employee,
            statut='VALIDE',
            horodatage=timezone.make_aware(datetime.combine(target_day, time(10, 30))),
            type='ENTREE',
            score_confiance=0.95,
        )

        sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[self.employee])

        self.assertTrue(Alerte.objects.filter(utilisateur=self.employee, type='ABSENCE').exists())
        self.assertFalse(Alerte.objects.filter(utilisateur=self.employee, type='JOURNEE_COURTE').exists())
        self.assertFalse(Alerte.objects.filter(utilisateur=self.employee, type='RETARD').exists())

    def test_disabled_switch_prevents_schedule_alerts(self):
        settings_obj = get_schedule_settings()
        settings_obj.is_enabled = False
        settings_obj.save(update_fields=['is_enabled', 'updated_at'])
        target_day = self._weekday_in_past()

        result = sync_schedule_alerts(start_date=target_day, end_date=target_day, users=[self.employee])

        self.assertEqual(result['absences'], 0)
        self.assertFalse(Alerte.objects.exists())
