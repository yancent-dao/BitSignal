"""
CDP facilitator 鉴权调试。
需要本地 .env 里有：
  CDP_API_KEY_ID=...
  CDP_API_KEY_SECRET=...
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv
load_dotenv()

import httpx
from cdp.auth.utils.http import GetAuthHeadersOptions, get_auth_headers

key_id = os.environ.get("CDP_API_KEY_ID", "").strip()
key_secret = os.environ.get("CDP_API_KEY_SECRET", "").strip()

print(f"Key ID: {key_id[:40]}{'...' if len(key_id) > 40 else ''}")
print(f"Key ID 格式: ", end="")
if key_id.startswith("organizations/"):
    print("organizations/.../apiKeys/...（旧格式 Secret Key ✅）")
elif "-" in key_id and len(key_id) == 36:
    print("UUID（新格式 Secret Key ✅）")
else:
    print(f"⚠️ 异常格式，长度={len(key_id)}，可能是 Client API Key（不能用于 JWT）")

print(f"Secret 长度: {len(key_secret)}")
print(f"Secret 格式: ", end="")
if key_secret.startswith("-----BEGIN"):
    print("PEM EC key ✅")
elif key_secret.endswith("==") or len(key_secret) > 60:
    print("base64 Ed25519 ✅")
else:
    print(f"⚠️ 可能异常")

print("\n--- 生成 JWT 并调用 CDP /supported ---")
try:
    opts = GetAuthHeadersOptions(
        api_key_id=key_id,
        api_key_secret=key_secret,
        request_method="GET",
        request_host="api.cdp.coinbase.com",
        request_path="/platform/v2/x402/supported",
    )
    headers = get_auth_headers(opts)
    print("JWT 生成成功 ✅")

    resp = httpx.get(
        "https://api.cdp.coinbase.com/platform/v2/x402/supported",
        headers=headers,
        timeout=15,
    )
    print(f"状态码: {resp.status_code}")
    print(f"响应体: {resp.text[:500]}")
    if resp.status_code == 200:
        print("\n✅✅✅ CDP 鉴权成功！可以上主网了")
except Exception as e:
    print(f"❌ 错误: {type(e).__name__}: {e}")
