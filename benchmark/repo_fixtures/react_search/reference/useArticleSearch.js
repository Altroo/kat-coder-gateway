const { useEffect, useState } = require('react');

const useArticleSearch = (query, search) => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const text = query.trim();
    setResults([]);
    setError(null);
    setLoading(Boolean(text));
    if (text) {
      Promise.resolve().then(() => {
        if (active) return search(text, { signal: controller.signal });
      }).then(value => {
        if (active) setResults(value);
      }).catch(err => {
        if (active) setError(err);
      }).finally(() => {
        if (active) setLoading(false);
      });
    }
    return () => { active = false; controller.abort(); };
  }, [query, search]);
  return { results, loading, error };
};
module.exports = { useArticleSearch };
