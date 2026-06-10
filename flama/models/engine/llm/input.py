import dataclasses
import typing as t

__all__ = ["EngineInput"]

if t.TYPE_CHECKING:
    import numpy as np
    from PIL.Image import Image as PILImage


@dataclasses.dataclass(frozen=True)
class EngineInput:
    """Engine-ready bundle (L3).

    Owns the token IDs that an :class:`~flama.models.engine.backend.llm._base.LLMBackend` feeds straight into its
    engine, plus the per-modality decoded payloads that travel alongside (PIL images,
    ``(samples, sample_rate)`` audio waveforms). The L2 to L3 conversion lives on
    :meth:`~flama.models.engine.backend.llm._base.LLMBackend.prepare_input`.

    :param tokens: Pre-rendered prompt token IDs (BOS already included by the template).
    :param images: Decoded image payloads in the order they appear in the message list.
    :param audios: Decoded audio payloads as ``(samples, sample_rate)`` pairs in the order they appear.
    """

    tokens: list[int]
    images: tuple["PILImage", ...] = ()
    audios: tuple[tuple["np.ndarray", int], ...] = ()
