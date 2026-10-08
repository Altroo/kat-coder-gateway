function createAsyncCache(load, ttlMs, now = Date.now) {
  const cache = new Map();
  
  function get(key) {
    const entry = cache.get(key);
    if (entry) {
      if (entry.type === 'cached') {
        if (now() < entry.expiresAt) {
          return Promise.resolve(entry.value);
        } else {
          cache.delete(key);
        }
      } else if (entry.type === 'pending') {
        return entry.promise;
      }
    }
    
    // Need to load
    let resolve, reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    
    const entry = {
      type: 'pending',
      promise,
      resolve,
      reject,
      generation: 0 // or some unique id
    };
    
    cache.set(key, entry);
    
    try {
      const result = load(key);
      if (result && typeof result.then === 'function') {
        result.then(
          (value) => {
            const current = cache.get(key);
            if (current === entry && now() < entry.expiresAt) {
              // Wait, for pending entries, expiresAt doesn't make sense...
            }
          }
        );
      }
    } catch (e) {
      // handle sync throw
    }
  }
}
