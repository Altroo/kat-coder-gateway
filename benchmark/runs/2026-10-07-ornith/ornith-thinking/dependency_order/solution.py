import heapq


def order_tasks(tasks):
    result = []
    if not tasks:
        return result

    index_of = {}
    for i, task in enumerate(tasks):
        tid = task["id"]
        if tid in index_of:
            raise ValueError("Duplicate task id: %r" % tid)
        index_of[tid] = i

    known = set(index_of)
    in_degree = {tid: 0 for tid in index_of}
    dependents = {tid: [] for tid in index_of}

    for task in tasks:
        tid = task["id"]
        seen = set()
        for dep in task.get("depends_on", ()):
            if dep == tid:
                raise ValueError("Task cannot depend on itself: %r" % tid)
            if dep not in known:
                raise ValueError("Unknown dependency: %r" % dep)
            if dep in seen:
                continue
            seen.add(dep)
            dependents[dep].append(tid)
            in_degree[tid] += 1

    heap = [(index_of[tid], tid) for tid in index_of if in_degree[tid] == 0]
    heapq.heapify(heap)

    while heap:
        _, tid = heapq.heappop(heap)
        result.append(tid)
        for dependent in dependents[tid]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(heap, (index_of[dependent], dependent))

    if len(result) != len(tasks):
        raise ValueError("Cycle detected in task dependencies")

    return result
