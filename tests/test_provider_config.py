import json

from utils.config import AppConfig, ProviderConfig, load_accounts_config


def test_builtin_provider_profile_persistence_defaults(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is True
	assert config.providers['agentrouter'].persist_profile is False


def test_provider_profile_persistence_can_override_builtin(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps(
			{
				'anyrouter': {'domain': 'https://anyrouter.top', 'persist_profile': False},
				'agentrouter': {'domain': 'https://agentrouter.org', 'persist_profile': True},
			}
		),
	)

	config = AppConfig.load_from_env()

	assert config.providers['anyrouter'].persist_profile is False
	assert config.providers['agentrouter'].persist_profile is True


def test_custom_provider_profile_persistence_defaults_to_false(monkeypatch):
	monkeypatch.setenv('PROVIDERS', json.dumps({'custom': {'domain': 'https://custom.example.com'}}))

	config = AppConfig.load_from_env()

	assert config.providers['custom'].persist_profile is False


def test_provider_from_dict_inherits_profile_persistence_from_defaults():
	defaults = ProviderConfig(name='custom', domain='https://old.example.com', persist_profile=True)

	provider = ProviderConfig.from_dict(
		'custom',
		{'domain': 'https://new.example.com'},
		defaults=defaults,
	)

	assert provider.persist_profile is True


def test_github_oauth_account_needs_no_password_cookie_or_api_user(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'name': 'AgentRouter', 'provider': 'agentrouter', 'auth_method': 'github'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert accounts[0].uses_github_oauth()


def test_github_oauth_account_rejects_other_provider(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'provider': 'anyrouter', 'auth_method': 'github'}]),
	)

	assert load_accounts_config() is None


def test_agentrouter_accounts_are_merged_without_overwriting_anyrouter(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'name': 'AnyRouter', 'cookies': {'session': 'session'}, 'api_user': '1'}]),
	)
	monkeypatch.setenv(
		'AGENTROUTER_ACCOUNTS',
		json.dumps([{'name': 'AgentRouter', 'provider': 'agentrouter', 'auth_method': 'github'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert [account.name for account in accounts] == ['AnyRouter', 'AgentRouter']
	assert accounts[1].uses_github_oauth()


def test_agentrouter_accounts_can_be_used_without_anyrouter_secret(monkeypatch):
	monkeypatch.delenv('ANYROUTER_ACCOUNTS', raising=False)
	monkeypatch.setenv(
		'AGENTROUTER_ACCOUNTS',
		json.dumps([{'provider': 'agentrouter', 'auth_method': 'github'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert len(accounts) == 1
	assert accounts[0].provider == 'agentrouter'
