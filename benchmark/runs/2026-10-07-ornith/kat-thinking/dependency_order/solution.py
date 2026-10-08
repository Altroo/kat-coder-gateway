def order_tasks(tasks):
    if not tasks:
        return []

    n = len(tasks)
    id_to_idx = {}
    adj = [[] for _ in range(n)]
    in_degree = [0] * n
    dep_list = []

    for i, task in enumerate(tasks):
        tid = task["id"]
        if tid in id_to_idx:
            raise ValueError("duplicate task id")
        id_to_idx[tid] = i
        deps = task.get("depends_on", [])
        seen_deps = set()
        for d in deps:
            if d == tid:
                raise ValueError("self dependency")
            if d not in id_to_idx:
                raise ValueError("unknown dependency")
            if d in seen_deps:
                continue
            seen_deps.add(d)
            j = id_to_idx[d]
            adj[j].append(i)
            in_degree[i] += 1
        dep_list.append(seen_deps)

    ready = set()
    for i in range(n):
        if in_degree[i] == 0:
            ready.add(i)

    result = []
    for _ in range(n):
        if not ready:
            raise ValueError("cycle detected")
        best = min(ready)
        ready.remove(best)
        result.append(tasks[best]["id"])
        for nxt in adj[best]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.add(nxt)

    return result
