"""
Generic registry module.

This module provides a generic registry implementation to manage named items
with a freeze mechanism to prevent further modifications.
"""


class FrozenError(Exception):
    """Exception raised when trying to modify a frozen registry."""
    pass


class Registry[T]:
    """
    A generic registry to store and retrieve items by name.

    The registry can be frozen to prevent adding new items.
    """

    def __init__(self, name: str) -> None:
        """
        Initialize the registry.

        Args:
            name: The name of the registry (used for error messages).
        """
        super().__init__()
        self._name = name
        self._items: dict[str,T] = dict()
        self._frozen: bool = False

    def get_name(self) -> str:
        """Get the name of the registry."""
        return self._name

    def register(self, key: str, item: T) -> None:
        """
        Register a new item.

        Args:
            key: The unique name/key for the item.
            item: The item to register.

        Raises:
            FrozenError: If the registry is frozen.
            KeyError: If the key is already registered.
        """
        if not isinstance(key, str):
            raise TypeError(f"Registry keys must be strings, got {type(key).__name__}")
        if self._frozen:
            raise FrozenError(f"Registry '{self._name}' has been frozen")
        if key in self._items:
            raise KeyError(f"Entry '{key}' is already registered in registry {self._name}")
        self._items[key] = item

    def get_all(self) -> list[T]:
        """Get all registered items."""
        return list(self._items.values())

    def get_keys(self) -> list[str]:
        """Get all registered keys."""
        return list(self._items.keys())

    def get_entries(self) -> list[tuple[str, T]]:
        """Get all registered key-item pairs."""
        return list(self._items.items())

    def get(self, key: str) -> T:
        """
        Get an item by its key.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The registered item.

        Raises:
            KeyError: If the key is not found.
        """
        if key not in self._items:
            raise KeyError(f"Entry '{key}' not found in registry '{self._name}'")
        return self._items[key]

    def freeze(self) -> None:
        """Freeze the registry, preventing further registrations."""
        self._frozen = True

    def has(self, key: str) -> bool:
        """Check if a key is registered in the registry."""
        return key in self._items
