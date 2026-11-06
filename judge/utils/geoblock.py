"""
Country blocking for the registration form (and only it: people who already have an account log in from anywhere).

The spam that registers thousands of accounts comes from a few countries where the site has no users at all, so
`settings.REGISTRATION_BLOCKED_COUNTRIES` lists them and the registration page refuses requests from their addresses.
The address ranges of each country are in `geoblock_ranges.txt` (one `CC first-last` per line), made by
`manage.py update_geoblock` from the free per-country allocation list of APNIC. The file only holds the countries that
were in the setting when it was made, so after adding one to the setting, run the command again; taking one out of
the setting is enough to lift its block.
"""
import bisect
import ipaddress
import logging
import os

from django.conf import settings

logger = logging.getLogger('judge.registration')

RANGES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geoblock_ranges.txt')

_ranges = None


def _load():
    """Sorted `(first, last, country)` lists for IPv4 and IPv6, read once."""
    global _ranges
    if _ranges is None:
        v4, v6 = [], []
        try:
            with open(RANGES_FILE, encoding='ascii') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    country, span = line.split()
                    first, last = (ipaddress.ip_address(part) for part in span.split('-'))
                    (v4 if first.version == 4 else v6).append((int(first), int(last), country))
        except (OSError, ValueError):
            logger.exception('could not read %s: nobody is blocked by country', RANGES_FILE)
        v4.sort()
        v6.sort()
        _ranges = (v4, [r[0] for r in v4], v6, [r[0] for r in v6])
    return _ranges


def country_of(ip):
    """The country code of `ip` if it is in a range of the file, else None."""
    try:
        address = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return None
    v4, starts4, v6, starts6 = _load()
    ranges, starts = (v4, starts4) if address.version == 4 else (v6, starts6)
    i = bisect.bisect_right(starts, int(address)) - 1
    if i >= 0 and ranges[i][0] <= int(address) <= ranges[i][1]:
        return ranges[i][2]
    return None


def is_blocked(ip):
    """Whether `ip` is in a country the registration is closed to."""
    return country_of(ip) in set(getattr(settings, 'REGISTRATION_BLOCKED_COUNTRIES', ()))
