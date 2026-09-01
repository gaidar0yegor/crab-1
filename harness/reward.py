import re
import unicodedata
from typing import Dict, Optional
from difflib import SequenceMatcher

try:
    from harness.fr_geo import resolve_to_dept_code, resolve_to_region, region_from_dept
except Exception:  # allow running as a loose module
    from fr_geo import resolve_to_dept_code, resolve_to_region, region_from_dept


def normalize(s):
    if not s:
        return ''
    s = str(s)
    # strip accents so "Charleville-Mézières" matches "CHARLEVILLE-MEZIERES"
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r'https?://', '', s)
    s = re.sub(r'^www\.', '', s)
    s = s.rstrip('/')
    return s


def _domain(u):
    """Registrable domain of a URL/string: scheme/www/path stripped -> 'azmed.co'."""
    u = normalize(u)              # lowercases, strips scheme + leading www + trailing slash
    u = u.split('/')[0].split('?')[0]
    return u


def _domain_root(d):
    parts = [p for p in d.split('.') if p]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')


def website_score(predicted: str, expected: str) -> Optional[float]:
    """TLD-aware (D10 fix). Exact registrable domain -> 1.0; right company but
    wrong TLD/subdomain -> 0.5; otherwise 0.0. No fuzzy SequenceMatcher credit —
    that rewarded plausible hallucinations (a made-up .com scored ~0.38)."""
    if not expected:
        return None
    if not predicted:
        return 0.0
    p, e = _domain(predicted), _domain(expected)
    if not p:
        return 0.0
    if p == e:
        return 1.0
    # same second-level name (right company), different TLD/subdomain -> partial
    if _domain_root(p) and _domain_root(p) == _domain_root(e):
        return 0.5
    return 0.0


def sector_score(predicted: str, expected: str) -> Optional[float]:
    if not expected:
        return None
    if not predicted:
        return 0.0
    p = normalize(predicted)
    e = normalize(expected)
    if e in p or p in e or SequenceMatcher(None, p, e).ratio() > 0.6:
        return 1.0
    return 0.0


def city_score(predicted: Dict, expected: Dict) -> Optional[float]:
    """Score location, at the finest granularity the ground truth reliably supports.

    * If ``expected`` has a ``department_code`` (the eval set — derived from the
      official registry by SIREN, reliable), score at **department** granularity.
    * Else if ``expected`` has a ``region`` (the training lake — region from its
      own hand label, reliable; per-company departments-by-name are NOT), score
      at **region** granularity. This keeps region-correct trajectories even when
      the hand label's department is coarse/imprecise, while still dropping true
      wrong-company collisions (different region).
    * Else fall back to a lenient string match on ``city``.

    Returns None when there is no location ground truth (excluded from the mean).
    """
    pred_city = predicted.get('city')
    pred_dep = predicted.get('department_code') or resolve_to_dept_code(pred_city)
    has_pred = bool(pred_city or predicted.get('department_code'))

    exp_dep = expected.get('department_code')
    exp_region = expected.get('region')
    exp_city = expected.get('city')

    # Department granularity (reliable expected department).
    if exp_dep:
        if not has_pred:
            return 0.0
        if pred_dep:
            return 1.0 if pred_dep == exp_dep else 0.0
        # Prediction is a commune we can't map without a lookup — lenient match.
        p, e = normalize(pred_city), normalize(exp_city)
        return 1.0 if e and (e in p or p in e) else 0.0

    # Region granularity (reliable expected region only).
    if exp_region:
        if not has_pred:
            return 0.0
        pred_region = resolve_to_region(pred_city) or region_from_dept(pred_dep)
        if pred_region:
            return 1.0 if pred_region == exp_region else 0.0
        p, e = normalize(pred_city), normalize(exp_city)
        return 1.0 if e and (e in p or p in e) else 0.0

    # No structured location ground truth.
    if not exp_city:
        return None
    if not has_pred:
        return 0.0
    p, e = normalize(pred_city), normalize(exp_city)
    return 1.0 if e and (e in p or p in e) else 0.0


def compute_reward(predicted: Dict, expected: Dict) -> Dict:
    predicted = predicted or {}
    expected = expected or {}
    raw = {
        'website': website_score(predicted.get('website'), expected.get('website')),
        'sector': sector_score(predicted.get('sector'), expected.get('sector')),
        'city': city_score(predicted, expected),
    }
    # Only average over components that actually have ground truth.
    scored = {k: v for k, v in raw.items() if v is not None}
    core = sum(scored.values()) / len(scored) if scored else 0.0

    # Optional headcount: small bonus if present on both sides and consistent.
    bonus = 0.0
    if predicted.get('headcount') and expected.get('headcount'):
        p = normalize(predicted.get('headcount'))
        e = normalize(expected.get('headcount'))
        if e in p or p in e:
            bonus = 0.05

    total = min(1.0, core + bonus)
    return {
        'total': round(total, 3),
        'components': {k: (round(v, 3) if v is not None else None) for k, v in raw.items()},
        'scored_fields': sorted(scored.keys()),
        'passes_threshold': total >= 0.7,
        'bonus_headcount': round(bonus, 3),
    }
