def order_tasks(tasks):
    """
    Return task ids in dependency-first topological order.
    At every step, choose the ready task that appeared earliest in the original input.
    """
    if not tasks:
        return []
    
    # Build mapping from id to task, checking for duplicates and self-dependencies
    id_to_task = {}
    id_order = []  # preserve original order
    seen_ids = set()
    
    for task in tasks:
        tid = task["id"]
        if tid in seen_ids:
            raise ValueError(f"Duplicate task id: {tid}")
        seen_ids.add(tid)
        id_to_task[tid] = task
        id_order.append(tid)
    
    # Build adjacency and in-degree
    # depends_on: list of ids this task depends on
    # We need to track for each task, how many dependencies it has (in-degree)
    # And for each task, which tasks depend on it (successors)
    
    in_degree = {tid: 0 for tid in id_order}
    successors = {tid: set() for tid in id_order}
    
    for tid in id_order:
        task = id_to_task[tid]
        deps = task.get("depends_on", [])
        # Deduplicate dependencies
        seen_deps = set()
        for dep in deps:
            if dep == tid:
                raise ValueError(f"Self dependency: {tid}")
            if dep not in id_to_task:
                raise ValueError(f"Unknown dependency: {dep}")
            if dep in seen_deps:
                continue
            seen_deps.add(dep)
            in_degree[tid] += 1
            successors[dep].add(tid)
    
    # Kahn's algorithm with priority: choose the ready task that appeared earliest
    # We need a queue of ready tasks (in-degree 0), and at each step pick the one
    # with the smallest original index.
    
    # Use a min-heap based on original index for ready tasks
    import heapq
    
    # Initialize: all tasks with in-degree 0
    ready = []
    for idx, tid in enumerate(id_order):
        if in_degree[tid] == 0:
            heapq.heappush(ready, (idx, tid))
    
    result = []
    while ready:
        idx, tid = heapq.heappop(ready)
        result.append(tid)
        for succ in successors[tid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                # Find the original index of succ
                heapq.heappush(ready, (id_order.index(succ), succ))
    
    if len(result) != len(id_order):
        raise ValueError("Cycle detected")
    
    return result
