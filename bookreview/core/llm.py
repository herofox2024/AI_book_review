"""LLM 客户端：OpenAI 兼容协议，内置 429 限流退避重试。"""

from __future__ import annotations

import json
import time
from typing import Iterator

from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

from .config import Settings
from .logging_utils import get_logger


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        key = settings.require_api_key()
        self.model = settings.llm.model
        self.temperature = settings.llm.temperature
        self.max_tokens = settings.llm.max_tokens
        self.max_retries = settings.llm.max_retries
        self.logger = get_logger("bookreview.llm")
        self._client = OpenAI(
            api_key=key,
            base_url=settings.llm.base_url,
            timeout=settings.llm.timeout,
            max_retries=0,  # 自己控制重试，便于打印进度
        )

    # ---------- 底层调用 ----------
    def _budget(self, max_tokens: int) -> int:
        """推理模型的思维链会占用输出预算，按 reserve 放大后再请求。"""
        reserve = getattr(self.settings.llm, "reasoning_reserve", 1.0) or 1.0
        cap = getattr(self.settings.llm, "max_output_cap", 32768) or 32768
        if reserve <= 1.0:
            return min(max_tokens, cap)
        return min(int(max_tokens * reserve), cap)

    def _request(self, messages: list[dict], temperature: float, max_tokens: int,
                 json_mode: bool, model: str | None = None) -> str:
        kwargs: dict = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self._budget(max_tokens),
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info("模型请求开始: model=%s tokens=%s json=%s", kwargs["model"], kwargs["max_tokens"], json_mode)
                resp = self._client.chat.completions.create(**kwargs)
                content = (resp.choices[0].message.content or "").strip()
                # 推理模型可能把预算全部消耗在思维链上，正文返回空
                if not content and resp.choices[0].finish_reason == "length":
                    raise LLMError(
                        "模型输出被截断（思维链耗尽了 max_tokens）。"
                        f"当前请求预算 {kwargs['max_tokens']}，"
                        "请调大 config.json 的 llm.reasoning_reserve 或 max_output_cap。"
                    )
                return content
            except RateLimitError as e:
                wait = min(2 ** attempt * 3, 60)
                last_err = e
                self.logger.warning("请求被限流，第%d次重试，等待%s秒", attempt, wait)
                print(f"  [限流] 第 {attempt} 次被限流，{wait}s 后重试…")
                time.sleep(wait)
            except (APIConnectionError, APITimeoutError) as e:
                wait = min(2 ** attempt, 20)
                last_err = e
                self.logger.warning("网络请求失败，第%d次重试，等待%s秒", attempt, wait)
                print(f"  [网络] 第 {attempt} 次连接失败，{wait}s 后重试…")
                time.sleep(wait)
            except LLMError:
                raise
            except Exception as e:  # 其他错误（400 等）直接抛出，重试无意义
                self.logger.exception("模型请求失败")
                raise LLMError(f"模型调用失败: {type(e).__name__}: {e}") from e
        raise LLMError(f"模型调用重试 {self.max_retries} 次仍失败: {last_err}")

    def chat(self, system: str, user: str, temperature: float | None = None,
             max_tokens: int | None = None, json_mode: bool = False,
             model: str | None = None) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self._request(
            messages,
            self.temperature if temperature is None else temperature,
            self.max_tokens if max_tokens is None else max_tokens,
            json_mode,
            model,
        )

    def chat_json(self, system: str, user: str, temperature: float | None = None,
                  max_tokens: int | None = None, model: str | None = None) -> dict:
        """要求模型返回 JSON 对象，失败时尝试从代码块中抢救。"""
        raw = self.chat(system, user, temperature, max_tokens, json_mode=True, model=model)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = _extract_json(raw)
            if cleaned is None:
                raise LLMError(f"模型未返回合法 JSON，原文前 500 字:\n{raw[:500]}")
            return cleaned

    def stream(self, system: str, user: str, temperature: float | None = None,
               max_tokens: int | None = None, model: str | None = None) -> Iterator[str]:
        """流式输出；尚未产生内容时对限流/网络错误进行重试。"""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self._budget(self.max_tokens if max_tokens is None else max_tokens),
            "stream": True,
        }
        last_err: Exception | None = None
        emitted = False
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                finish_reason = None
                for chunk in resp:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish_reason = choice.finish_reason or finish_reason
                    delta = choice.delta.content
                    if delta:
                        emitted = True
                        yield delta
                if finish_reason == "length":
                    raise LLMError("流式输出被截断，请调大 max_tokens 或 reasoning_reserve。")
                return
            except RateLimitError as e:
                last_err = e
                if emitted:
                    raise LLMError(f"流式输出中断（限流）: {e}") from e
                time.sleep(min(2 ** attempt * 3, 60))
            except (APIConnectionError, APITimeoutError) as e:
                last_err = e
                if emitted:
                    raise LLMError(f"流式输出中断（网络错误）: {e}") from e
                time.sleep(min(2 ** attempt, 20))
            except LLMError:
                raise
            except Exception as e:
                raise LLMError(f"流式模型调用失败: {type(e).__name__}: {e}") from e
        raise LLMError(f"流式模型调用重试 {self.max_retries} 次仍失败: {last_err}")
    # ---------- 自检 ----------
    def ping(self) -> tuple[bool, str]:
        try:
            r = self.chat("你是一个测试助手。", "只回复两个字：正常", max_tokens=16)
            return True, r[:50]
        except Exception as e:
            return False, str(e)


def _extract_json(text: str) -> dict | None:
    """从 ```json ... ``` 包裹或首尾杂讯中提取 JSON 对象。"""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None
