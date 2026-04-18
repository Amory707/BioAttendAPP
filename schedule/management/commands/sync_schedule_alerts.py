from datetime import datetime

from django.core.management.base import BaseCommand

from schedule.services import sync_schedule_alerts


class Command(BaseCommand):
    help = "Synchronise les alertes de retards, absences et journées trop courtes."

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, help='Date de début YYYY-MM-DD')
        parser.add_argument('--end', type=str, help='Date de fin YYYY-MM-DD')

    def handle(self, *args, **options):
        start_date = datetime.strptime(options['start'], '%Y-%m-%d').date() if options.get('start') else None
        end_date = datetime.strptime(options['end'], '%Y-%m-%d').date() if options.get('end') else None
        result = sync_schedule_alerts(start_date=start_date, end_date=end_date)
        self.stdout.write(self.style.SUCCESS(
            f"Synchronisation terminée : absences={result['absences']}, retards={result['retards']}, départs anticipés={result['early_departures']}, journées courtes={result['short_days']}"
        ))
