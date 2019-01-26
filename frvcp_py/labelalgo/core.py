from typing import List, Any
from enum import Enum
class NodeType(Enum):
  DEPOT = 0,
  CUSTOMER = 1,
  CHARGING_STATION = 2

class Node(object):
  def __init__(self, node_id: int, name: str, type: NodeType):
    """Defines a node for the graph underlying an FRVCP."""
    self.node_id = node_id
    self.name = name
    self.type = type

  def __str__(self):
    return f'({self.node_id}; {self.type})'

class HeapE(object):
  """Represents an element in the labeling algorithm's heap.
  Since the data type used for heap nodes in the labeling
  algorithm is just int, this object is largely unnecessary.
  We keep it here to maintain consistency"""
  def __init__(self, data: Any):
    self.data = data

from queue import PriorityQueue
import heapq
class PseudoFibonacciHeap(PriorityQueue):
  """Defines a priority queue whose keys can be updated.
  This mimics the Fibonacci heap object used in the original labeling
  algorithm, allowing for increase-/decrease-key functionality.
  However, the underlying implementation is not actually a Fibonacci 
  heap, so it lacks the nice theoretical advantages.
  """
  def __init__(self):
    self._pq = []                         # list of entries arranged in a heap
    self._entry_finder = {}               # mapping of tasks to entries
    self._REMOVED = '<removed-task>'      # placeholder for a removed task
    import itertools
    self._counter = itertools.count()     # unique sequence count

  def add_task(self, task: Any, priority: float=0):
      'Add a new task or update the priority of an existing task'
      if task in self._entry_finder:
          self.remove_task(task)
      count = next(self._counter)
      entry = [priority, count, task]
      self._entry_finder[task] = entry
      heapq.heappush(self._pq, entry)

  def remove_task(self, task: Any):
      'Mark an existing task as REMOVED.  Raise KeyError if not found.'
      entry = self._entry_finder.pop(task)
      entry[-1] = self._REMOVED

  def pop_task(self) -> Any:
      'Remove and return the lowest priority task. Raise KeyError if empty.'
      while self._pq:
          priority, count, task = heapq.heappop(self._pq)
          if task is not self._REMOVED:
              del self._entry_finder[task]
              return task
      raise KeyError('pop from an empty priority queue')

