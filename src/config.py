from __future__ import annotations

from dataclasses import dataclass, field
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    OLLAMA_BASE_URL: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    LLM_PROVIDER: str = field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "openai"))
    LLM_MODEL: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "gpt-4o-mini"))

    OLLAMA_MODEL: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5"))

    LOG_DIR: str = field(default_factory=lambda: os.getenv("LOG_DIR", "storage/logs"))
    INITIAL_CASH: float = field(default_factory=lambda: float(os.getenv("INITIAL_CASH", "100000")))

    MAX_POSITION_PCT: float = 0.20
    MIN_CASH_RESERVE_PCT: float = 0.20
    STOP_LOSS_PCT: float = 0.05
    BROKER_FEE_PCT: float = 0.001

    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    API_PORT: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    def get_llm(self):
        from langchain_openai import ChatOpenAI

        provider = self.LLM_PROVIDER.lower()
        if provider == "openai":
            return ChatOpenAI(
                model=self.LLM_MODEL,
                api_key=self.OPENAI_API_KEY,
                temperature=0.1,
            )
        if provider == "gemini":
            return ChatOpenAI(
                model=self.LLM_MODEL,
                api_key=self.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                temperature=0.1,
            )
        if provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=self.OLLAMA_MODEL,
                base_url=self.OLLAMA_BASE_URL,
                temperature=0.1,
            )
        raise ValueError(f"Unknown LLM provider: {provider}")

    def get_structured_llm(self, pydantic_model):
        return self.get_llm().with_structured_output(pydantic_model)


config = Config()
