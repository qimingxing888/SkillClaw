"""
KimiClient - OpenAI-compatible API client for Kimi (Moonshot AI)
Supports streaming, function calling, and automatic retry.
"""

import json
import time
from typing import Dict, List, Optional, Any, AsyncGenerator, Generator
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI, OpenAI


@dataclass
class ChatResponse:
    """Standardized chat response"""
    content: str
    tool_calls: List[Dict[str, Any]]
    model: str
    reasoning_content: str = ""
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "model": self.model,
            "reasoning_content": self.reasoning_content,
            "usage": self.usage,
            "finish_reason": self.finish_reason
        }


@dataclass
class StreamChunk:
    """A chunk of streaming response"""
    content: str = ""
    tool_calls: Optional[List[Dict]] = None
    is_finished: bool = False
    finish_reason: Optional[str] = None


class KimiClient:
    """
    Client for Kimi/Moonshot AI API with OpenAI compatibility.
    Supports both sync and async operations, streaming, and function calling.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.cn/v1",
        model: str = "kimi-k2.5",
        temperature: float = 1.0,  # Kimi K2.5 only supports temperature=1
        max_tokens: int = 8192,
        timeout: int = 60,
        retry_attempts: int = 3
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.retry_attempts = retry_attempts

        # Initialize clients
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> ChatResponse:
        """
        Send a chat request to the API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice strategy ("auto", "none", or specific)
            temperature: Optional temperature override
            max_tokens: Optional max_tokens override
            stream: Whether to stream the response

        Returns:
            ChatResponse object
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": stream
        }

        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        # Retry logic
        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                response = self.client.chat.completions.create(**kwargs)

                if stream:
                    raise ValueError("Use chat_stream() for streaming requests")

                return self._parse_response(response)

            except openai.RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)
                continue

            except (openai.APIError, openai.APITimeoutError) as e:
                last_error = e
                if attempt < self.retry_attempts - 1:
                    time.sleep(1)
                    continue
                raise

        raise last_error or Exception("Max retry attempts reached")

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Generator[StreamChunk, None, None]:
        """
        Stream a chat response.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions
            temperature: Optional temperature override
            max_tokens: Optional max_tokens override

        Yields:
            StreamChunk objects
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True
        }

        if tools:
            kwargs["tools"] = tools

        try:
            stream = self.client.chat.completions.create(**kwargs)

            for chunk in stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                content = delta.content or ""
                tool_calls = None

                if delta.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in delta.tool_calls
                    ]

                yield StreamChunk(
                    content=content,
                    tool_calls=tool_calls,
                    is_finished=finish_reason is not None,
                    finish_reason=finish_reason
                )

        except Exception as e:
            yield StreamChunk(
                content=f"\n[Error: {str(e)}]",
                is_finished=True,
                finish_reason="error"
            )

    async def achat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> ChatResponse:
        """
        Async chat request.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice strategy
            temperature: Optional temperature override
            max_tokens: Optional max_tokens override

        Returns:
            ChatResponse object
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens
        }

        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        for attempt in range(self.retry_attempts):
            try:
                response = await self.async_client.chat.completions.create(**kwargs)
                return self._parse_response(response)

            except openai.RateLimitError:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue

            except (openai.APIError, openai.APITimeoutError):
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1)
                    continue
                raise

        raise Exception("Max retry attempts reached")

    async def achat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Async streaming chat request.

        Args:
            messages: List of message dicts
            tools: Optional list of tool definitions
            temperature: Optional temperature override
            max_tokens: Optional max_tokens override

        Yields:
            StreamChunk objects
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True
        }

        if tools:
            kwargs["tools"] = tools

        try:
            stream = await self.async_client.chat.completions.create(**kwargs)

            async for chunk in stream:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                content = delta.content or ""
                tool_calls = None

                if delta.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in delta.tool_calls
                    ]

                yield StreamChunk(
                    content=content,
                    tool_calls=tool_calls,
                    is_finished=finish_reason is not None,
                    finish_reason=finish_reason
                )

        except Exception as e:
            yield StreamChunk(
                content=f"\n[Error: {str(e)}]",
                is_finished=True,
                finish_reason="error"
            )

    def _parse_response(self, response) -> ChatResponse:
        """Parse OpenAI response to ChatResponse. Extract reasoning_content for thinking model compatibility."""
        choice = response.choices[0]
        message = choice.message

        # Extract reasoning_content if available (required for Kimi K2.5 thinking mode)
        reasoning_content = ""
        if hasattr(message, "reasoning_content") and message.reasoning_content is not None:
            reasoning_content = message.reasoning_content

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })

        return ChatResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            model=response.model,
            reasoning_content=reasoning_content,
            usage=response.usage.dict() if response.usage else None,
            finish_reason=choice.finish_reason
        )

    def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Estimate token count for messages.
        This is a rough estimate - actual count may vary.
        """
        total = 0
        for msg in messages:
            # Every message follows <|start|>{role}\n{content}<|end|>\n
            total += 4  # Base tokens per message
            total += len(msg.get("content", "")) // 4  # Rough character-to-token ratio
            total += len(msg.get("role", "")) // 4

        total += 2  # Every reply is primed with <|start|>assistant<|end|>
        return total

    def validate_config(self) -> bool:
        """Validate API configuration by making a test request"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            print(f"API validation failed: {e}")
            return False


# Import asyncio for async sleep
import asyncio
