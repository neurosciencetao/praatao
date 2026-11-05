"""Optional model back-ends for the Praatao tutor.

Only the standard library is used: ``urllib.request`` performs the HTTP call
and ``json`` encodes the payload.

Three capabilities are needed, and they are deliberately kept behind
**separate, swappable seams** so that a better model can replace any one of
them without touching the tutor:

=====================  ====================================================
capability             interface
=====================  ====================================================
chat                   :meth:`ModelBackend.chat`
vision (read an image) :meth:`ModelBackend.chat_with_image`
image generation       :meth:`ImageBackend.generate_image`
=====================  ====================================================

A backend is *any* object that implements those methods.  The bundled
:class:`OpenAiCompatibleBackend` covers MiniMax, DeepSeek, OpenAI, Qwen-VL,
SiliconFlow, vLLM, LM Studio ... (they all speak the same dialect), and
:class:`MiniMaxImageBackend` covers MiniMax's ``/image_generation`` endpoint.

Configuration comes from the environment first, and falls back to the
credential store of the DeepSeek Harness, so the tool works out of the box on
the machine that already runs DSH:

==========================  ==============================================
``PRAATAO_LLM_ENDPOINT``     base URL, e.g. ``https://api.minimaxi.com/v1``
``PRAATAO_LLM_MODEL``        chat model, e.g. ``MiniMax-M3.1-Flash``
``PRAATAO_LLM_API_KEY``      bearer token (never written to the repo)
``PRAATAO_LLM_BACKEND``      ``'openai'`` (default) or ``'ollama'``
``PRAATAO_IMAGE_MODEL``      image-generation model, e.g. ``image-01``
``PRAATAO_VISION``           ``1`` to allow sending images to the model
==========================  ==============================================

**Images are never uploaded unless the user turns that on.**  A Praat
spectrogram can show a participant's voice, so the drawing-area feature
defaults to a purely local analysis; ``PRAATAO_VISION=1`` is the explicit
opt-in.  The tutor's primary mode stays fully offline: with no configuration
the client reports itself as unavailable and every call returns ``None``
instead of raising.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable
from urllib.parse import urlsplit

__all__ = [
    "LlmClient",
    "NullLlmClient",
    "LlmConfig",
    "ImageInput",
    "ModelBackend",
    "ImageBackend",
    "OpenAiCompatibleBackend",
    "OllamaBackend",
    "MiniMaxImageBackend",
    "NullImageBackend",
    "default_llm_client",
    "describe_config",
    "read_dsh_api_key",
    "ENV_ENDPOINT",
    "ENV_MODEL",
    "ENV_API_KEY",
    "ENV_BACKEND",
    "ENV_IMAGE_MODEL",
    "ENV_VISION",
    "ENV_LLM_OFF",
    "ENV_IMAGEGEN",
    "BACKEND_OPENAI",
    "BACKEND_OLLAMA",
    "MINIMAX_ENDPOINT",
    "MINIMAX_MODEL",
    "MINIMAX_IMAGE_MODEL",
    "DSH_CREDENTIALS_PATH",
    "DSH_KEY_REF",
    "DEFAULT_TIMEOUT",
]

#: Environment variable names (kept public so the UI can show them).
ENV_ENDPOINT = "PRAATAO_LLM_ENDPOINT"
ENV_MODEL = "PRAATAO_LLM_MODEL"
ENV_API_KEY = "PRAATAO_LLM_API_KEY"
ENV_BACKEND = "PRAATAO_LLM_BACKEND"
ENV_IMAGE_MODEL = "PRAATAO_IMAGE_MODEL"
ENV_VISION = "PRAATAO_VISION"
ENV_LLM_OFF = "PRAATAO_LLM_OFF"
ENV_IMAGEGEN = "PRAATAO_IMAGEGEN"

BACKEND_OPENAI = "openai"
BACKEND_OLLAMA = "ollama"

#: MiniMax China defaults.  MiniMax speaks the OpenAI dialect, so the chat
#: endpoint is the ordinary ``/v1/chat/completions``.
MINIMAX_ENDPOINT = "https://api.minimaxi.com/v1"
MINIMAX_MODEL = "MiniMax-M3.1-Flash"
MINIMAX_IMAGE_MODEL = "image-01"

#: Where the DeepSeek Harness keeps the MiniMax key.
DSH_CREDENTIALS_PATH = Path.home() / ".dsh" / ".credentials.yaml"
DSH_KEY_REF = "MINIMAX_CN_API_KEY"

#: Default per-request timeout in seconds.
DEFAULT_TIMEOUT = 30.0
#: Image generation is much slower than a chat turn.
DEFAULT_IMAGE_TIMEOUT = 90.0

#: Failures are written to stderr at most once per this many seconds.
DEFAULT_LOG_INTERVAL = 60.0

_OPENAI_ALIASES = {
    "",
    "openai",
    "openai-compatible",
    "openai_compatible",
    "openai_compat",
    "deepseek",
    "deepseek-chat",
    "deepseek-reasoner",
    "azure",
    "vllm",
    "lmstudio",
    "siliconflow",
    "moonshot",
    "qwen",
    "qwen-vl",
    "openrouter",
    "minimax",
    "minimax-cn",
}

_OLLAMA_ALIASES = {"ollama", "ollama-chat", "ollama_chat", "ollamaapi"}


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LlmConfig:
    """Immutable snapshot of the model configuration."""

    endpoint: str = ""
    model: str = ""
    api_key: str = ""
    backend: str = BACKEND_OPENAI
    image_model: str = ""
    #: Uploading an image to the model is opt-in.
    allow_vision: bool = False
    #: Drawing a teaching picture is opt-in: it costs money and takes
    #: fifteen seconds, so it only runs when the student is really stuck.
    allow_imagegen: bool = False
    #: Where the configuration came from, for the status line.
    source: str = "env"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        dsh_fallback: bool = True,
        dsh_path: Path | None = None,
    ) -> "LlmConfig":
        """Build a config from ``env`` (defaults to :data:`os.environ`).

        When the environment says nothing about the endpoint, the MiniMax
        credentials of the DeepSeek Harness are used, so the tool works on
        this machine without any setup.  Set ``dsh_fallback=False`` to
        disable that.
        """

        source: Mapping[str, str] = os.environ if env is None else env
        raw_backend = (source.get(ENV_BACKEND) or "").strip().lower()
        if raw_backend in _OLLAMA_ALIASES:
            backend = BACKEND_OLLAMA
        else:
            # Unknown value: stay on the widely compatible dialect.
            backend = BACKEND_OPENAI

        if _truthy(source.get(ENV_LLM_OFF)):
            # The master switch: no model at all, not even the fallback.
            return cls(source="off")

        endpoint = (source.get(ENV_ENDPOINT) or "").strip()
        model = (source.get(ENV_MODEL) or "").strip()
        api_key = (source.get(ENV_API_KEY) or "").strip()
        image_model = (source.get(ENV_IMAGE_MODEL) or "").strip()
        allow_vision = _truthy(source.get(ENV_VISION))
        allow_imagegen = _truthy(source.get(ENV_IMAGEGEN))
        origin = "env"

        if not endpoint and dsh_fallback:
            key = read_dsh_api_key(dsh_path)
            if key:
                endpoint = MINIMAX_ENDPOINT
                model = model or MINIMAX_MODEL
                image_model = image_model or MINIMAX_IMAGE_MODEL
                api_key = api_key or key
                origin = "dsh"

        return cls(
            endpoint=endpoint,
            model=model,
            api_key=api_key,
            backend=backend,
            image_model=image_model,
            allow_vision=allow_vision,
            allow_imagegen=allow_imagegen,
            source=origin,
        )

    def is_configured(self) -> bool:
        """True when an endpoint is set (the only hard requirement)."""

        return bool(self.endpoint)

    def host(self) -> str:
        """Short, human-readable host of the endpoint (no scheme/path)."""

        if not self.endpoint:
            return ""
        try:
            parts = urlsplit(self.endpoint)
        except ValueError:
            return self.endpoint
        return parts.netloc or parts.path or self.endpoint

    def chat_url(self) -> str:
        """Full URL of the chat endpoint for the selected backend."""

        base = self.endpoint.rstrip("/")
        if self.backend == BACKEND_OLLAMA:
            suffix = "/api/chat"
        else:
            suffix = "/chat/completions"
        if base.endswith(suffix):
            return base
        return base + suffix

    def image_url(self) -> str:
        """Full URL of the image-generation endpoint."""

        base = self.endpoint.rstrip("/")
        suffix = "/image_generation"
        if base.endswith(suffix):
            return base
        return base + suffix


def _truthy(value: Any) -> bool:
    """Is an environment value a yes?"""

    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enable",
                                                 "enabled"}


def read_dsh_api_key(path: Path | None = None) -> str:
    """Read the MiniMax key out of the DSH credential store.

    The file looks like this::

        version: 1
        records:
          ...
        refs:
          MINIMAX_CN_API_KEY: sk-cp-...

    Only the ``refs`` section is read, and only a plain value: an indirect
    reference (``keychain:...``) is ignored, because this tool must not
    guess at another program's credential protocol.  The key is never
    printed or logged.
    """

    target = Path(path) if path is not None else DSH_CREDENTIALS_PATH
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

    in_refs = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            in_refs = stripped.lower().startswith("refs:")
            continue
        if not in_refs:
            continue
        key, _, value = raw.partition(":")
        if key.strip() != DSH_KEY_REF:
            continue
        value = value.strip().strip("'\"")
        if not value or re.match(r"^[a-z]+://", value, re.I):
            return ""
        return value
    return ""


# --------------------------------------------------------------------------
# the swappable seams
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageInput:
    """One image to be shown to a model.

    Either give a ``path`` or raw ``data``.  ``mime`` is guessed from the
    file name when it is not given.
    """

    path: Path | None = None
    data: bytes | None = None
    mime: str = "image/png"

    @classmethod
    def from_path(cls, path: str | Path) -> "ImageInput":
        p = Path(path)
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return cls(path=p, mime=mime)

    def read_bytes(self) -> bytes:
        """The raw image bytes (empty when unreadable)."""

        if self.data is not None:
            return self.data
        if self.path is None:
            return b""
        try:
            return self.path.read_bytes()
        except Exception:
            return b""

    def data_uri(self) -> str:
        """The image as a ``data:`` URI, ready for an OpenAI-style payload."""

        blob = self.read_bytes()
        if not blob:
            return ""
        return f"data:{self.mime};base64," + base64.b64encode(blob).decode("ascii")


@runtime_checkable
class ModelBackend(Protocol):
    """Anything that can answer a prompt (optionally with images)."""

    name: str

    def chat(self, system: str, user: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
        ...

    def chat_with_image(
        self,
        system: str,
        user: str,
        images: Sequence[ImageInput],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str | None:
        ...


@runtime_checkable
class ImageBackend(Protocol):
    """Anything that can draw a picture from a prompt."""

    name: str

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> bytes | None:
        ...


# --------------------------------------------------------------------------
# HTTP plumbing
# --------------------------------------------------------------------------


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    api_key: str,
    timeout: float,
    log: "ErrorLog",
) -> dict[str, Any] | None:
    """POST a JSON payload and decode the JSON answer.  Never raises."""

    try:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "praatao/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        data = json.loads(raw.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
        log.write(f"HTTP {exc.code} {exc.reason}")
        return None
    except Exception as exc:  # noqa: BLE001 - the client must never raise
        log.write(f"{type(exc).__name__}: {exc}")
        return None


class ErrorLog:
    """Write a failure to stderr at most once per ``interval`` seconds."""

    def __init__(self, interval: float = DEFAULT_LOG_INTERVAL, prefix: str = "LLM") -> None:
        self.interval = float(interval)
        self.prefix = prefix
        self._last = 0.0

    def write(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last < self.interval:
            return
        self._last = now
        try:
            print(f"[praatao] {self.prefix} request failed: {message}", file=sys.stderr)
        except Exception:  # pragma: no cover - stderr may be closed
            pass


# --------------------------------------------------------------------------
# back-ends
# --------------------------------------------------------------------------


class OpenAiCompatibleBackend:
    """Chat (and vision) against any OpenAI-compatible endpoint.

    MiniMax, DeepSeek, OpenAI, Qwen-VL, SiliconFlow, vLLM and LM Studio all
    accept ``POST {endpoint}/chat/completions`` with a bearer token, and all
    of the multimodal ones accept an ``image_url`` part holding a ``data:``
    URI.
    """

    name = "openai"

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = "",
        *,
        log: ErrorLog | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout)
        self._log = log or ErrorLog()

    def chat_url(self) -> str:
        suffix = "/chat/completions"
        return self.endpoint if self.endpoint.endswith(suffix) else self.endpoint + suffix

    def chat(self, system: str, user: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        data = _post_json(self.chat_url(), payload, self.api_key,
                          timeout or self.timeout, self._log)
        return _extract_content(data) if data else None

    def chat_with_image(
        self,
        system: str,
        user: str,
        images: Sequence[ImageInput],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str | None:
        parts: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for image in images:
            uri = image.data_uri()
            if not uri:
                continue
            parts.append({"type": "image_url", "image_url": {"url": uri}})
        if len(parts) == 1:
            return self.chat(system, user, timeout)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": parts},
            ],
            "stream": False,
        }
        data = _post_json(self.chat_url(), payload, self.api_key,
                          timeout or self.timeout, self._log)
        return _extract_content(data) if data else None


class OllamaBackend:
    """Chat against a local Ollama server."""

    name = "ollama"

    def __init__(
        self,
        endpoint: str,
        model: str,
        *,
        log: ErrorLog | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = float(timeout)
        self._log = log or ErrorLog()

    def chat_url(self) -> str:
        suffix = "/api/chat"
        return self.endpoint if self.endpoint.endswith(suffix) else self.endpoint + suffix

    def chat(self, system: str, user: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        data = _post_json(self.chat_url(), payload, "", timeout or self.timeout, self._log)
        return _extract_content(data) if data else None

    def chat_with_image(
        self,
        system: str,
        user: str,
        images: Sequence[ImageInput],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str | None:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": user},
                {"role": "user", "content": images[0].read_bytes().decode("latin-1")
                 if images else ""},
            ],
            "stream": False,
        }
        data = _post_json(self.chat_url(), payload, "", timeout or self.timeout, self._log)
        return _extract_content(data) if data else None


class MiniMaxImageBackend:
    """Image generation through an OpenAI-style ``/image_generation`` endpoint.

    MiniMax calls the model ``image-01`` and answers with a URL that has to
    be downloaded.  Swapping in another provider means implementing
    :class:`ImageBackend` and handing it to :class:`LlmClient`; nothing else
    in the tutor changes.
    """

    name = "image"

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = "",
        *,
        log: ErrorLog | None = None,
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout)
        self._log = log or ErrorLog(prefix="image generation")

    def image_url(self) -> str:
        suffix = "/image_generation"
        return self.endpoint if self.endpoint.endswith(suffix) else self.endpoint + suffix

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> bytes | None:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
            "response_format": "url",
        }
        data = _post_json(self.image_url(), payload, self.api_key,
                          timeout or self.timeout, self._log)
        if not data:
            return None
        url = _first_image_url(data)
        if not url:
            return None
        return _download(url, timeout or self.timeout, self._log)


class NullImageBackend:
    """An image back-end that never draws anything."""

    name = "none"

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> bytes | None:
        return None


# --------------------------------------------------------------------------
# the client
# --------------------------------------------------------------------------


class LlmClient:
    """The tutor's model client.

    Every public method is total: nothing raises, network problems degrade to
    ``None``/``False``.  The chat side and the image side are separate
    objects, so either can be replaced without touching the other.
    """

    def __init__(
        self,
        config: LlmConfig | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        log_interval: float = DEFAULT_LOG_INTERVAL,
        backend: ModelBackend | None = None,
        image_backend: ImageBackend | None = None,
    ) -> None:
        self.config = config if config is not None else LlmConfig.from_env()
        self.timeout = float(timeout)
        self.log_interval = float(log_interval)
        self._log = ErrorLog(log_interval)
        self._backend = backend
        self._image_backend = image_backend

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_env(cls, **kwargs: Any) -> "LlmClient":
        """Build a client from the process environment."""

        return cls(LlmConfig.from_env(), **kwargs)

    # ------------------------------------------------------------------
    # back-ends
    # ------------------------------------------------------------------
    def backend(self) -> ModelBackend:
        """The chat back-end, built lazily from the configuration."""

        if self._backend is None:
            cfg = self.config
            if cfg.backend == BACKEND_OLLAMA:
                self._backend = OllamaBackend(
                    cfg.endpoint, cfg.model, log=self._log, timeout=self.timeout
                )
            else:
                self._backend = OpenAiCompatibleBackend(
                    cfg.endpoint, cfg.model, cfg.api_key,
                    log=self._log, timeout=self.timeout,
                )
        return self._backend

    def image_backend(self) -> ImageBackend:
        """The image back-end, built lazily from the configuration."""

        if self._image_backend is None:
            cfg = self.config
            if cfg.image_model and cfg.endpoint:
                self._image_backend = MiniMaxImageBackend(
                    cfg.endpoint, cfg.image_model, cfg.api_key,
                    log=self._log, timeout=DEFAULT_IMAGE_TIMEOUT,
                )
            else:
                self._image_backend = NullImageBackend()
        return self._image_backend

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def available(self) -> bool:
        """True when the client is configured well enough to try a request."""

        return self.config.is_configured()

    def supports_vision(self) -> bool:
        """True when images may be sent to the model.

        This is the opt-in that keeps participant recordings on the machine:
        a Praat spectrogram is a picture of somebody's voice.
        """

        return bool(self.available() and self.config.allow_vision)

    def supports_image_generation(self) -> bool:
        """True when the model can draw a picture.

        Drawing a picture is opt-in for the same reason as vision: it costs
        money and takes far longer than a chat turn, so it only runs when
        the user asked for it.
        """

        return bool(
            self.available() and self.config.image_model and self.config.allow_imagegen
        )

    def chat(self, system: str, user: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
        """Send one chat turn and return the assistant text.

        Returns ``None`` on *any* failure (missing configuration, DNS error,
        HTTP 401, malformed JSON, timeout).  The method never raises.
        """

        if not self.available():
            return None
        try:
            return self.backend().chat(system, user, timeout)
        except Exception as exc:  # noqa: BLE001 - the client must never raise
            self._log.write(f"{type(exc).__name__}: {exc}")
            return None

    def chat_with_image(
        self,
        system: str,
        user: str,
        images: Sequence[ImageInput],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str | None:
        """Send a chat turn that shows the model one or more images.

        Returns ``None`` when vision is switched off
        (:attr:`LlmConfig.allow_vision`), so a caller cannot accidentally
        ship a screenshot of somebody's voice.
        """

        if not self.supports_vision():
            return None
        usable = [image for image in images if image.read_bytes()]
        if not usable:
            return None
        try:
            return self.backend().chat_with_image(system, user, usable, timeout)
        except Exception as exc:  # noqa: BLE001 - the client must never raise
            self._log.write(f"{type(exc).__name__}: {exc}")
            return None

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> bytes | None:
        """Draw a picture.  Returns the image bytes, or ``None``."""

        if not self.supports_image_generation():
            return None
        try:
            return self.image_backend().generate_image(
                prompt, aspect_ratio=aspect_ratio, timeout=timeout
            )
        except Exception as exc:  # noqa: BLE001 - the client must never raise
            self._log.write(f"{type(exc).__name__}: {exc}")
            return None

    def describe_config(self, lang: str = "zh") -> str:
        """One-line status of this client, meant for a UI status line."""

        zh = lang == "zh"
        if not self.available():
            return "LLM：未启用（离线模式）" if zh else "LLM: off (offline mode)"
        model = self.config.model or ("（未指定模型）" if zh else "(no model set)")
        host = self.config.host() or self.config.endpoint
        extra = []
        if self.config.allow_vision:
            extra.append("识图开" if zh else "vision on")
        if self.config.image_model and self.config.allow_imagegen:
            extra.append("生图开" if zh else "image-gen on")
        tail = (" · " + " · ".join(extra)) if extra else ""
        if zh:
            return f"LLM：已开启 · {self.config.backend} · {model} · {host}{tail}"
        return f"LLM: on · {self.config.backend} · {model} · {host}{tail}"


class NullLlmClient(LlmClient):
    """A client that is always unavailable - the default, offline mode."""

    def __init__(self, reason: str = "") -> None:
        super().__init__(LlmConfig())
        self.reason = reason

    def available(self) -> bool:
        return False

    def chat(self, system: str, user: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
        return None

    def chat_with_image(
        self,
        system: str,
        user: str,
        images: Sequence[ImageInput],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str | None:
        return None

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> bytes | None:
        return None

    def describe_config(self, lang: str = "zh") -> str:
        zh = lang == "zh"
        if self.reason:
            suffix = f"（{self.reason}）" if zh else f" ({self.reason})"
        else:
            suffix = ""
        return ("LLM：未启用（离线模式）" if zh else "LLM: off (offline mode)") + suffix


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _extract_content(data: Any) -> str | None:
    """Pull the assistant text out of an OpenAI- or Ollama-shaped payload."""

    if not isinstance(data, dict):
        return None

    # OpenAI chat-completions.
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                text = _as_text(message.get("content"))
                if text:
                    return text
            text = _as_text(first.get("text"))
            if text:
                return text

    # Ollama chat.
    message = data.get("message")
    if isinstance(message, dict):
        text = _as_text(message.get("content"))
        if text:
            return text

    # Ollama completions / generic fallback.
    text = _as_text(data.get("response"))
    if text:
        return text
    return None


def _as_text(value: Any) -> str | None:
    """Coerce a content value (string or list of parts) into plain text."""

    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "".join(parts)
    return None


def _first_image_url(data: Mapping[str, Any]) -> str:
    """Find the first generated-image URL in a provider payload."""

    block = data.get("data")
    if isinstance(block, Mapping):
        urls = block.get("image_urls")
        if isinstance(urls, list):
            for item in urls:
                if isinstance(item, str) and item:
                    return item
        url = block.get("url")
        if isinstance(url, str) and url:
            return url
    for key in ("image_url", "url"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _download(url: str, timeout: float, log: ErrorLog) -> bytes | None:
    """Fetch a generated image.  Never raises."""

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
        log.write(f"HTTP {exc.code} {exc.reason}")
        return None
    except Exception as exc:  # noqa: BLE001
        log.write(f"{type(exc).__name__}: {exc}")
        return None


def default_llm_client() -> LlmClient:
    """Return an env-configured client, or a :class:`NullLlmClient`."""

    client = LlmClient.from_env()
    if client.available():
        return client
    return NullLlmClient()


def describe_config(lang: str = "zh") -> str:
    """Status line for the environment-configured default client."""

    return default_llm_client().describe_config(lang=lang)
