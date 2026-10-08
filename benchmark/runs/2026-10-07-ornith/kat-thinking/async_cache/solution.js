function createAsyncCache(load, ttlMs, now = Date.now) {
  const cache = new Map();
  const pending = new Map();
  let versionCounter = 0;

  return {
    get(key) {
      const entry = cache.get(key);
      if (entry && now() < entry.expiresAt) {
        return Promise.resolve(entry.value);
      }

      const pendingEntry = pending.get(key);
      if (pendingEntry) {
        return pendingEntry.promise;
      }

      const version = ++versionCounter;

      const promise = new Promise(function (resolve, reject) {
        try {
          const result = load(key);
          if (result != null && typeof result.then === 'function') {
            result.then(resolve).catch(reject);
          } else {
            resolve(result);
          }
        } catch (err) {
          reject(err);
        }
      }).then(function (value) {
        const current = pending.get(key);
        if (current && current.version === version) {
          cache.set(key, { value: value, expiresAt: now() + ttlMs });
        }
        pending.delete(key);
        return value;
      }).catch(function (err) {
        const current = pending.get(key);
        if (current && current.version === version) {
          pending.delete(key);
        }
        throw err;
      });

      pending.set(key, { promise: promise, version: version });
      return promise;
    },
    invalidate(key) {
      cache.delete(key);
      pending.delete(key);
    }
  };
}

module.exports = { createAsyncCache: createAsyncCache };
