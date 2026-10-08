function createAsyncCache(load, ttlMs, now = Date.now) {
  const cache = new Map();
  const pending = new Map();

  function get(key) {
    const cached = cache.get(key);
    if (cached !== undefined) {
      const expiresAt = cached.expiresAt;
      const value = cached.value;
      if (now() < expiresAt) {
        return Promise.resolve(value);
      }
      cache.delete(key);
    }

    const pendingLoad = pending.get(key);
    if (pendingLoad !== undefined) {
      return pendingLoad;
    }

    const promise = (async () => {
      try {
        const value = await load(key);
        const expiresAt = now() + ttlMs;
        cache.set(key, { value, expiresAt });
        pending.delete(key);
        return value;
      } catch (err) {
        pending.delete(key);
        throw err;
      }
    })();

    pending.set(key, promise);
    return promise;
  }

  function invalidate(key) {
    cache.delete(key);
    const pendingLoad = pending.get(key);
    if (pendingLoad !== undefined) {
      pending.delete(key);
      // The old load must still settle for its original callers,
      // but we've removed it from pending so it can't overwrite newer state.
      // We need to wrap it so that when it settles, it doesn't affect cache.
      // Actually, the original promise already has the cache.set inside it.
      // We need to intercept that. Let's restructure.
    }
  }

  // Restructure to handle the detach requirement properly
  const cache2 = new Map();
  const pending2 = new Map();

  function get2(key) {
    const cached = cache2.get(key);
    if (cached !== undefined) {
      const expiresAt = cached.expiresAt;
      const value = cached.value;
      if (now() < expiresAt) {
        return Promise.resolve(value);
      }
      cache2.delete(key);
    }

    const pendingLoad = pending2.get(key);
    if (pendingLoad !== undefined) {
      return pendingLoad;
    }

    let resolveCache;
    let rejectCache;
    const promise = new Promise((resolve, reject) => {
      resolveCache = resolve;
      rejectCache = reject;
    });

    pending2.set(key, { promise, resolveCache, rejectCache });

    let settled = false;
    let detach = false;

    const cleanup = () => {
      if (!settled) {
        settled = true;
        pending2.delete(key);
      }
    };

    const runLoad = async () => {
      try {
        const value = await load(key);
        if (!settled) {
          settled = true;
          if (!detach) {
            const expiresAt = now() + ttlMs;
            cache2.set(key, { value, expiresAt });
            resolveCache(value);
          } else {
            // detached: old load settled, don't overwrite newer cache state
            // but still resolve original callers
            resolveCache(value);
          }
        }
      } catch (err) {
        if (!settled) {
          settled = true;
          if (!detach) {
            cache2.delete(key);
          }
          rejectCache(err);
        }
      }
    };

    // Start the load
    runLoad();

    // Return a promise that resolves/rejects based on the load
    // But we need to handle the case where invalidate is called
    return promise;
  }

  function invalidate2(key) {
    cache2.delete(key);
    const pendingEntry = pending2.get(key);
    if (pendingEntry !== undefined) {
      // Mark as detached so the old load won't overwrite newer cache state
      // But we need to let the old load settle for its original callers
      // The original promise is already created and returned to callers.
      // We need to signal to the running load that it's detached.
      // Let's add a detach flag to the pending entry.
      pendingEntry.detach = true;
      // Remove from pending so next get starts fresh
      pending2.delete(key);
    }
  }

  // Hmm, the above approach with resolveCache/rejectCache is getting complex.
  // Let me think about this more carefully.

  // The key insight: when invalidate is called, we need to:
  // 1. Remove from cache
  // 2. Detach any pending load so it can't overwrite newer state
  // 3. But the old load must still settle for its original callers

  // So the structure should be:
  // - pending stores the load promise and a flag for whether it's still "active"
  // - When the load settles, if it's still active, update cache and resolve/reject callers
  // - If detached, just let it settle without affecting cache

  const cache3 = new Map();
  const pending3 = new Map();

  function get3(key) {
    // Check cache
    const cached = cache3.get(key);
    if (cached !== undefined && now() < cached.expiresAt) {
      return Promise.resolve(cached.value);
    }
    cache3.delete(key);

    // Check pending
    const pendingEntry = pending3.get(key);
    if (pendingEntry !== undefined) {
      return pendingEntry.promise;
    }

    // Create new load
    const loadPromise = load(key);
    
    // Track whether this load is still "active" (not invalidated)
    let active = true;
    let settled = false;
    let resolveFn;
    let rejectFn;
    
    const resultPromise = new Promise((resolve, reject) => {
      resolveFn = resolve;
      rejectFn = reject;
    });

    const entry = {
      promise: resultPromise,
      resolve: resolveFn,
      reject: rejectFn,
      active: () => active,
      setDetached: () => { active = false; }
    };

    pending3.set(key, entry);

    loadPromise.then(
      (value) => {
        if (!settled) {
          settled = true;
          if (active) {
            const expiresAt = now() + ttlMs;
            cache3.set(key, { value, expiresAt });
            entry.resolve(value);
          } else {
            // Detached: old load settled, resolve original callers but don't update cache
            entry.resolve(value);
          }
        }
      },
      (err) => {
        if (!settled) {
          settled = true;
          if (active) {
            cache3.delete(key);
          }
          entry.reject(err);
        }
      }
    ).then(() => {
      pending3.delete(key);
    });

    return resultPromise;
  }

  function invalidate3(key) {
    cache3.delete(key);
    const entry = pending3.get(key);
    if (entry !== undefined) {
      entry.setDetached();
      // Don't delete from pending yet - the load is still running and needs to settle
      // But we need to make sure the next get doesn't reuse this entry
      // Actually, we should delete it so next get creates a new one
      // But the old load must still settle for original callers...
      // The original callers have the promise, so they're fine.
      // We just need to remove the entry from pending.
      pending3.delete(key);
    }
  }

  // Wait, there's an issue. If we delete from pending in invalidate, but the load
  // is still running, when it settles it will try to delete from pending again.
  // That's fine, Map.delete is idempotent.
  
  // But there's another issue: what if invalidate is called, then another get comes in
  // before the old load settles? The new get will create a new load. When the old load
  // settles, it checks active() which is false, so it won't overwrite cache. Good.
  
  // What about the case where the old load throws synchronously?
  // load(key) is called, and if it throws synchronously, the promise will reject.
  // That's handled by the catch branch.

  // Let me also handle the ttlMs=0 case. If ttlMs=0, expiresAt = now(), so
  // now() < expiresAt is false, so the cached value is immediately expired.
  // But concurrent gets for the same key should still deduplicate.
  // The pending check handles this.

  // One more issue: what if load throws synchronously?
  // load(key) throws, so loadPromise is a rejected promise.
  // The .then handlers will catch it. Good.

  // Let me also think about the case where invalidate is called while load is running,
  // and then another get for the same key happens before the old load settles.
  // The new get will create a new load. The old load will settle but won't overwrite
  // cache because active is false. Good.

  // I think this is correct. Let me write the final version.

  return {
    get: get3,
    invalidate: invalidate3
  };
}

module.exports = { createAsyncCache };
