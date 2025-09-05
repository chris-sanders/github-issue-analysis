"""
Summary retrieval client for Snowflake Cortex operations.
Provides hybrid product+symptom retrieval for case summaries from exp05.
"""

from .snowflake_dev_client import SnowflakeDevClient


class SummaryRetrievalClient:
    """Client for retrieving case summaries using vector similarity search."""

    def __init__(self):
        """Initialize the summary retrieval client."""
        self.client = SnowflakeDevClient(schema="EXP05")

    def search_by_product(
        self, product_text: str, limit: int = 5, threshold: float = 0.7
    ) -> list[dict]:
        """
        Vector similarity search using PRODUCT_EMBEDDING.

        Args:
            product_text: Product text to search for
            limit: Maximum number of results
            threshold: Minimum similarity score

        Returns:
            List of matching cases with product_similarity
        """
        try:
            search_sql = """
            WITH query_embedding AS (
                SELECT
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                        'snowflake-arctic-embed-m',
                        %s
                    ) as query_emb
            )
            SELECT
                s.*,
                VECTOR_COSINE_SIMILARITY(s.PRODUCT_EMBEDDING, q.query_emb) as product_similarity
            FROM DEV_CRE.EXP05.SUMMARIES s, query_embedding q
            WHERE s.PRODUCT_EMBEDDING IS NOT NULL
              AND VECTOR_COSINE_SIMILARITY(s.PRODUCT_EMBEDDING, q.query_emb) >= %s
            ORDER BY product_similarity DESC
            LIMIT %s
            """

            # Use the client's _get_connection method with parameterized query
            with self.client._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(search_sql, (product_text, threshold, limit))
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Product search failed: {e}")
            return []

    def search_by_symptoms(
        self, symptoms_text: str, limit: int = 5, threshold: float = 0.7
    ) -> list[dict]:
        """
        Vector similarity search using SYMPTOMS_EMBEDDING.

        Args:
            symptoms_text: Symptoms text to search for
            limit: Maximum number of results
            threshold: Minimum similarity score

        Returns:
            List of similar cases with symptom_similarity
        """
        try:
            search_sql = """
            WITH query_embedding AS (
                SELECT
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                        'snowflake-arctic-embed-m',
                        %s
                    ) as query_emb
            )
            SELECT
                s.*,
                VECTOR_COSINE_SIMILARITY(s.SYMPTOMS_EMBEDDING, q.query_emb) as symptom_similarity
            FROM DEV_CRE.EXP05.SUMMARIES s, query_embedding q
            WHERE s.SYMPTOMS_EMBEDDING IS NOT NULL
              AND VECTOR_COSINE_SIMILARITY(s.SYMPTOMS_EMBEDDING, q.query_emb) >= %s
            ORDER BY symptom_similarity DESC
            LIMIT %s
            """

            # Use the client's _get_connection method with parameterized query
            with self.client._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(search_sql, (symptoms_text, threshold, limit))
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Symptom vector search failed: {e}")
            return []

    def search_by_evidence(
        self, evidence_text: str, limit: int = 5, threshold: float = 0.7
    ) -> list[dict]:
        """
        Vector similarity search using EVIDENCE_EMBEDDING.

        Args:
            evidence_text: Evidence text to search for
            limit: Maximum number of results
            threshold: Minimum similarity score

        Returns:
            List of similar cases with evidence_similarity
        """
        try:
            search_sql = """
            WITH query_embedding AS (
                SELECT
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
                        'snowflake-arctic-embed-m',
                        %s
                    ) as query_emb
            )
            SELECT
                s.*,
                VECTOR_COSINE_SIMILARITY(s.EVIDENCE_EMBEDDING, q.query_emb) as evidence_similarity
            FROM DEV_CRE.EXP05.SUMMARIES s, query_embedding q
            WHERE s.EVIDENCE_EMBEDDING IS NOT NULL
              AND VECTOR_COSINE_SIMILARITY(s.EVIDENCE_EMBEDDING, q.query_emb) >= %s
            ORDER BY evidence_similarity DESC
            LIMIT %s
            """

            # Use the client's _get_connection method with parameterized query
            with self.client._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(search_sql, (evidence_text, threshold, limit))
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Evidence vector search failed: {e}")
            return []

    def retrieve_similar_cases(
        self,
        product: list[str],
        symptoms: list[str],
        limit: int = 2,
        threshold: float = 0.7,
        product_weight: float = 0.4,
        symptom_weight: float = 0.6,
    ) -> list[dict]:
        """
        Combine product and symptom searches with weighted scoring.

        Args:
            product: List of product terms
            symptoms: List of symptom terms
            limit: Maximum number of results to return
            threshold: Minimum combined similarity score
            product_weight: Weight for product match (default 0.4)
            symptom_weight: Weight for symptom similarity (default 0.6)

        Returns:
            List of most relevant cases with combined_score
        """
        try:
            # Prepare search texts
            product_text = " ".join(product) if product else ""
            symptoms_text = " ".join(symptoms) if symptoms else ""

            if not product_text and not symptoms_text:
                print("⚠️ No product or symptom text provided for search")
                return []

            # Perform combined search using both product and symptom vector similarity
            combined_sql = """
            WITH
            embeddings AS (
                SELECT
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', %s) as product_query_emb,
                    SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', %s) as symptoms_query_emb
            ),
            combined_results AS (
                SELECT
                    s.*,
                    -- Vector similarities
                    CASE
                        WHEN s.PRODUCT_EMBEDDING IS NULL THEN 0.0
                        ELSE VECTOR_COSINE_SIMILARITY(s.PRODUCT_EMBEDDING, e.product_query_emb)
                    END as product_similarity,
                    CASE
                        WHEN s.SYMPTOMS_EMBEDDING IS NULL THEN 0.0
                        ELSE VECTOR_COSINE_SIMILARITY(s.SYMPTOMS_EMBEDDING, e.symptoms_query_emb)
                    END as symptom_similarity,
                    -- Weighted combination
                    (CASE
                        WHEN s.PRODUCT_EMBEDDING IS NULL THEN 0.0
                        ELSE VECTOR_COSINE_SIMILARITY(s.PRODUCT_EMBEDDING, e.product_query_emb)
                    END * %s) +
                    (CASE
                        WHEN s.SYMPTOMS_EMBEDDING IS NULL THEN 0.0
                        ELSE VECTOR_COSINE_SIMILARITY(s.SYMPTOMS_EMBEDDING, e.symptoms_query_emb)
                    END * %s) as combined_score
                FROM DEV_CRE.EXP05.SUMMARIES s, embeddings e
            )
            SELECT *
            FROM combined_results
            WHERE combined_score >= %s
            ORDER BY combined_score DESC
            LIMIT %s
            """

            # Use the client's _get_connection method with parameterized query
            with self.client._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    combined_sql,
                    (
                        product_text,
                        symptoms_text,
                        product_weight,
                        symptom_weight,
                        threshold,
                        limit,
                    ),
                )
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                cases = [dict(zip(columns, row)) for row in results]

            print(f"🔍 Found {len(cases)} similar cases (threshold: {threshold})")
            for case in cases:
                issue_key = f"{case['REPO_NAME']}-{case['ISSUE_NUMBER']}"
                score = case.get("COMBINED_SCORE", 0)
                print(f"   - {issue_key}: {score:.3f}")

            return cases

        except Exception as e:
            print(f"❌ Combined search failed: {e}")
            return []

    def format_memory_context(self, cases: list[dict]) -> str:
        """
        Format retrieved cases for prompt injection using XML.

        Args:
            cases: List of similar case dictionaries

        Returns:
            Formatted XML string for prompt injection
        """
        if not cases:
            return ""

        context_lines = ["<relevant_past_cases>"]

        for i, case in enumerate(cases, 1):
            # Create case header
            issue_key = f"{case['ORG_NAME']}/{case['REPO_NAME']}#{case['ISSUE_NUMBER']}"
            similarity = case.get("COMBINED_SCORE", case.get("symptom_similarity", 0))

            context_lines.append(
                f'<case id="{i}" issue="{issue_key}" similarity="{similarity:.2f}">'
            )

            # Add structured fields - handle both arrays and string representations
            def parse_array_field(field_value):
                """Parse array field that might be returned as string from Snowflake."""
                if isinstance(field_value, str):
                    # Try to parse as JSON array if it looks like one
                    if field_value.strip().startswith(
                        "["
                    ) and field_value.strip().endswith("]"):
                        import json

                        try:
                            return json.loads(field_value)
                        except json.JSONDecodeError:
                            return [field_value]  # Return as single item if can't parse
                    else:
                        return [field_value]  # Single string item
                elif isinstance(field_value, list):
                    return field_value
                else:
                    return []

            product = parse_array_field(case.get("PRODUCT", []))
            if product and any(p for p in product):
                product_str = ", ".join(str(p) for p in product if p and str(p).strip())
                context_lines.append(f"<product>{product_str}</product>")

            symptoms = parse_array_field(case.get("SYMPTOMS", []))
            if symptoms and any(s for s in symptoms):
                context_lines.append("<symptoms>")
                for symptom in symptoms:
                    if symptom and str(symptom).strip():
                        context_lines.append(f"<symptom>{symptom}</symptom>")
                context_lines.append("</symptoms>")

            evidence = parse_array_field(case.get("EVIDENCE", []))
            if evidence and any(e for e in evidence):
                context_lines.append("<evidence>")
                for item in evidence[:3]:  # Limit to top 3 evidence items
                    if item and str(item).strip():
                        context_lines.append(f"<item>{item}</item>")
                context_lines.append("</evidence>")

            cause = case.get("CAUSE", "")
            if cause and str(cause).strip():
                context_lines.append(f"<root_cause>{cause}</root_cause>")

            fix_items = parse_array_field(case.get("FIX", []))
            if fix_items and any(f for f in fix_items):
                context_lines.append("<fix_applied>")
                for fix_item in fix_items[:2]:  # Limit to top 2 fix items
                    if fix_item and str(fix_item).strip():
                        context_lines.append(f"<action>{fix_item}</action>")
                context_lines.append("</fix_applied>")

            context_lines.append("</case>")

        context_lines.append("</relevant_past_cases>")

        return "\n".join(context_lines)
