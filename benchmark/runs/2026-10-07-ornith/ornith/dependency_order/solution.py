def order_tasks(tasks):
    order = []
    index = {}
    indegree = {}
    dependents = {}
    ids = []
    for t in tasks:
        tid = t["id"]
        if tid in index:
            raise ValueError("Duplicate task id: " + str(tid))
        index[tid] = len(ids)
        indegree[tid] = 0
        dependents[tid] = []
        ids.append(tid)
    for t in tasks:
        tid = t["id"]
        deps = t.get("depends_on") or []
        seen = set()
        for dep in deps:
            if dep == tid:
                raise ValueError("Self dependency: " + str(tid))
            if dep not in index:
                raise ValueError("Unknown dependency: " + str(dep))
            if dep in seen:
                continue
            seen.add(dep)
            indegree[tid] += 1
            dependents[dep].append(tid)
    queue = [tid for tid in ids if indegree[tid] == 0]
    head = 0
    while head < len(queue):
        tid = queue[head]
        head += 1
        order.append(tid)
        for dep in dependents[tid]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                queue.append(dep)
    if len(order) != len(ids):
        raise ValueError("Cycle detected in tasks")
    return order
