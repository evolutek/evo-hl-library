"""Graph runner: binds a graph to a scheduler and runs nodes."""

#from evo_lib.graph.graph import Graph, Node
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


class GraphRunner:
    def __init__(self, logger: Logger, scheduler: Scheduler):
        self._scheduler = scheduler
        self._logger = logger

    def get_logger(self) -> Logger:
        return self._logger

    def get_scheduler(self) -> Scheduler:
        return self._scheduler

    # def bind_graph(self, graph: Graph) -> None:
    #     """Bind a graph to this runner so its nodes can be scheduled."""
    #     if graph._runner is not None and graph._runner is not self:
    #         raise ValueError("Trying to bind an already bound graph to a runner")
    #     graph._runner = self

    # def run_node(self, node: Node) -> None:
    #     """Schedule a node for execution."""
    #     if node._graph._runner is not self:
    #         raise ValueError("Trying to run a node on a graph not bound to this runner")
    #     self._scheduler.schedule_now(0, node.on_run)
