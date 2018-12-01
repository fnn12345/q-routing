import abc
from random import choice
import random
import collections
import networkx as nx

class PacketRouter:

  __metaclass__ = abc.ABCMeta

  def __init__(self, simulator):
    self.simulator = simulator

  @abc.abstractmethod
  def routePacket(self, packet):
    pass

  @abc.abstractmethod
  def routePacketSingleStep(self, packet, node):
    pass

# randomly hops packet through the network
class RandomPacketRouter(PacketRouter):
  def routePacket(self, packet):
    cur = packet.src
    while cur != packet.dst:
      nxt = choice(list(self.simulator.G.neighbors(cur)))
      self.simulator.traverseEdge(packet, cur, nxt)
      if packet.dropped: break
      cur = nxt

  def routePacketSingleStep(self, packet, node):
      nxt = choice(list(self.simulator.G.neighbors(node)))
      self.simulator.traverseEdge(packet, node, nxt)
      return None if packet.dropped else nxt

# performs Q-routing based on this paper (not predictive):
# https://bit.ly/2PYlvTR

# this algorithm leans heavily on using elapsed time to guide exploration
# we need to maintain some kind of clock that actually keeps track of the current time
# relative to the elapsed time from the simulation
# could be tricky, since packets are being routed in tandem
class QPacketRouter(PacketRouter):

  def __init__(self, simulator, epsilon=0.05, learning_rate=0.01):
    super().__init__(simulator)
    # Q[(x, d, y)] = time that node x estimates it takes to deliver a packet P bound
    # for node d by way of x's neighbour y
    self.Q = collections.defaultdict(float)
    self.epsilon = epsilon
    self.learning_rate = learning_rate

  # returns True with p = epsilon
  def explore(self):
    return random.random() < self.epsilon

  # returns best next step for packet from x to d for minimized Q
  def min_Q(self, x, d):
    x_neighbours = self.simulator.G.neighbors(x)
    min_Q = float('inf')
    min_node = None
    for y in x_neighbours:
      if self.Q[(x, d, y)] < min_Q:
        min_Q = self.Q[(x, d, y)]
        min_node = y
    return min_node, min_Q

  def routePacket(self, packet):
    cur = packet.src
    while cur != packet.dst:
      # select next node with epsilon-greedy strategy
      if self.explore():
        nxt = choice(list(self.simulator.G.neighbors(cur)))
      else:
        nxt, _ = self.min_Q(cur, packet.dst)

      # estimated time remaining from next node
      _, t = self.min_Q(nxt, packet.dst)
      s = self.simulator.traverseEdge(packet, cur, nxt)

      self.Q[(cur, packet.dst, nxt)] = self.Q[(cur, packet.dst, nxt)] + self.learning_rate * (t + s - self.Q[(cur, packet.dst, nxt)])

      # TODO: not sure how to handle dropped packets with r.t.
      # Q-routing, would we add a higher penalty to Q?
      if packet.dropped: break
      cur = nxt

  def routePacketSingleStep(self, packet, node):
      if self.explore():
        nxt = choice(list(self.simulator.G.neighbors(node)))
      else:
        nxt, _ = self.min_Q(node, packet.dst)

      # estimated time remaining from next node
      _, t = self.min_Q(nxt, packet.dst)
      s = self.simulator.traverseEdge(packet, node, nxt)

      self.Q[(node, packet.dst, nxt)] = self.Q[(node, packet.dst, nxt)] + self.learning_rate * (t + s - self.Q[(node, packet.dst, nxt)])
      return None if packet.dropped else nxt

# TODO: only works with connected graphs
class RIPPacketRouter(PacketRouter):
  def __init__(self, simulator, epsilon=0.05, learning_rate=0.01):
    super().__init__(simulator)

    self.routing_table = {}

    for src in simulator.G.nodes():
      for dst in simulator.G.nodes():
        assert(nx.has_path(simulator.G, src, dst))

    for src, destinations in nx.shortest_path(simulator.G).items():
      for dst, path in destinations.items():
        if src == dst:
          hop = None
        else:
          hop = path[1]
        self.routing_table[(src, dst)] = hop

  # perform dijsktras to find shortest path to compute a routing table: (x, d -> y) from node x,
  # with destination d, jump to y for the shortest path
  def routePacket(self, packet):
    cur = packet.src
    while cur != packet.dst:
      nxt = self.routing_table[(cur, packet.dst)]
      self.simulator.traverseEdge(packet, cur, nxt)
      if packet.dropped: break
      cur = nxt

  def routePacketSingleStep(self, packet, node):
      nxt = self.routing_table[(node, packet.dst)]
      self.simulator.traverseEdge(packet, node, nxt)
      return None if packet.dropped else nxt
