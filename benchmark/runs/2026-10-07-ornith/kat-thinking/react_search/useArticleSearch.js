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
      return;
    }

    const controller = new AbortController();
    const signal = controller.signal;

    setLoading(true);
    setError(null);
    setResults([]);

    search(trimmed, { signal })
      .then(results => {
        if (!signal.aborted) {
          setResults(results);
        }
      })
      .catch(err => {
        if (!signal.aborted) {
          setError(err);
        }
      })
      .finally(() => {
        if (!signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [query, search]);

  return { results, loading, error };
};
module.exports = { useArticleSearch };
