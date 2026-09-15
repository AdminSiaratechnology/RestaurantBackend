from typing import Dict, Type

from .base import BasePlatformAdapter
from .mock import MockPlatformAdapter


class PlatformRegistry:

    _adapters: Dict[
        str,
        Type[BasePlatformAdapter]
    ] = {}

    @classmethod
    def register(
        cls,
        platform: str,
        adapter_class: Type[BasePlatformAdapter],
    ) -> None:

        cls._adapters[
            platform.lower()
        ] = adapter_class

    @classmethod
    def get_adapter_class(
        cls,
        platform: str,
    ) -> Type[BasePlatformAdapter]:

        adapter = cls._adapters.get(
            platform.lower()
        )

        if not adapter:
            raise ValueError(
                f"No adapter registered for platform: {platform}"
            )

        return adapter

    @classmethod
    def create(
        cls,
        platform: str,
        connection,
        config: dict | None = None,
    ) -> BasePlatformAdapter:

        adapter_class = cls.get_adapter_class(
            platform
        )

        return adapter_class(
            connection=connection,
            config=config,
        )

    @classmethod
    def available_platforms(
        cls,
    ) -> list[str]:

        return list(cls._adapters.keys())


# Register adapters

PlatformRegistry.register(
    "mock",
    MockPlatformAdapter,
)