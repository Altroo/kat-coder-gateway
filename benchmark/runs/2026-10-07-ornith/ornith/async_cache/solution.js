'use strict';

function createAsyncCache(load, ttlMs, now = Date.now) {
  const cache = new Map();
  const inflight = new Map();

  function get(key) {
    const nowMs = now();
    const entry = cache.get(key);
    if (entry !== undefined && entry.expiresAt > nowMs) {
      return Promise.resolve(entry.value);
    }
    if (entry !== undefined) {
      cache.delete(key);
    }

    const pending = inflight.get(key);
    if (pending !== undefined) {
      return pending.promise;
    }

    let resolveFn;
    let rejectFn;
    const promise = new Promise((resolve, reject) => {
      resolveFn = resolve;
      rejectFn = reject;
    });

    const record = {
      promise,
      resolve: resolveFn,
      reject: rejectFn,
      active: true,
      expiresAt: 0,
    };
    inflight.set(key, record);

    let settled = false;
    let result;
    let isError = false;

    function finalize(value) {
      if (!record.active) {
        return;
      }
      settled = true;
      result = value;
      isError = false;
      inflight.delete(key);
      cache.set(key, { value: value, expiresAt: now() + ttlMs });
      record.active = false;
      resolveFn(value);
    }

    function fail(err) {
      if (!record.active) {
        return;
      }
      settled = true;
      result = err;
      isError = true;
      inflight.delete(key);
      cache.delete(key);
      record.active = false;
      rejectFn(err);
    }

    function settle() {
      try {
        const maybe = load(key);
        if (maybe instanceof Promise) {
          maybe.then(
            (v) => {
              if (settled) return;
              finalize(v);
            },
            (e) => {
              if (settled) return;
              fail(e);
            }
          );
        } else {
          finalize(maybe);
        }
      } catch (e) {
        fail(e);
      }
    }

    settle();

    return promise;
  }

  function invalidate(key) {
    cache.delete(key);
    const pending = inflight.get(key);
    if (pending !== undefined) {
      pending.active = false;
      inflight.delete(key);
    }
  }

  return { get: get, invalidate: invalidate };
}

module.exports = { createAsyncCache };
