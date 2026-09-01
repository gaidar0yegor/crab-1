import json
import time
import urllib.request
import urllib.parse
from typing import Dict, List, Optional


class OSINTTools:
    """Minimal toolset for company OSINT profiling.

    web_search uses DuckDuckGo (ddgs), web_extract uses trafilatura,
    registry_lookup queries the official French company registry
    (recherche-entreprises.api.gouv.fr). All live services: results
    drift over time — see the README's note on benchmark perishability.
    """

    def __init__(self):
        self.history = []
        self._duckduckgo = None

    def log(self, action: str, input_data: dict, output_data: dict):
        self.history.append({
            'timestamp': time.time(),
            'action': action,
            'input': input_data,
            'output': output_data,
        })

    def _load_duckduckgo(self):
        if self._duckduckgo is None:
            try:
                from ddgs import DDGS
                self._duckduckgo = DDGS()
            except Exception:
                self._duckduckgo = False
        return self._duckduckgo if self._duckduckgo else None

    def web_search(self, query: str, limit: int = 5) -> Dict:
        """Search the web for a query."""
        ddgs = self._load_duckduckgo()
        if ddgs:
            try:
                results = ddgs.text(query, max_results=limit)
                normalized = [{'title': r.get('title', ''), 'url': r.get('href', ''),
                               'description': r.get('body', '')} for r in results]
                out = {'success': True, 'results': normalized}
            except Exception as e:
                out = {'success': False, 'error': str(e)}
        else:
            out = {'success': False, 'error': 'no search backend available (pip install ddgs)'}
        self.log('web_search', {'query': query, 'limit': limit}, out)
        return out

    def web_extract(self, urls: List[str], char_limit: int = 3000) -> Dict:
        """Extract clean text content from URLs."""
        out = {'success': True, 'results': []}
        import requests
        import trafilatura
        for url in urls:
            try:
                r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0 (Crab-1 bot)'})
                text = trafilatura.extract(r.text, include_comments=False, include_tables=False,
                                           deduplicate=True, url=url)
                out['results'].append({'url': url, 'content': (text or '')[:char_limit]})
            except Exception as e:
                out['results'].append({'url': url, 'content': '', 'error': str(e)})
        self.log('web_extract', {'urls': urls}, out)
        return out

    def registry_lookup(self, company_name: str) -> Dict:
        """Query the official French registry (recherche-entreprises.api.gouv.fr).
        Returns SIREN, SIRET, legal name, NAF/sector code, city, headcount range.
        """
        encoded = urllib.parse.quote(company_name)
        url = f"https://recherche-entreprises.api.gouv.fr/search?q={encoded}&page=1&per_page=5"
        try:
            data = urllib.request.urlopen(url, timeout=15).read().decode()
            j = json.loads(data)
            results = j.get('results', [])
            if not results:
                out = {'success': False, 'error': 'no registry results'}
            else:
                best = results[0]
                siege = best.get('siege', {})
                out = {
                    'success': True,
                    'count': len(results),
                    'results': results,
                    'top': {
                        'legal_name': best.get('nom_complet'),
                        'siren': best.get('siren'),
                        'siret': siege.get('siret'),
                        'naf': best.get('activite_principale'),
                        'sector': best.get('libelle_activite_principale'),
                        'city': siege.get('libelle_commune'),
                        'department': siege.get('departement'),
                        'region_code': siege.get('region'),
                        'postal_code': siege.get('code_postal'),
                        'headcount_code': best.get('tranche_effectif_salarie'),
                    },
                }
        except Exception as e:
            out = {'success': False, 'error': str(e)}
        self.log('registry_lookup', {'company': company_name}, out)
        return out

    def headcount_from_code(self, code: str) -> Optional[str]:
        """Map French tranche_effectif_salarie code to a human range."""
        mapping = {
            '00': '0 salarié', '01': '1-2 salariés', '02': '3-5 salariés',
            '03': '6-9 salariés', '11': '10-19 salariés', '12': '20-49 salariés',
            '21': '50-99 salariés', '22': '100-199 salariés', '31': '200-249 salariés',
            '32': '250-499 salariés', '41': '500-999 salariés', '42': '1000-1999 salariés',
            '51': '2000-4999 salariés', '52': '5000-9999 salariés', '53': '10000+ salariés',
            'NN': None,
        }
        return mapping.get(code)
