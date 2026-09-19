"""Safe Jinja pre-processing and macro mocking for dbt SQL models."""

import re


class JinjaSanitizer:
    """
    Sanitizes raw dbt Jinja expressions into standard SQL so that SQLGlot
    can parse valid Abstract Syntax Trees without requiring `dbt compile`.
    """

    # Regex patterns for standard dbt Jinja expressions
    _COMMENT_PATTERN = re.compile(r"\{#.*?#\}", re.DOTALL)
    _CONFIG_PATTERN = re.compile(r"\{\{\s*config\s*\(.*?\)\s*\}\}", re.DOTALL | re.IGNORECASE)
    _REF_PATTERN = re.compile(r"""\{\{\s*ref\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\}\}""", re.IGNORECASE)
    _SOURCE_PATTERN = re.compile(
        r"""\{\{\s*source\s*\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\)\s*\}\}""",
        re.IGNORECASE,
    )
    # Control block tags (e.g. {% if is_incremental() %} ... {% endif %}, {% set ... %}, {% for ... %})
    _BLOCK_TAG_PATTERN = re.compile(r"\{%.*?%\}", re.DOTALL)
    # Catch-all for remaining generic {{ macro(...) }}
    _GENERIC_MACRO_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\(.*?\)\s*\}\}", re.DOTALL)
    _SIMPLE_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

    @classmethod
    def sanitize(cls, sql: str) -> str:
        """
        Transforms raw dbt SQL containing Jinja into valid SQL identifiers and expressions.
        """
        if not sql:
            return ""

        # 1. Strip Jinja comments {# ... #}
        cleaned = cls._COMMENT_PATTERN.sub("", sql)

        # 2. Strip {{ config(...) }} blocks
        cleaned = cls._CONFIG_PATTERN.sub("", cleaned)

        # 3. Replace {{ ref('model_name') }} with model_name
        cleaned = cls._REF_PATTERN.sub(r"\1", cleaned)

        # 4. Replace {{ source('source_name', 'table_name') }} with source_name__table_name
        cleaned = cls._SOURCE_PATTERN.sub(r"\1__\2", cleaned)

        # 5. Strip block tags ({% ... %}) while preserving internal SQL statements
        cleaned = cls._BLOCK_TAG_PATTERN.sub("", cleaned)

        # 6. Replace remaining macro calls {{ macro(...) }} with an identifier
        cleaned = cls._GENERIC_MACRO_PATTERN.sub(r"\1_macro", cleaned)

        # 7. Replace simple variables {{ var }} with var
        cleaned = cls._SIMPLE_VAR_PATTERN.sub(r"\1", cleaned)

        return cleaned.strip()
