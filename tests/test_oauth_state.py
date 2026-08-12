import base64
import gzip
import json

import pytest

from utils.oauth_state import decode_github_storage_state, encode_github_storage_state, load_github_storage_state


def github_state():
	return {
		'cookies': [
			{
				'name': 'user_session',
				'value': 'github-session-value',
				'domain': '.github.com',
				'path': '/',
				'httpOnly': True,
				'secure': True,
				'sameSite': 'Lax',
			},
			{'name': 'session', 'value': 'must-not-leak', 'domain': 'agentrouter.org', 'path': '/'},
		],
		'origins': [
			{'origin': 'https://github.com', 'localStorage': []},
			{'origin': 'https://agentrouter.org', 'localStorage': [{'name': 'user', 'value': 'secret'}]},
		],
	}


def test_encode_decode_keeps_only_github_state():
	decoded = decode_github_storage_state(encode_github_storage_state(github_state()))

	assert [cookie['domain'] for cookie in decoded['cookies']] == ['.github.com']
	assert [origin['origin'] for origin in decoded['origins']] == ['https://github.com']
	assert 'must-not-leak' not in json.dumps(decoded)


def test_decode_rejects_state_without_authenticated_github_cookie():
	state = {'cookies': [{'name': 'logged_in', 'value': 'yes', 'domain': '.github.com'}], 'origins': []}
	payload = json.dumps(state).encode()
	encoded = base64.urlsafe_b64encode(gzip.compress(payload)).decode()

	with pytest.raises(ValueError, match='user_session'):
		decode_github_storage_state(encoded)


def test_load_state_reports_missing_secret_without_echoing_value(monkeypatch):
	monkeypatch.delenv('AGENTROUTER_GITHUB_STATE', raising=False)

	with pytest.raises(ValueError, match='AGENTROUTER_GITHUB_STATE'):
		load_github_storage_state()


def test_decode_rejects_malformed_secret():
	with pytest.raises(ValueError, match='gzip/base64'):
		decode_github_storage_state('not-a-storage-state')