class PCCMLabel(object):
  """Class defining a label for the labeling algorithm of
  Froger (2018) for the fixed-route vehicle charging problem.
  """

  def __init__ (self, node_id_for_label: int, key_time: float, trip_time: float, 
    last_visited_cs: int, soc_arr_to_last_cs: float, energy_consumed_since_last_cs: float, 
    supporting_pts:List[List[float]], slope: List[float], time_last_arc: float,
    energy_last_arc: float, parent: PCCMLabel, y_intercept: List[float]=None
  ):
    self.node_id_for_label = node_id_for_label
    self.key_time = key_time
    self.trip_time = trip_time
    self.last_visited_cs = last_visited_cs
    self.soc_arr_to_last_cs = soc_arr_to_last_cs
    self.energy_consumed_since_last_cs = energy_consumed_since_last_cs
    self.supporting_pts = supporting_pts
    self.slope = slope
    self.time_last_arc = time_last_arc
    self.energy_last_arc = energy_last_arc
    self.parent = parent
    self.y_intercept = self._compute_y_intercept() if y_intercept is None else y_intercept

  def _compute_y_intercept(self) -> List[float]:
    if self.slope is None:
      return None
    else:
      return [(self.supporting_pts[1][b]-self.slope[b]*self.supporting_pts[0][b])
        for b in range(len(self.slope))]

  def dominates(self, other: PCCMLabel) -> bool:
    # drive time dominance
    if self.trip_time > other.trip_time:
      return False
    
    n_pts = len(self.supporting_pts[0])
    n_pts_other = len(other.supporting_pts[0])
    
    # energy dominance (larger reachable SOC)
    if self.supporting_pts[1][-1] < other.supporting_pts[1][-1]:
      return False
    
    # SOC dominance
    # 1) supp pts of this SOC function
    for k in range(n_pts):
      soc_other = other.getSOCDichotomic(self.supporting_pts[0][k])
      if self.supporting_pts[1][k] < soc_other:
        return False

    # 2) supp pts of the other SOC function
    for k in range(n_pts_other):
      soc = self.get_soc_dichotomic(other.supporting_pts[0][k])
      if soc < other.supporting_pts[1][k]:
        return False

    return True

  def get_soc_dichotomic(self, time: float) -> float:
    if time < self.trip_time:
      return -float('inf')
		
    n_pts = len(self.supporting_pts)
    if time >= self.supporting_pts[0][-1]:
      return self.supporting_pts[1][-1]
    
    low = 0
    high = n_pts-1
    while (low + 1 < high):
      mid = (low + high) // 2
      if self.supporting_pts[0][mid] < time:
        low = mid
      else: # self.supporting_pts[0][mid] >= time
        high = mid
    
    return self.slope[low] * time + self.y_intercept[low]

  def get_first_supp_pt_soc(self) -> float:
    return self.supporting_pts[1][0]
  
  def get_last_supp_pt_soc(self) -> float:
    return self.supporting_pts[1][-1]
    
  def get_num_supp_pts(self) -> int:
    """Returns the number of supporting points."""
    return len(self.supporting_pts[0])
  
  def get_path(self) -> List[int]:
    path = []
    curr_parent = self
    stop = False
    while not stop:
      path.append(curr_parent.node_id_for_label)
      curr_parent = curr_parent.parent
      if curr_parent is None:
        stop = True
    return path
  
  def get_path_from_last_customer (self) -> List[int]:
    """Provides a list of the node IDs that the vehicle has 
    visited since the last time it either a) visited a customer,
    b) visited a depot, or c) visited the node at which it
    currently resides.

    I think. Getting closer to the implementation should answer this.
    """
    if self.last_visited_cs is None:
      return []
    
    path = []
    curr_parent = self
    curr_prev_cs = curr_parent.last_visited_cs

    stop = False
    while not stop:
      next_prev_cs = curr_parent.last_visited_cs
      path.append(curr_parent.node_id_for_label)
      curr_parent = curr_parent.parent
      curr_prev_cs = curr_parent.last_visited_cs
      if curr_parent is None or curr_prev_cs is None or curr_prev_cs == next_prev_cs:
        stop = True
    
    return path
  
  def get_charging_amounts(self) -> List[float]:

    if self.last_visited_cs is None:
      return [] # no visits to CS

    # charge amount at last visited CS
    charge_amts = [(self.energy_consumed_since_last_cs + 
      self.get_first_supp_pt_soc - 
      self.soc_arr_to_last_cs)]
      
    # computation of other charge amounts (if any)
    curr_label = self
    while True:
      s_last_vis_cs = curr_label.last_visited_cs

      stop = False
      while not stop:
        charge_reqd = (curr_label.energy_consumed_since_last_cs + 
          curr_label.get_first_supp_pt_soc - 
          curr_label.soc_arr_to_last_cs)
        curr_label = curr_label.parent
        if curr_label.last_visited_cs != s_last_vis_cs:
          stop = True

      if curr_label.last_visited_cs is None:
        break
        
      # compute charging amount
      charge_amts.append(charge_reqd)
    
    return charge_amts

  def __str__(self):
    s = f"---- Label for node {self.node_id_for_label}\n"
    s += (f"keyTime = {self.key_time}\t tripTime = {self.trip_time}\n")
    s += (f"timeLastArc = {self.time_last_arc}\t energyLastArc = {self.energy_last_arc}\n")
    s += (f"lastVisitedCS = {self.last_visited_cs}\t")
    s += (f"socAtArrLastCS = {self.soc_arr_to_last_cs}\n")
    s += (f"energyConsumedSinceLastCS = {self.energy_consumed_since_last_cs}\n")
    s += ("Supporting points \n")
    s += str(self.supporting_pts[0])+"\n"
    s += str(self.supporting_pts[1])+"\n"
    if self.slope is not None:
      s += "Slope\n"
      s += str(self.slope)+"\n"
      s += "Intercept\n"
      s += str(self.y_intercept)+"\n"
    s += "Path\n"
    s += str(self.get_path())
    return s

  # region comparable methods
  def compare_to(self, other: PCCMLabel) -> int:
    if self.key_time < other.key_time:
      return -1
    elif self.key_time > other.key_time:
      return 1
    
    else:
      diff = other.supporting_pts[1][0]-self.supporting_pts[1][0]
      if diff > 0.0:
        return 1
      elif diff < 0.0:
        return -1
      else:
        return 0
  
  def __eq__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) == 0

  def __ne__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) != 0

  def __lt__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) < 0

  def __le__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) <= 0

  def __gt__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) > 0

  def __ge__(self, other: PCCMLabel) -> bool:
    return self.compare_to(other) >= 0

  # endregion

