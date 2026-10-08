def order_tasks(tasks):
    if not tasks:
        return []

    # Build task info without mutating input
    seen_ids = {}
    task_ids = []
    task_deps = {}

    for idx, task in enumerate(tasks):
        tid = task["id"]
        if tid in seen_ids:
            raise ValueError(f"Duplicate task id: {tid}")
        seen_ids[tid] = idx
        task_ids.append(tid)
        deps = task.get("depends_on", [])
        # Deduplicate while preserving order
        seen = set()
        unique_deps = []
        for d in deps:
            if d not in seen:
                seen.add(d)
                unique_deps.append(d)
        task_deps[tid] = unique_deps

    # Validate dependencies
    for tid, deps in task_deps.items():
        for d in deps:
            if d == tid:
                raise ValueError(f"Self dependency: {tid}")
            if d not in seen_ids:
                raise ValueError(f"Unknown dependency: {d}")

    # Build adjacency list and in-degree counts
    # adj[a] = list of tasks that depend on a
    adj = {tid: [] for tid in task_ids}
    in_degree = {tid: 0 for tid in task_ids}

    for tid, deps in task_deps.items():
        for d in deps:
            adj[d].append(tid)
            in_degree[tid] += 1

    # Min-heap by original index to pick earliest-appearing ready task
    import heapq
    heap = []
    for tid in task_ids:
        if in_degree[tid] == 0:
            heapq.heappush(heap, (seen_ids[tid], tid))

    result = []
    while heap:
        _, tid = heapq.heappop(heap)
        result.append(tid)
        for neighbor in adj[tid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                heapq.heappush(heap, (seen_ids[neighbor], neighbor))

    if len(result) != len(task_ids):
        raise ValueError("Cycle detected")

    return result
