import math
import struct
import time
from queue import Empty, Full, Queue
from threading import Thread
from typing import Iterator

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.lidar.virtual import Lidar2DVirtual
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.interfaces.serial import Serial
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

_MEASURES_QUEUE_LENGTH = 10000


class LD06LidarDriver(Lidar2D):
    def __init__(self, name: str, logger: Logger, serial: Serial):
        super().__init__(name)
        self._log = logger
        self._serial = serial
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._scan_thread: Thread | None = None
        self._running: bool = False
        self._measures: Queue[Lidar2DMeasure] = Queue(maxsize = _MEASURES_QUEUE_LENGTH)

    def init(self) -> Task[()]:
        self._log.info(f"LD06 lidar '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self.stop().wait()
        self._log.info(f"LD06 lidar '{self.name}' closed")

    def start(self) -> Task[()]:
        if self._running:
            return ImmediateResultTask()
        self._running = True
        self._scan_thread = Thread(target=self._scan_loop)
        self._scan_thread.start()
        return ImmediateResultTask()

    def stop(self) -> Task[()]:
        if not self._running:
            return ImmediateResultTask()
        self._running = False
        if self._scan_thread is not None:
            self._scan_thread.join(timeout=1.0)
            if self._scan_thread.is_alive():
                self._log.error(f"Failed to stop LD06 lidar '{self.name}' thread")
            self._scan_thread = None
        return ImmediateResultTask()

    @staticmethod
    def _process_packet(packet: bytes) -> list[Lidar2DMeasure]:
        ## Some things are commented out for efficiency. Uncomment if you need them.
        ## Packet Header
        #speed = struct.unpack('<H', packet[0:2])[0] #Bytes 0 and 1, little endian, degrees per second
        startangle = struct.unpack('<H', packet[2:4])[0] / 100 #Bytes 2 and 3, little endian, convert to float

        ## Packet Footer
        endangle = struct.unpack('<H', packet[40:42])[0] / 100 #Bytes 40 and 41, little endian, convert to float
        #timestamp = struct.unpack('<H', packet[42:44])[0] #Bytes 42 and 43
        #crc = struct.unpack('<B', packet[44:45])[0] #Byte 44

        #print("Speed:", speed, "Start Angle:", startangle, "End Angle:", endangle, "TimeStamp:", timestamp, "CRC:", crc)

        ## Packet Data
        if(endangle - startangle > 0):
            angleStep = float(endangle - startangle) / 12
        else:
            angleStep = float((endangle + 360) - startangle) / 12

        angleStep %= 360 # Normalize angleStep to 0-360

        data = []
        num_readings = 12 # 12 readings per packet
        bytes_per_reading = 3 # 3 bytes per reading: 2 for distance, 1 for intensity
        sample_ratio = 1 # 1 = process every reading, 2 = process every other packet, etc.

        for i in range(0, num_readings * bytes_per_reading, 3 * sample_ratio):
            angle = round((angleStep * i / 3 + startangle) % 360, 1) # Angle of the reading, Degrees
            distance = struct.unpack('<H', packet[4+i:6+i])[0] # First 2 bytes of the data structure, little endian, distance in mm
            quality = struct.unpack('<B', packet[6+i:7+i])[0] # Last byte of the data structure, intensity of returned light, 0-255
            data.append(Lidar2DMeasure(math.radians(angle), distance, time.monotonic(), quality / 255.0))

        return data

    def iter(self, duration: float | None = None) -> Iterator[Lidar2DMeasure]:
        start = time.monotonic()
        while True:
            if duration is not None and time.monotonic() - start >= duration:
                return
            if self._measures:
                try:
                    yield self._measures.get(block = True, timeout = 0.1)
                except Empty:
                    pass

    def _scan_loop(self) -> None:
        """Background thread: read scans and fire events."""

        # New adafruit RPLidar implementation
        while self._running:
            byte = self._serial.read(1)
            if byte == b'\x54':  # Packet Header
                byte = self._serial.read(1)
                if byte == b'\x2c':  # Packet Version
                    packet = self._serial.read(45)
                    measures = LD06LidarDriver._process_packet(packet)
                    self._scan_event.trigger(measures)
                    for measure in measures:
                        try:
                            self._measures.put_nowait(measure)
                        except Full:
                            pass
            # else:
            #     self._log.warning("Invalid packet LD06 lidar packet")


class LD06LidarDriverDefinition(DriverDefinition):
    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(Lidar2D.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        args = DriverInitArgsDefinition()
        args.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return args

    def create(self, args: DriverInitArgs) -> Peripheral:
        return LD06LidarDriver(
            name=args.get_name(),
            logger=self._logger,
            serial=args.get("serial")
        )


class LD06LidarVirtual(Lidar2DVirtual):
    """Drop-in virtual twin for LD06LidarDriver.

    Constructor mirrors LD06LidarDriver exactly so a config swap is a
    one-line change. The ``serial`` bus is kept for signature parity; the
    bus itself may be a real or virtual Serial (orthogonal choice).
    """

    def __init__(self, name: str, logger: Logger, serial: Serial):
        super().__init__(name, logger)
        self._serial = serial


class LD06LidarVirtualDefinition(DriverDefinition):
    """Factory for LD06LidarVirtual — args mirror LD06LidarDriverDefinition."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(Lidar2D.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        args = DriverInitArgsDefinition()
        args.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return args

    def create(self, args: DriverInitArgs) -> Peripheral:
        return LD06LidarVirtual(
            name=args.get_name(),
            logger=self._logger,
            serial=args.get("serial"),
        )
