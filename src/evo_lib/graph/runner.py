"""Graph runner: binds a graph to a scheduler and runs nodes."""

from evo_lib.scheduler import Scheduler
from evo_lib.graph.graph import Graph, Node


class GraphRunner:
    def __init__(self, scheduler: Scheduler):
        self._scheduler = scheduler

    def bind_graph(self, graph: Graph) -> None:
        """Bind a graph to this runner so its nodes can be scheduled."""
        if graph._runner is not None and graph._runner is not self:
            raise ValueError("Trying to bind an already bound graph to a runner")
        graph._runner = self

    def run_node(self, node: Node) -> None:
        """Schedule a node for execution."""
        if node._graph._runner is not self:
            raise ValueError("Trying to run a node on a graph not bound to this runner")
        self._scheduler.schedule_now(0, node.run)
