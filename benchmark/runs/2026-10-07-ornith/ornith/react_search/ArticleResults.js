const React = require('react');
const { useArticleSearch } = require('./useArticleSearch');

const ArticleResults = ({ query, search }) => {
  const { results, loading, error } = useArticleSearch(query, search);
  if (loading) return React.createElement('p', { role: 'status' }, 'Loading');
  if (error) return React.createElement('p', { role: 'alert' }, error.message);
  return React.createElement('ul', null, results.map(item => React.createElement('li', { key: item.id }, item.title)));
};
module.exports = { ArticleResults };