class FRVCPInstance(object):
  #TODO
  def __init__(self, energy_matrix: List[List[float]], 
    time_matrix: List[List[float]], process_times: List[float],
    max_q: float
  ):
    self.energy_matrix = energy_matrix # [i][j] are indices in g, not gprime
    self.time_matrix = time_matrix
    self.process_times = process_times
    self.max_q = max_q
    # more TODO
    return

  def is_cs_faster(self, node1: Node, node2: Node) -> bool:
    # TODO
    # here's the java implementation:
    # private boolean isCSFaster(int csType1, int csType2) {
    #   return mSlope[csType1][0] > mSlope[csType2][0];
    # }

    # public boolean isCSFaster(Node cs1, Node cs2) {
    #   if (!cs1.getType().equals(NodeType.CHARGING_STATION) || !cs2.getType().equals(NodeType.CHARGING_STATION)) {
    #     throw new IllegalArgumentException("Method can only be used with a charging station");
    #   }
    #   int csType1 = mCSTypes[this.getLocalCSID(cs1)];
    #   int csType2 = mCSTypes[this.getLocalCSID(cs2)];
    #   return isCSFaster(csType1, csType2);
    # }
    return
  
  def get_supporting_points(self, node: Node) -> List[List[float]]:
    # TODO note that we are accessing it by node
    return

  def get_slope(self, node: Node=None, soc: float=None):
    # TODO again, note that we are accessing it by node
    
    # if no node passed:
    #  if soc passed, throw a warning message that if passing SOC, Node must also be passed. no node passed, so ignoring soc
    #  just return the array of slopes for CSs' charging functions
    
    # if node passed, but no soc:
    #  return the slopes of the node's charging function

    # the code from the java implementation:
    # public double getSlope(Node node, double soc) {
    #   int segment = getSegment(node, soc);
    #   int localCSID = mMapNodeCStoLocalID.get(node);
    #   int typeCS = mCSTypes[localCSID];
    #   return mSlope[typeCS][segment];

    # }

    # public int getSegment(Node node, double soc) {
    #   if (!node.getType().equals(NodeType.CHARGING_STATION)) {
    #     throw new IllegalArgumentException("Method can only be used with a charging station");
    #   }
    #   int localCSID = mMapNodeCStoLocalID.get(node);
    #   int typeCS = mCSTypes[localCSID];
    #   int nbPoints = mNbBreakPoints[typeCS];
    #   int k = 0;
    #   while (k < nbPoints && mPiecewisePoints[typeCS][k][1] <= soc) {
    #     k++;
    #   }
    #   if (k == 0) {
    #     throw new IllegalStateException(mPiecewisePoints[typeCS][k][1] + " vs " + soc);
    #   }
    #   return k - 1;

    # }
    return

  def get_time(self, node: Node=None, soc: float=None):
    # TODO again, note that we are accessing it by node
    
    # if no node passed:
    #  if soc passed, throw a warning message that if passing SOC, Node must also be passed. no node passed, so ignoring soc
    #  just return the array of slopes for CSs' charging functions
    
    # if node passed, but no soc:
    #  return the slopes of the node's charging function

    # the code from the java implementation:
    # private double getTime(int typeCS, double energy, int nbDecimals) {
    #   int b = 0;
    #   while (b < (mNbBreakPoints[typeCS] - 1) && mPiecewisePoints[typeCS][b + 1][1] < energy) {
    #     b++;
    #   }
    #   if (b == (mNbBreakPoints[typeCS] - 1)) {
    #     throw new IllegalStateException("Unknown breakpoint -> " + energy + " vs "
    #         + mPiecewisePoints[typeCS][mNbBreakPoints[typeCS] - 1][1]);
    #   }
    #   return (energy - mYIntercept[typeCS][b]) / mSlope[typeCS][b];
    # }
    return