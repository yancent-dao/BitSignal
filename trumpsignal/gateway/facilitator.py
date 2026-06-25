"""
x402 facilitator 工厂。

- 测试网：x402.org/facilitator（免费，无需鉴权）
- 主网：Coinbase CDP facilitator（需 CDP API key，JWT 鉴权）

通过环境变量切换：
  FACILITATOR_URL       facilitator 基础 URL
  CDP_API_KEY_ID        CDP API key ID（仅主网 CDP 需要）
  CDP_API_KEY_SECRET    CDP API key secret（仅主网 CDP 需要）
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.facilitator_client_base import CreateHeadersAuthProvider

from config import settings

logger = logging.getLogger(__name__)


def _build_cdp_create_headers(base_url: str, api_key_id: str, api_key_secret: str):
    """返回一个 create_headers 函数，为 verify/settle/supported 三个端点各生成 JWT。"""
    from cdp.auth.utils.http import GetAuthHeadersOptions, get_auth_headers

    parsed = urlparse(base_url)
    host = parsed.netloc
    base_path = parsed.path.rstrip("/")  # 如 /platform/v2/x402

    def _headers_for(method: str, endpoint: str) -> dict[str, str]:
        opts = GetAuthHeadersOptions(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            request_method=method,
            request_host=host,
            request_path=f"{base_path}/{endpoint}",
        )
        return get_auth_headers(opts)

    def create_headers() -> dict[str, dict[str, str]]:
        return {
            "verify": _headers_for("POST", "verify"),
            "settle": _headers_for("POST", "settle"),
            "supported": _headers_for("GET", "supported"),
        }

    return create_headers


def build_facilitator() -> HTTPFacilitatorClient:
    """根据配置构造 facilitator 客户端（自动选测试网/主网 CDP）。"""
    # strip 掉环境变量可能带入的空格/换行（Railway 粘贴常见问题）
    url = settings.facilitator_url.strip().rstrip("/")
    is_cdp = "cdp.coinbase.com" in url

    if is_cdp:
        key_id = settings.cdp_api_key_id.strip()
        key_secret = settings.cdp_api_key_secret.strip()
        if not (key_id and key_secret):
            raise RuntimeError(
                "使用 CDP facilitator 需设置 CDP_API_KEY_ID 和 CDP_API_KEY_SECRET"
            )
        create_headers = _build_cdp_create_headers(url, key_id, key_secret)
        auth_provider = CreateHeadersAuthProvider(create_headers)
        logger.info("Using CDP production facilitator: %s", url)
        client = HTTPFacilitatorClient(FacilitatorConfig(url=url, auth_provider=auth_provider))
        # 启动时主动探测一次，把真实鉴权/连接错误暴露到日志
        try:
            supported = client.get_supported()
            networks = sorted({k.network for k in supported.kinds})
            logger.info("CDP facilitator OK. Supported networks: %s", networks)
        except Exception as exc:
            logger.error("CDP facilitator probe FAILED: %s: %s", type(exc).__name__, exc)
        return client

    logger.info("Using free testnet facilitator: %s", url)
    return HTTPFacilitatorClient(FacilitatorConfig(url=url))
