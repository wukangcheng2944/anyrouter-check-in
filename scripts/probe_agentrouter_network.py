"""Probe AgentRouter official API reachability without printing OAuth secrets."""

from __future__ import annotations

import json
import platform
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OFFICIAL_DOMAINS = ('https://agentrouter.org', 'https://ps.air-outer.com')
ENDPOINTS = ('/api/status', '/api/oauth/state?mode=login')


def probe(url: str) -> None:
	request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'AgentRouter-Network-Probe/1.0'})
	try:
		with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed official URLs only
			status = response.status
			content_type = response.headers.get_content_type()
			body = response.read(64 * 1024)
	except HTTPError as exc:
		status = exc.code
		content_type = exc.headers.get_content_type()
		body = exc.read(64 * 1024)
	except (TimeoutError, URLError) as exc:
		print(f'{url}: network_error={type(exc).__name__}')
		return

	json_ok = False
	json_keys: list[str] = []
	try:
		payload = json.loads(body)
		json_ok = isinstance(payload, dict)
		if json_ok:
			json_keys = sorted(payload)
	except (UnicodeDecodeError, json.JSONDecodeError):
		pass

	print(f'{url}: status={status} content_type={content_type} json_object={json_ok} keys={json_keys}')


def main() -> None:
	print(f'runner_os={platform.system()} architecture={platform.machine()}')
	for domain in OFFICIAL_DOMAINS:
		for endpoint in ENDPOINTS:
			probe(domain + endpoint)


if __name__ == '__main__':
	main()
