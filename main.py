import argparse
import json
from time import sleep
from datetime import datetime, timezone
from os import environ
from pathlib import Path

import jwt as JWT
import requests
import arxiv
from dateutil.parser import isoparse


arxiv_categories = set(['cs.AI', 'cs.CL', 'cs.CC', 'cs.CE', 'cs.CG', 'cs.GT', 'cs.CV', 'cs.CY', 'cs.CR', 'cs.DS', 'cs.DB', 'cs.DL', 'cs.DM', 'cs.DC', 'cs.ET', 'cs.FL', 'cs.GL', 'cs.GR', 'cs.AR', 'cs.HC', 'cs.IR', 'cs.IT', 'cs.LO', 'cs.LG', 'cs.MS', 'cs.MA', 'cs.MM', 'cs.NI', 'cs.NE', 'cs.NA', 'cs.OS', 'cs.OH', 'cs.PF', 'cs.PL', 'cs.RO', 'cs.SI', 'cs.SE', 'cs.SD', 'cs.SC', 'cs.SY', 'econ.EM', 'econ.GN', 'econ.TH', 'eess.AS', 'eess.IV', 'eess.SP', 'eess.SY', 'math.AG', 'math.AT', 'math.AP', 'math.CT', 'math.CA', 'math.CO', 'math.AC', 'math.CV', 'math.DG', 'math.DS', 'math.FA', 'math.GM', 'math.GN', 'math.GT', 'math.GR', 'math.HO', 'math.IT', 'math.KT', 'math.LO', 'math.MP', 'math.MG', 'math.NT', 'math.NA', 'math.OA', 'math.OC', 'math.PR', 'math.QA', 'math.RT', 'math.RA', 'math.SP', 'math.ST', 'math.SG', 'astro-ph.GA', 'astro-ph.CO', 'astro-ph.EP', 'astro-ph.HE', 'astro-ph.IM', 'astro-ph.SR', 'cond-mat.dis-nn', 'cond-mat.mtrl-sci', 'cond-mat.mes-hall', 'cond-mat.other', 'cond-mat.quant-gas', 'cond-mat.soft', 'cond-mat.stat-mech', 'cond-mat.str-el', 'cond-mat.supr-con', 'gr-qc', 'hep-ex', 'hep-lat', 'hep-ph', 'hep-th', 'math-ph', 'nlin.AO', 'nlin.CG', 'nlin.CD', 'nlin.SI', 'nlin.PS', 'nucl-ex', 'nucl-th', 'physics.acc-ph', 'physics.app-ph', 'physics.ao-ph', 'physics.atm-clus', 'physics.atom-ph', 'physics.bio-ph', 'physics.chem-ph', 'physics.class-ph', 'physics.comp-ph', 'physics.data-an', 'physics.flu-dyn', 'physics.gen-ph', 'physics.geo-ph', 'physics.hist-ph', 'physics.ins-det', 'physics.med-ph', 'physics.optics', 'physics.soc-ph', 'physics.ed-ph', 'physics.plasm-ph', 'physics.pop-ph', 'physics.space-ph', 'quant-ph', 'q-bio.BM', 'q-bio.CB', 'q-bio.GN', 'q-bio.MN', 'q-bio.NC', 'q-bio.OT', 'q-bio.PE', 'q-bio.QM', 'q-bio.SC', 'q-bio.TO', 'q-fin.CP', 'q-fin.EC', 'q-fin.GN', 'q-fin.MF', 'q-fin.PM', 'q-fin.PR', 'q-fin.RM', 'q-fin.ST', 'q-fin.TR', 'stat.AP', 'stat.CO', 'stat.ML', 'stat.ME', 'stat.OT', 'stat.TH'])

def create_issue (article, token):
    title = article['title']
    body = f"URL: {article['id'].strip()}\n\n> {' '.join(article['summary'].strip().splitlines())}"
    labels = set(map(lambda t: t['term'], article['tags'])) & arxiv_categories
    r = requests.post(
        'https://api.github.com/repos/{}/issues'.format(environ['GITHUB_REPOSITORY']),
        auth=('', token),
        data=json.dumps({
            'title': title,
            'body': body,
            'labels': list(labels)
        })
    )


class GitHubAppToken:

    def __init__(self, app_id, installation_id, private_key_path):

        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key = Path(private_key_path).read_bytes()

        self.token = ''
        self.expires_at = datetime.now(timezone.utc)

    def retrieve_token(self):

        now = datetime.now(timezone.utc)

        payload = {
            'iat': int(now.timestamp()),
            'exp': int(now.timestamp()) + 600,
            'iss': self.app_id
        }

        jwt = JWT.encode(payload, self.private_key, 'RS256').decode('utf-8')

        token_response = requests.post(
            'https://api.github.com/app/installations/{}/access_tokens'.format(self.installation_id),
            headers={
                'Authorization': 'Bearer {}'.format(jwt),
                'Accept': 'application/vnd.github.machine-man-preview+json'
            }
        )

        token_data = token_response.json()

        if token_response.status_code != 201:
            raise Exception('Failed to refresh token: `{}`'.format(token_data['message']))
            return
        
        self.token = token_data['token']
        self.expires_at = isoparse(token_data['expires_at'])

    def read(self):

        now = datetime.now(timezone.utc)

        if self.expires_at < now:
            self.retrieve_token()

        return self.token


parser = argparse.ArgumentParser()
parser.add_argument('--no-post', action='store_true')

opt = parser.parse_args()

seen_ids_file = Path(environ['ARXIV_SEEN_IDS_PATH'])

seen_ids = set(seen_ids_file.read_text().split('\n'))

search_result = arxiv.query(
    query=environ['ARXIV_QUERY'],
    max_results=300,
    sort_by='submittedDate'
)

print('Loaded {} articles from arXiv.'.format(len(search_result)))

token = GitHubAppToken(
    app_id=environ['GITHUB_APP_ID'],
    installation_id=environ['GITHUB_INSTALLATION_ID'],
    private_key_path=environ['GITHUB_PRIVATE_KEY_PATH']
)

num_issues = 0

for article in search_result:
    if article['id'] not in seen_ids:
        if opt.no_post:
            continue
        create_issue(article, token.read())
        seen_ids.add(article['id'])
        seen_ids_file.write_text('\n'.join(seen_ids))
        num_issues += 1
        sleep(0.5)

print('Created {} issues on {}.'.format(num_issues, environ['GITHUB_REPOSITORY']))