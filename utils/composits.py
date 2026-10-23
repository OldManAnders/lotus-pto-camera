"""Composite methods shared by the capture pipeline and the offline tools.

``CompositeMethod`` is an abstract base with a small name registry, so callers
can select a strategy (``mean``, ``median``, ``percentile``) without importing
the concrete classes. Only NumPy is required; this module stays importable
without ``cv2`` so the capture path does not pull in image-codec dependencies.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Type

import numpy as np


class CompositeMethod(ABC):
    """Abstract base and registry for compositing strategies.

    Concrete subclasses register themselves under a short name via the
    ``register`` decorator and are instantiated by name through ``create``,
    allowing callers to select a method without importing it directly.
    """

    _registry: Dict[str, Type["CompositeMethod"]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type["CompositeMethod"]], Type["CompositeMethod"]]:
        """Register a composite subclass under ``name``.

        Args:
            name: Short identifier used to look the method up via ``create``.

        Returns:
            A class decorator that records the subclass and returns it unchanged.
        """
        def _wrap(subclass: Type["CompositeMethod"]) -> Type["CompositeMethod"]:
            """Record ``subclass`` under ``name`` and return it unchanged.

            Args:
                subclass: The concrete composite class being decorated.

            Returns:
                The same class, so the decorator is transparent to callers.
            """
            cls._registry[name] = subclass
            return subclass
        return _wrap

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "CompositeMethod":
        """Instantiate a registered composite method by name.

        Args:
            name: Registered method name (see ``available_methods``).
            **kwargs: Keyword arguments forwarded to the method constructor.

        Returns:
            A new instance of the registered composite method.

        Raises:
            ValueError: If ``name`` is not present in the registry.
        """
        if name not in cls._registry:
            available = ", ".join(sorted(cls._registry)) or "<none registered>"
            raise ValueError(f"Unknown composite method '{name}'. Available: {available}")
        return cls._registry[name](**kwargs)

    @classmethod
    def available_methods(cls) -> List[str]:
        """List the names of all registered composite methods.

        Returns:
            Sorted method names currently present in the registry.
        """
        return sorted(cls._registry)

    @abstractmethod
    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        """Combine a stack of aligned images into a single image.

        Args:
            images: Non-empty list of equally shaped BGR images.

        Returns:
            The composited ``uint8`` image.

        Raises:
            NotImplementedError: Always, unless overridden by a subclass.
        """
        raise NotImplementedError("The scaffolding class does not contain the combine functionality please subclass and implement")

    def __call__(self, images: List[np.ndarray]) -> np.ndarray:
        """Composite ``images`` via ``composite``.

        Args:
            images: Non-empty list of equally shaped BGR images.

        Returns:
            The composited ``uint8`` image.

        Raises:
            ValueError: If ``images`` is empty.
        """
        if not images:
            raise ValueError("Composite requires at least one image")
        return self.composite(images)


# Per-pixel average across the stack.
@CompositeMethod.register("mean")
class MeanComposite(CompositeMethod):
    """Composite method computing the per-pixel mean across the stack."""

    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        """Average ``images`` per pixel.

        Args:
            images: Non-empty list of equally shaped BGR images.

        Returns:
            The per-pixel mean image as ``uint8``.
        """
        acc = np.zeros(images[0].shape, dtype=np.float32)
        for image in images:
            acc += image.astype(np.float32, copy=False)

        result = acc / len(images)
        return np.clip(result, 0, 255).astype(np.uint8)


# Per-pixel median across the stack.
@CompositeMethod.register("median")
class MedianComposite(CompositeMethod):
    """Composite method computing the per-pixel median across the stack."""

    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        """Take the per-pixel median of ``images``.

        Args:
            images: Non-empty list of equally shaped BGR images.

        Returns:
            The per-pixel median image as ``uint8``.
        """
        stack = np.stack(images)
        return np.clip(np.median(stack, axis=0), 0, 255).astype(np.uint8)


# Percentile based sampling.
@CompositeMethod.register("percentile")
class PercentileComposite(CompositeMethod):
    """Composite method selecting a per-pixel percentile across the stack."""

    def __init__(self, percentile: float = 25.0) -> None:
        """Initialize the percentile composite.

        Args:
            percentile: Percentile to sample per pixel, in ``[0, 100]``.
        """
        self.percentile = float(percentile)

    def composite(self, images: List[np.ndarray]) -> np.ndarray:
        """Take the per-pixel percentile of ``images``.

        Args:
            images: Non-empty list of equally shaped BGR images.

        Returns:
            The per-pixel percentile image as ``uint8``.
        """
        stack = np.stack(images)
        return np.clip(np.percentile(stack, self.percentile, axis=0), 0, 255).astype(np.uint8)
