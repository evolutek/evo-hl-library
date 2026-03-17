from typing import Callable


class Listener[*T]:
    """An entry in the ``Listeners`` class."""
    def __init__(self, callback: Callable[[*T], None], onetime: bool) -> None:
        self._callback = callback
        self._onetime = onetime


class Listeners[*T]:
    """
    Utils class to manage a list of callback with three methods:
    - ``register``
    - ``unregister``
    - ``trigger``

    This class is not threads-safe. Use the ``Event`` class if you want a
    threads-safe version with additional features.
    """

    def __init__(self) -> None:
        self._listeners: list[Listener[*T]] = []

    def _trigger(self) -> list[Listener]:
        """Return the list of listener to call when trigger and remove all
        onetime listeners from the listeners.
        """
        new_listeners: list[Listener] = []

        for listener in self._listeners:
            if not listener._onetime:
                new_listeners.append(listener)

        listeners_to_call = self._listeners
        self._listeners = new_listeners

        return listeners_to_call

    def trigger(self, *args: *T) -> None:
        """Call all listeners with arguments."""
        listeners_to_call = self._trigger()
        for listener in listeners_to_call:
            listener._callback(*args)

    def register(self, callback: Callable[[*T], None], onetime: bool = False) -> Listener:
        listener = Listener(callback, onetime)
        self._listeners.append(listener)
        return listener

    def unregister(self, listener: Listener) -> None:
        self._listeners.remove(listener)
