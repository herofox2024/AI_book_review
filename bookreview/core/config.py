"""配置层：LLM 接入、流水线参数、数据目录。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

# 常见 OpenAI 兼容服务商预设，切换时只需改 provider 或手动填 base_url
PRESETS: dict[str, dict[str, str]] = {
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.7",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "deepseek-pro": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "custom": {"base_url": "", "model": ""},
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class LLMSettings:
    provider: str = "glm"
    base_url: str = PRESETS["glm"]["base_url"]
    api_key: str = ""
    model: str = PRESETS["glm"]["model"]
    # 生成书评专用的模型，留空则复用 model。
    # 建议：分块摘要调用几十次，用便宜模型；最终生成只有一次，用强模型。
    review_model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 180
    max_retries: int = 3
    # 推理模型（如 deepseek-v4-*、o-series）的思维链 token 会占用同一份
    # max_tokens 预算。若不放大，长文本输出会被思维链吃光，返回空内容。
    # 请求时实际预算 = min(max_tokens * reasoning_reserve, max_output_cap)
    reasoning_reserve: float = 4.0
    max_output_cap: int = 32768


@dataclass
class PipelineSettings:
    chunk_size: int = 6000          # 单块字符数
    chunk_overlap: int = 300        # 块间重叠，避免切断情节
    concurrency: int = 4            # 摘要并发数
    digest_target_chars: int = 3000 # 全书理解卡目标字数
    chapter_merge_size: int = 12000 # 章节合并后再摘要的阈值


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    data_dir: str = "data"

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path | str = CONFIG_PATH) -> None:
        data = self.to_dict()
        # Never persist a secret supplied through the environment.
        if os.environ.get("BOOKREVIEW_API_KEY"):
            data["llm"]["api_key"] = ""
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path | str = CONFIG_PATH) -> "Settings":
        p = Path(path)
        if not p.exists():
            s = cls()
            s.save(p)
            return s
        raw = json.loads(p.read_text(encoding="utf-8"))
        s = cls()
        if "llm" in raw:
            for k, v in raw["llm"].items():
                if hasattr(s.llm, k):
                    setattr(s.llm, k, v)
        if "pipeline" in raw:
            for k, v in raw["pipeline"].items():
                if hasattr(s.pipeline, k):
                    setattr(s.pipeline, k, v)
        if "data_dir" in raw:
            s.data_dir = raw["data_dir"]
        env_key = os.environ.get("BOOKREVIEW_API_KEY", "").strip()
        if env_key:
            s.llm.api_key = env_key
        return s

    # ---------- 便捷方法 ----------
    def apply_preset(self, provider: str) -> None:
        """切换到预设服务商，只改 base_url 与默认模型，不动 api_key。"""
        if provider not in PRESETS:
            raise ValueError(f"未知服务商: {provider}，可选: {', '.join(PRESETS)}")
        self.llm.provider = provider
        preset = PRESETS[provider]
        if preset["base_url"]:
            self.llm.base_url = preset["base_url"]
        if preset["model"]:
            self.llm.model = preset["model"]

    def resolve_data_dir(self) -> Path:
        override = os.environ.get("BOOKREVIEW_DATA_DIR", "").strip()
        if override:
            d = Path(override)
            d.mkdir(parents=True, exist_ok=True)
            return d
        d = Path(self.data_dir)
        if not d.is_absolute():
            # 打包后 exe 目录只读，优先使用用户目录
            user_dir = Path(os.environ.get("APPDATA", PROJECT_ROOT)) / "bookreview"
            if getattr(__import__("sys"), "frozen", False):
                d = user_dir
            else:
                d = PROJECT_ROOT / d
        d.mkdir(parents=True, exist_ok=True)
        return d

    def require_api_key(self) -> str:
        key = (os.environ.get("BOOKREVIEW_API_KEY") or self.llm.api_key or "").strip()
        if not key:
            raise RuntimeError(
                f"未配置 API Key。请在 {CONFIG_PATH} 中填写 llm.api_key，"
                f"或在设置界面填入。当前服务商: {self.llm.provider}"
            )
        return key


def load_settings() -> Settings:
    return Settings.load()
