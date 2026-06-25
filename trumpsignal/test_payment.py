"""
x402 付费测试脚本。
需要在 .env 里配置：
  TEST_WALLET_PRIVATE_KEY=0x...   # 测试钱包私钥（Base Sepolia，需有 USDC）

Base Sepolia USDC faucet: https://faucet.circle.com
"""
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv
load_dotenv()

import httpx
from eth_account import Account
from x402.client import x402Client
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm.signers import EthAccountSigner
from x402.schemas import PaymentRequired

TARGET_URL = "https://trumpsignal-production.up.railway.app/signals/recent?limit=3"
NETWORK = "eip155:84532"  # Base Sepolia testnet


async def main():
    private_key = os.environ.get("TEST_WALLET_PRIVATE_KEY", "").strip()
    if not private_key:
        print("❌ 请在 .env 里设置 TEST_WALLET_PRIVATE_KEY=0x...")
        sys.exit(1)

    # 标准化：去掉空格/换行，确保 0x 前缀
    private_key = private_key.replace(" ", "").replace("\n", "").replace("\r", "")
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    print(f"🔑 私钥长度: {len(private_key)} 字符（应为 66）")
    if len(private_key) != 66:
        print(f"❌ 私钥长度不对，请检查 .env 里的 TEST_WALLET_PRIVATE_KEY")
        sys.exit(1)

    account = Account.from_key(private_key)
    print(f"💳 测试钱包地址: {account.address}")

    signer = EthAccountSigner(account)
    scheme = ExactEvmClientScheme(signer=signer)

    client = x402Client()
    client.register(NETWORK, scheme)

    async with httpx.AsyncClient() as http:
        # Step 1: 发请求，拿 402
        print(f"\n📡 请求: GET {TARGET_URL}")
        r1 = await http.get(TARGET_URL)
        print(f"   状态码: {r1.status_code}")

        if r1.status_code != 402:
            print(f"   ⚠️  预期 402，实际收到 {r1.status_code}")
            print(f"   响应: {r1.text[:300]}")
            return

        # Step 2: 解析 payment-required header
        pr_b64 = r1.headers.get("payment-required", "")
        pr_json = base64.b64decode(pr_b64 + "==").decode()
        pr_data = json.loads(pr_json)
        print(f"\n💰 Payment Required:")
        print(f"   网络: {pr_data['accepts'][0]['network']}")
        print(f"   金额: {int(pr_data['accepts'][0]['amount']) / 1_000_000:.4f} USDC")
        print(f"   收款: {pr_data['accepts'][0]['payTo']}")

        payment_required = PaymentRequired.model_validate(pr_data)

        # Step 3: 创建付款 payload
        print("\n🔐 创建付款签名...")
        try:
            payload = await client.create_payment_payload(payment_required)
        except Exception as e:
            print(f"❌ 付款创建失败: {e}")
            print("   可能原因：钱包余额不足，或网络问题")
            return

        # 用 SDK 官方编码函数，header 名为 PAYMENT-SIGNATURE
        from x402.http.utils import encode_payment_signature_header
        payload_header = encode_payment_signature_header(payload)
        print("   签名完成 ✅")

        # Step 4: 带付款 header 重新请求
        print("\n📡 携带付款重新请求...")
        print(f"   PAYMENT-SIGNATURE 长度: {len(payload_header)} 字符")
        r2 = await http.get(
            TARGET_URL,
            headers={"PAYMENT-SIGNATURE": payload_header},
        )
        print(f"   状态码: {r2.status_code}")
        print(f"   响应体: {r2.text[:500]}")

        if r2.status_code == 200:
            data = r2.json()
            print(f"\n✅ 付费成功！收到 {data.get('count', 0)} 条信号：")
            for sig in data.get("signals", []):
                print(f"\n   [{sig.get('event_type','?')}] {sig.get('source','?')}")
                print(f"   摘要: {sig.get('summary','')[:120]}")
                assets = sig.get("assets_affected", [])
                if assets:
                    print(f"   影响标的: {', '.join(a['asset'] + '(' + a['direction'] + ')' for a in assets[:3])}")
        else:
            print(f"❌ 付款后仍失败: {r2.status_code}")
            print(f"   {r2.text[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
