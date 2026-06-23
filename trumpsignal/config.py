from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-haiku-4-5"

    # 信源
    twitterapi_io_key: str = ""

    # 支付
    payment_recipient_address: str = "0x0000000000000000000000000000000000000000"
    use_testnet: bool = True

    # AgentVerse
    agentverse_api_key: str = ""
    agent_seed_phrase: str = "trumpsignal default seed phrase change me"
    agent_port: int = 8001

    # 服务
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    port: int = 0  # Railway 注入的 PORT 环境变量

    @property
    def effective_port(self) -> int:
        return self.port if self.port else self.gateway_port
    public_base_url: str = ""

    # 日志
    log_level: str = "INFO"
    log_dir: str = "logs"

    @property
    def evm_network(self) -> str:
        return "eip155:84532" if self.use_testnet else "eip155:8453"

    @property
    def signal_price(self) -> str:
        return "$0.01"

    @property
    def openrouter_base_url(self) -> str:
        return "https://openrouter.ai/api/v1"


settings = Settings()
