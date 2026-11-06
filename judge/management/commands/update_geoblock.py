import ipaddress
import os
from datetime import date

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from judge.utils.geoblock import RANGES_FILE

APNIC_URL = 'https://ftp.apnic.net/stats/apnic/delegated-apnic-latest'


class Command(BaseCommand):
    help = ('Rewrites judge/utils/geoblock_ranges.txt with the address ranges of the countries in '
            'settings.REGISTRATION_BLOCKED_COUNTRIES, from the free APNIC allocation list (see judge/utils/geoblock.py).')

    def add_arguments(self, parser):
        parser.add_argument('--file', help='a copy of delegated-apnic-latest to read instead of downloading it')
        parser.add_argument('--countries', nargs='*', help='country codes (default: settings.REGISTRATION_BLOCKED_COUNTRIES)')

    def handle(self, *args, **options):
        countries = {c.upper() for c in (options['countries'] or settings.REGISTRATION_BLOCKED_COUNTRIES)}
        if not countries:
            raise CommandError('no countries to write')
        if options['file']:
            with open(options['file'], encoding='ascii', errors='ignore') as f:
                lines = f.read().splitlines()
        else:
            response = requests.get(APNIC_URL, timeout=120, headers={'User-Agent': 'joel-geoblock'})
            response.raise_for_status()
            lines = response.text.splitlines()

        out = []
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) < 7 or parts[0] != 'apnic' or parts[1] not in countries or parts[6] not in ('allocated', 'assigned'):
                continue
            if parts[2] == 'ipv4':
                first = ipaddress.IPv4Address(parts[3])
                last = ipaddress.IPv4Address(int(first) + int(parts[4]) - 1)
            elif parts[2] == 'ipv6':
                network = ipaddress.IPv6Network('%s/%s' % (parts[3], parts[4]), strict=False)
                first, last = network.network_address, network.broadcast_address
            else:
                continue
            out.append((parts[1], first, last))
        if not out:
            raise CommandError('the list has no ranges for %s: file left untouched' % ', '.join(sorted(countries)))
        out.sort(key=lambda r: (r[1].version, int(r[1])))

        tmp = RANGES_FILE + '.tmp'
        with open(tmp, 'w', encoding='ascii') as f:
            f.write('# Made by `manage.py update_geoblock` on %s from %s\n' % (date.today().isoformat(), options['file'] and os.path.basename(options['file']) or APNIC_URL))
            f.write('# Countries: %s\n' % ' '.join(sorted(countries)))
            for country, first, last in out:
                f.write('%s %s-%s\n' % (country, first, last))
        os.replace(tmp, RANGES_FILE)
        self.stdout.write('%d ranges for %s written to %s' % (len(out), ' '.join(sorted(countries)), RANGES_FILE))
