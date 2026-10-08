const { useEffect, useState } = require('react');

const useArticleSearch = (query, search) => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    const trimmed = (query ?? '').trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError(null);
      return undefined;
    }
    const controller = new AbortController();
    const signal = controller.signal;
    setLoading(true);
    setError(null);
    setResults([]);
    search(trimmed, { signal })
      .then(setResults)
      .catch(setError)
      .finally(() => {
        if (!signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, search]);
  return { results, loading, error };
};
module.exports = { useArticleSearch };
