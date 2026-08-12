import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from checkin import browser_cookies_for_url, generate_balance_hash


def test_balance_hash_changes_when_quota_changes():
	before = {'account_1': {'quota': 100.0, 'used': 20.0}}
	after = {'account_1': {'quota': 125.0, 'used': 20.0}}

	assert generate_balance_hash(before) != generate_balance_hash(after)


def test_balance_hash_changes_when_used_quota_changes():
	before = {'account_1': {'quota': 100.0, 'used': 20.0}}
	after = {'account_1': {'quota': 100.0, 'used': 21.0}}

	assert generate_balance_hash(before) != generate_balance_hash(after)


def test_balance_hash_is_stable_for_equivalent_balances():
	left = {
		'account_2': {'quota': 50.0, 'used': 1.0},
		'account_1': {'quota': 100.0, 'used': 20.0},
	}
	right = {
		'account_1': {'used': 20.0, 'quota': 100.0},
		'account_2': {'used': 1.0, 'quota': 50.0},
	}

	assert generate_balance_hash(left) == generate_balance_hash(right)


def test_browser_cookies_are_filtered_to_target_domain():
	cookies = [
		{'name': 'session', 'value': 'agentrouter-session', 'domain': 'agentrouter.org'},
		{'name': 'acw_tc', 'value': 'waf-cookie', 'domain': '.agentrouter.org'},
		{'name': 'user_session', 'value': 'github-secret', 'domain': 'github.com'},
		{'name': 'evil', 'value': 'wrong-suffix', 'domain': 'evilagentrouter.org'},
	]

	result = browser_cookies_for_url(cookies, 'https://agentrouter.org')

	assert result == {'session': 'agentrouter-session', 'acw_tc': 'waf-cookie'}
	assert 'github-secret' not in result.values()
