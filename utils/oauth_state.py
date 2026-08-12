"""GitHub OAuth 浏览器登录态的安全序列化辅助函数。"""

from __future__ import annotations

import base64
import gzip
import io
import json
import os
from urllib.parse import urlparse

DEFAULT_GITHUB_STATE_ENV = 'AGENTROUTER_GITHUB_STATE'
MAX_STORAGE_STATE_BYTES = 256 * 1024


def _is_github_domain(domain: str) -> bool:
	domain = domain.lstrip('.').lower()
	return domain == 'github.com' or domain.endswith('.github.com')


def _is_github_origin(origin: str) -> bool:
	hostname = urlparse(origin).hostname or ''
	return _is_github_domain(hostname)


def filter_github_storage_state(storage_state: dict) -> dict:
	"""只保留 GitHub 域 Cookie/Storage，避免把 AgentRouter 会话装入 Secret。"""
	if not isinstance(storage_state, dict):
		raise ValueError('Browser storage state must be a JSON object')

	cookies = storage_state.get('cookies', [])
	origins = storage_state.get('origins', [])
	if not isinstance(cookies, list) or not isinstance(origins, list):
		raise ValueError('Browser storage state has invalid cookies/origins')

	filtered_cookies = [
		cookie for cookie in cookies if isinstance(cookie, dict) and _is_github_domain(str(cookie.get('domain', '')))
	]
	filtered_origins = [
		origin for origin in origins if isinstance(origin, dict) and _is_github_origin(str(origin.get('origin', '')))
	]

	has_user_session = any(
		cookie.get('name') in {'user_session', '__Host-user_session_same_site'} and cookie.get('value')
		for cookie in filtered_cookies
	)
	if not has_user_session:
		raise ValueError('No authenticated GitHub user_session cookie found; complete GitHub login first')

	return {'cookies': filtered_cookies, 'origins': filtered_origins}


def encode_github_storage_state(storage_state: dict) -> str:
	"""将 GitHub-only storage state 压缩成适合 GitHub Secret 的单行文本。"""
	filtered = filter_github_storage_state(storage_state)
	payload = json.dumps(filtered, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
	return base64.urlsafe_b64encode(gzip.compress(payload, compresslevel=9)).decode('ascii')


def decode_github_storage_state(encoded: str) -> dict:
	"""解码并重新验证 GitHub-only storage state。"""
	if not encoded or not encoded.strip():
		raise ValueError('GitHub OAuth state secret is empty')

	try:
		compressed = base64.urlsafe_b64decode(encoded.strip().encode('ascii'))
		with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as archive:
			payload = archive.read(MAX_STORAGE_STATE_BYTES + 1)
	except Exception as exc:
		raise ValueError('GitHub OAuth state secret is not valid gzip/base64 data') from exc

	if len(payload) > MAX_STORAGE_STATE_BYTES:
		raise ValueError('GitHub OAuth state secret is unexpectedly large')

	try:
		storage_state = json.loads(payload.decode('utf-8'))
	except (UnicodeDecodeError, json.JSONDecodeError) as exc:
		raise ValueError('GitHub OAuth state secret does not contain valid JSON') from exc

	return filter_github_storage_state(storage_state)


def load_github_storage_state(env_name: str = DEFAULT_GITHUB_STATE_ENV) -> dict:
	"""从环境变量读取 GitHub OAuth 登录态，错误中不包含 Secret 内容。"""
	encoded = os.getenv(env_name, '')
	if not encoded:
		raise ValueError(f'Required GitHub Actions secret {env_name} is not configured')
	return decode_github_storage_state(encoded)
