const { useEffect, useState } = require('react');

const useArticleSearch = (query, search) => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    setLoading(true);
    search(query)
      .then(setResults)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [query]);
  return { results, loading, error };
};
module.exports = { useArticleSearch };
