import threading
from queue import Empty, Queue

import can

from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.can import CAN, CANFilter, CANMessage
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class SocketCAN(CAN):
    def __init__(self, name: str, logger: Logger, interface: str):
        super().__init__(name)
        self._interface = interface
        self._logger = logger
        self._bus: can.BusABC | None = None
        self._filters: list[CANFilter] = []
        self._recv_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._recv_messages = Queue[CANMessage]()
        self._recv_event = Event[CANMessage]()

    def init(self) -> Task[()]:
        self._bus = can.Bus(interface="socketcan", channel=self._interface)

        self._recv_thread = threading.Thread(target=self._receiver_thread_func)
        self._recv_thread.start()

        return ImmediateResultTask()

    def close(self) -> None:
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None

    def _receiver_thread_func(self) -> None:
        while self._bus is not None:
            try:
                raw_message = self._bus.recv()
                if raw_message is not None:
                    message = CANMessage(
                        heading=raw_message.arbitration_id,
                        data=bytes(raw_message.data),
                    )
                    self._recv_event.trigger(message)
                    self._recv_messages.put(message)
            except can.CanOperationError as e:
                self._logger.error(f"CAN operation error: {e}")

    def _check_initialized(self) -> None:
        if self._bus is None:
            raise RuntimeError("SocketCAN driver is not initialized")

    def write_sync(self, message: CANMessage) -> None:
        self._check_initialized()
        assert self._bus is not None
        with self._send_lock:
            self._bus.send(
                can.Message(arbitration_id=message.heading, data=message.data, is_extended_id=True)
            )

    def write_async(self, message: CANMessage) -> Task[()]:
        self._check_initialized()
        self.write_sync(message)
        return ImmediateResultTask()

    def read_sync(self, timeout: float | None = None) -> CANMessage:
        self._check_initialized()
        try:
            message = self._recv_messages.get(timeout=timeout, block=timeout is not None)
            return message
        except Empty:
            raise TimeoutError("No CAN message received within timeout")

    def read_async(self) -> Event[CANMessage]:
        return self._recv_event

    def _update_filters(self) -> None:
        self._check_initialized()
        assert self._bus is not None
        with self._send_lock:
            self._bus.set_filters(
                [
                    {"can_id": filter.id, "can_mask": filter.mask, "extended": True}
                    for filter in self._filters
                ]
            )

    def clear_filter(self) -> None:
        self._check_initialized()
        self._filters.clear()
        self._update_filters()

    def add_filter(self, filter: CANFilter) -> None:
        self._check_initialized()
        self._filters.append(filter)
        self._update_filters()


class SocketCANDefininition(DriverDefinition):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        return super().get_init_args_definition()

    def create(self, args: DriverInitArgs) -> SocketCAN:
        return SocketCAN(
            name=args.get_name(),
            logger=self._logger,
            interface=args.get("interface"),
        )
