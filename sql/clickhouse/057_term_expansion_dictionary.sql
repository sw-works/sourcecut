CREATE DICTIONARY IF NOT EXISTS term_expansion_dict
(
    category String,
    term String,
    expansions Array(String)
)
PRIMARY KEY category, term
SOURCE(CLICKHOUSE(QUERY 'SELECT category, term, expansions FROM sourcecut.term_expansions FINAL'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);
