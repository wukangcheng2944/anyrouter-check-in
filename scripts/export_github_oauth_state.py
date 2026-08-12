#!/usr/bin/env python3
"""交互式导出 GitHub-only 浏览器登录态，供 AgentRouter GitHub OAuth 使用。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cloakbrowser import launch_async  # noqa: E402

from utils.oauth_state import encode_github_storage_state  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / '.github_oauth_state'
OUTPUT_FILE = OUTPUT_DIR / 'agentrouter-github-state.secret'


async def export_state() -> None:
	launch_kwargs = {
		'headless': False,
		'humanize': True,
		'human_preset': 'careful',
	}
	browser = await launch_async(**launch_kwargs)
	context = await browser.new_context(viewport={'width': 1440, 'height': 960})
	page = await context.new_page()

	try:
		await page.goto('https://agentrouter.org/login', wait_until='domcontentloaded', timeout=60_000)
		print('\n请在打开的浏览器中完成以下操作：')
		print('1. 点击“使用 GitHub 继续”')
		print('2. 完成 GitHub 登录、二次验证及 AgentRouter 授权')
		print('3. 确认浏览器已经进入 AgentRouter 控制台')
		await asyncio.to_thread(input, '\n完成后回到终端按 Enter：')

		if '/console' not in page.url:
			await page.goto('https://agentrouter.org/console', wait_until='domcontentloaded', timeout=60_000)
		if '/console' not in page.url:
			raise RuntimeError('AgentRouter 登录尚未完成，请重新运行并完成 GitHub OAuth')

		storage_state = await context.storage_state()
		encoded = encode_github_storage_state(storage_state)
		OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
		OUTPUT_FILE.write_text(encoded, encoding='utf-8')
		try:
			os.chmod(OUTPUT_FILE, 0o600)
		except OSError:
			pass

		print(f'\n已生成 Secret 文件：{OUTPUT_FILE}')
		print('请把该文件的完整内容保存为 production Environment Secret：')
		print('AGENTROUTER_GITHUB_STATE')
		print('设置完成后删除本地 .github_oauth_state 目录，或妥善离线保管。')
	finally:
		await context.close()
		await browser.close()


if __name__ == '__main__':
	asyncio.run(export_state())
