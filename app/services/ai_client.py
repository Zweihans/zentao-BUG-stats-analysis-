"""AI 客户端 — OpenAI / Anthropic 兼容接口"""
import os
import json
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)


def get_ai_config() -> dict:
    return {
        'base_url': os.getenv('AI_BASE_URL', '').rstrip('/'),
        'api_key': os.getenv('AI_API_KEY', ''),
        'model': os.getenv('AI_MODEL', ''),
    }


def call_ai(system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 2000, timeout: int = 30) -> str:
    base_url = os.getenv('AI_BASE_URL', '').rstrip('/')
    api_key = os.getenv('AI_API_KEY', '')
    model = os.getenv('AI_MODEL', '')

    if not base_url or not api_key:
        raise Exception('AI 未配置：请先在设置页填写 API 地址和 Key')

    is_anthropic = 'anthropic' in base_url.lower()
    session = requests.Session()

    if is_anthropic:
        endpoint = f"{base_url}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    else:
        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json"
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    resp = session.post(endpoint, headers=headers, json=body, timeout=timeout)

    if not resp.ok:
        raise Exception(f"AI 调用失败 ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()

    if is_anthropic:
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise Exception(f"未知响应格式: {json.dumps(data, ensure_ascii=False)[:500]}")
    else:
        return data["choices"][0]["message"]["content"]


def update_ai_config(base_url: str, api_key: str, model: str) -> None:
    """更新 .env 中的 AI 配置"""
    env_path = os.path.join(BASE_DIR, ".env")

    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    updates = {
        'AI_BASE_URL': base_url,
        'AI_API_KEY': api_key,
        'AI_MODEL': model,
    }

    new_lines = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            key = stripped.split('=', 1)[0].strip()
            if key in updates:
                new_lines.append(f'{key}={updates[key]}\n')
                seen.add(key)
                continue
        new_lines.append(line)

    for key in updates:
        if key not in seen:
            new_lines.append(f'{key}={updates[key]}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    # 重新加载环境变量，确保后续调用即时生效
    load_dotenv(env_path, override=True)


def test_connection() -> dict:
    """测试 AI 连接是否正常"""
    try:
        config = get_ai_config()
        if not config['base_url'] or not config['api_key']:
            return {'ok': False, 'message': 'AI 未配置：请填写 API 地址和 Key'}
        response = call_ai(
            system_prompt='你是一个测试助手，请简短回复。',
            user_prompt='请回复"连接成功"',
            temperature=0,
            max_tokens=50,
            timeout=10
        )
        return {'ok': True, 'message': response.strip()[:200]}
    except Exception as e:
        return {'ok': False, 'message': str(e)[:300]}
