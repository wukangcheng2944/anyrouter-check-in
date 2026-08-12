import sys
from types import SimpleNamespace
from typing import Any

import pytest

from utils.browser import (
	is_access_verification_text,
	launch_login_context,
	load_browser_login_settings,
	login_with_github_oauth_direct,
	parse_github_oauth_callback,
	parse_github_oauth_client_id,
	parse_github_oauth_redirect,
	parse_github_oauth_state,
)


def test_browser_login_settings_records_profile_persistence(monkeypatch, tmp_path):
	monkeypatch.setenv('CHECKIN_BROWSER_PROFILE_DIR', str(tmp_path))

	settings = load_browser_login_settings('Account 1', 'agentrouter', persist_profile=False)

	assert settings.persist_profile is False
	assert settings.profile_dir == tmp_path / 'agentrouter' / 'Account 1'


@pytest.mark.asyncio
async def test_launch_login_context_uses_persistent_context_when_enabled(monkeypatch, tmp_path):
	calls = {}
	context = SimpleNamespace()

	async def fake_launch_persistent_context_async(profile_dir, **kwargs):
		calls['profile_dir'] = profile_dir
		calls['kwargs'] = kwargs
		return context

	monkeypatch.setitem(
		sys.modules,
		'cloakbrowser',
		SimpleNamespace(launch_persistent_context_async=fake_launch_persistent_context_async),
	)

	settings = load_browser_login_settings('Account 1', 'anyrouter', persist_profile=True)
	settings = settings.__class__(
		headless=settings.headless,
		humanize=False,
		wait_timeout_ms=settings.wait_timeout_ms,
		profile_dir=tmp_path / 'profiles' / 'anyrouter' / 'Account 1',
		cloakbrowser_binary_path=settings.cloakbrowser_binary_path,
		persist_profile=settings.persist_profile,
	)

	result: Any = await launch_login_context(settings)

	assert result is context
	assert calls['profile_dir'] == str(settings.profile_dir)


@pytest.mark.asyncio
async def test_launch_login_context_closes_browser_for_ephemeral_context(monkeypatch, tmp_path):
	class FakeContext:
		def __init__(self):
			self.closed = False

		async def close(self):
			self.closed = True

	class FakeBrowser:
		def __init__(self):
			self.context = FakeContext()
			self.closed = False
			self.context_kwargs = {}
			self.launch_kwargs = {}

		async def new_context(self, **kwargs):
			self.context_kwargs = kwargs
			return self.context

		async def close(self):
			self.closed = True

	browser = FakeBrowser()

	async def fake_launch_async(**kwargs):
		browser.launch_kwargs = kwargs
		return browser

	monkeypatch.setitem(
		sys.modules,
		'cloakbrowser',
		SimpleNamespace(launch_async=fake_launch_async),
	)

	settings = load_browser_login_settings('Account 1', 'agentrouter', persist_profile=False)
	settings = settings.__class__(
		headless=settings.headless,
		humanize=False,
		wait_timeout_ms=settings.wait_timeout_ms,
		profile_dir=tmp_path / 'profiles' / 'agentrouter' / 'Account 1',
		cloakbrowser_binary_path=settings.cloakbrowser_binary_path,
		persist_profile=settings.persist_profile,
	)

	context: Any = await launch_login_context(settings)
	await context.close()

	assert context.closed is True
	assert browser.closed is True
	assert not settings.profile_dir.exists()


@pytest.mark.asyncio
async def test_launch_login_context_passes_storage_state_to_ephemeral_context(monkeypatch, tmp_path):
	class FakeBrowser:
		def __init__(self):
			self.context_kwargs = {}

		async def new_context(self, **kwargs):
			self.context_kwargs = kwargs
			return SimpleNamespace(close=lambda: None)

		async def close(self):
			pass

	browser = FakeBrowser()

	async def fake_launch_async(**kwargs):
		return browser

	monkeypatch.setitem(sys.modules, 'cloakbrowser', SimpleNamespace(launch_async=fake_launch_async))
	settings = load_browser_login_settings('Account 1', 'agentrouter', persist_profile=False)
	storage_state: dict[str, list] = {'cookies': [], 'origins': []}

	await launch_login_context(settings, storage_state=storage_state)

	assert browser.context_kwargs['storage_state'] is storage_state


def test_parse_github_oauth_callback_requires_checked_in():
	with pytest.raises(ValueError, match='checked_in'):
		parse_github_oauth_callback({'success': True, 'data': {'id': 123}})


@pytest.mark.parametrize('checked_in', [True, False])
def test_parse_github_oauth_callback_preserves_checkin_status(checked_in):
	result = parse_github_oauth_callback({'success': True, 'data': {'id': 123, 'checked_in': checked_in}})

	assert result.checked_in is checked_in
	assert result.user['id'] == 123


def test_access_verification_text_matches_slider_page():
	assert is_access_verification_text('Access Verification Please slide to verify')
	assert not is_access_verification_text('Sign in with GitHub')


def test_parse_direct_oauth_inputs_fail_closed():
	with pytest.raises(ValueError, match='github_client_id'):
		parse_github_oauth_client_id({'success': True, 'data': {}})
	with pytest.raises(ValueError, match='empty'):
		parse_github_oauth_state({'success': True, 'data': ''})
	with pytest.raises(ValueError, match='state did not match'):
		parse_github_oauth_redirect(
			'https://agentrouter.org/oauth/github?code=one-time-code&state=wrong',
			'https://agentrouter.org',
			'expected',
		)


@pytest.mark.asyncio
async def test_direct_github_oauth_uses_official_api_and_preserves_checkin_status(monkeypatch):
	class FakeResponse:
		def __init__(self, payload):
			self.payload = payload
			self.status = 200

		def json(self):
			return self.payload

	class FakeClient:
		def __init__(self):
			self.urls = []
			self.cookies = {'session': 'agentrouter-session'}

		async def __aenter__(self):
			return self

		async def __aexit__(self, *args):
			return None

		async def aclose(self):
			return None

		async def get(self, url, **kwargs):
			self.urls.append(str(url))
			if url == '/api/status':
				return FakeResponse({'success': True, 'data': {'github_client_id': 'client-id'}})
			if url == '/api/oauth/state':
				return FakeResponse({'success': True, 'data': 'expected-state'})
			if url == '/api/oauth/github':
				return FakeResponse({'success': True, 'data': {'id': 123, 'checked_in': True}})
			if url == '/api/user/self':
				return FakeResponse({'success': True, 'data': {'id': 123}})
			raise AssertionError(f'Unexpected URL: {url}')

	class FakePage:
		def __init__(self):
			self.url = 'https://agentrouter.org/login'

		async def goto(self, url, **kwargs):
			assert 'client_id=client-id' in url
			self.url = 'https://agentrouter.org/oauth/github?code=one-time-code&state=expected-state'

	fake_client = FakeClient()
	monkeypatch.setattr('utils.browser.httpx.AsyncClient', lambda **kwargs: fake_client)
	page: Any = FakePage()

	result = await login_with_github_oauth_direct(page, 'https://agentrouter.org', 5_000)

	assert result.callback.checked_in is True
	assert result.callback.user['id'] == 123
	assert result.user_profile['id'] == 123
	assert result.cookies == {'session': 'agentrouter-session'}
	assert result.request_domain == 'https://agentrouter.org'
	assert '/api/oauth/github' in fake_client.urls
