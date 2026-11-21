# ShelfLife product brief

## Product

**ShelfLife** is an AI-powered financial research copilot for Indian quick-commerce filings. It helps analysts, founders, and researchers ask natural-language questions about annual reports and IPO prospectuses from:

- Eternal Limited (Zomato and Blinkit)
- Swiggy Limited (including Instamart)
- Zepto

The product condenses a large filing corpus into fast, verifiable answers without replacing the underlying documents.

## User experience

Users sign in with email, ask questions in chat, and receive answers grounded in retrieved filing passages. Inline citations open the source passage and show available company, filing, year, page, or section details.

Example research questions:

1. Compare Blinkit and Swiggy Instamart dark-store expansion and contribution margins.
2. What regulatory and supply-chain risks are disclosed in the latest quick-commerce filings?
3. Break down quick-commerce AOV and take-rate trends across FY24–FY25.
4. How do Eternal, Swiggy, and Zepto describe competition and customer acquisition?
5. What do the filings disclose about order growth, gross order value, and profitability?

## Trust contract

- Never fabricate facts or financial metrics.
- Cite the filing and the most precise available page or section for each factual claim.
- Keep answers within the available source material; say when the corpus does not support a conclusion.
- Show the underlying passage so users can verify the answer.

## Current product scope

- **Corpus:** Indian quick-commerce annual reports and IPO prospectuses in the configured manifest.
- **Retrieval:** Hybrid semantic (`pgvector`) and Postgres full-text search.
- **Generation and embeddings:** Google Gemini.
- **Authentication and persistence:** Supabase Auth and Postgres.
- **Out of scope:** Trading recommendations, stock picks, and unsupported external claims.

## Success criteria

Users can answer research questions more quickly while verifying each material claim against its cited source. Release readiness should be evaluated with real filings, user feedback, citation quality, and operational limits of the selected hosting tiers.
