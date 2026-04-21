You are evaluating the chunking pipeline in ctx (the tool at this repo) for use
in AI coding agent retrieval. You have access to the repo and can read files
and run commands — use this. Your job is to decide whether ctx's approach is
well-suited for AI coding agents, or whether it should change — and to back
each claim with evidence from the code and the chunks it actually produces.

## What ctx does today

- Three chunking strategies (`src/ctx/chunker/`):
  - `heading` (default) — splits markdown at H2 boundaries; subsections stay
    with their parent; splits further if a section exceeds `max_tokens` (500
    default) with `overlap_tokens` of carryover (50 default)
  - `fixed` — sliding token window, 500 tokens with 50 overlap
  - `definition` — one chunk per term (detects H3/H4 headings or `**Bold**:`
    patterns), intended for glossaries and API references
- Token counting via `tiktoken` with `cl100k_base`
- Deterministic hierarchical chunk IDs: `{module}/{file-stem}/{section-slug}`
- Each chunk carries: id, module, source_file, section_path, content,
  metadata (tags, version, token_count, optional source_hash)
- Output is JSONL; consumer supplies the embedding model and vector store
- ctx is designed for two targets: RAG pipelines and Claude Code / Cursor /
  Copilot skills-and-rules installation — both feed AI coding agents

## What to evaluate

For each of the three chunkers and for the pipeline as a whole:

1. **Semantic coherence.** When an AI coding agent retrieves a chunk, is the
   chunk self-contained enough to be useful, or does it require neighboring
   context to make sense? Run `ctx chunks tests/fixtures/sample-module -f jsonl`
   and also pack a realistic doc from the repo itself (e.g. `ctx pack ./docs`
   or point at `SPEC.md` / `CLAUDE.md`). Pick 3–5 chunks and assess each.

2. **Retrieval behavior under realistic queries.** For an agent question like
   "how do I authenticate against the API?", would the retrieved chunk(s)
   actually land on the right passage? Where does heading-based splitting
   help vs. hurt? Where does definition chunking shine or fail?

3. **Coding-agent-specific concerns.** Code-heavy documents have different
   needs than prose. Does heading-based chunking preserve code blocks and
   their surrounding explanation? What happens to long code listings vs.
   `max_tokens`? Any risk of splitting mid-block? Test this by chunking a
   real code-heavy doc from the repo.

4. **Context window economy.** Are 500-token chunks the right default for
   today's agents (Claude Sonnet/Opus, GPT-4, Gemini 2.x), given context
   budgets of 200K–1M tokens but retrieval budgets that are often smaller?
   Should defaults differ by strategy or content type?

5. **Metadata sufficiency.** Does the metadata ctx attaches give a retriever
   enough to reorder, dedupe, or filter results? What's missing that a coding
   agent would actually use (e.g., language, symbols defined, imports, file
   path depth)?

6. **Determinism and incremental updates.** The hierarchical, content-derived
   IDs are designed to enable incremental re-indexing. Does the design hold
   up when a document is edited mid-section? When headings are renamed?

7. **Alternatives worth comparing.** LLM-at-chunk-time approaches are fully
   on the table — evaluate their cost/latency/quality tradeoffs on their
   merits, not as a last resort.
   - **Anthropic's Contextual Retrieval** (prepending LLM-generated context
     to each chunk before embedding)
   - **Late chunking** (embed the whole document, then chunk embeddings)
   - **Semantic / agentic chunking** (LLM decides boundaries by topic shift)
   - **AST-aware chunking** for code (split at function/class boundaries)
   - **Hierarchical / multi-granularity chunking** (parent doc + child chunks,
     retrieve children but return parent)
   For each, state whether you'd recommend ctx adopt it, reject it, or offer
   it as an alternative strategy. Justify briefly, including the cost to ctx's
   "deterministic, dependency-light" design ethos.

## Deliverable format

Structure your response as:

1. **Verdict in one sentence.** Is ctx's current chunking fit-for-purpose for
   AI coding agent retrieval — yes, no, or "yes for X, no for Y"?
2. **Evidence.** For each claim, cite a specific chunk, file path, or code
   reference from the repo. Don't generalize without evidence.
3. **Top 3 concrete changes** you'd make to the ctx code to improve it,
   ranked by impact. For each: what to change (file + function), why,
   and the expected effect. If any of the top 3 involve LLM-at-chunk-time,
   include a rough cost/latency estimate.
4. **Out of scope.** Name one or two ideas that sound appealing but
   aren't worth the complexity for this tool's scale (personal use, single
   maintainer, deterministic-output design).

## Constraints on your evaluation

- Don't recommend "more tests" or "more configuration" as an answer — focus
  on the chunking logic itself.
- Be specific. "Consider semantic chunking" is not useful; "replace
  HeadingChunker's fallback sliding window with a sentence-boundary-aware
  splitter because chunks currently cut mid-sentence at token N" is useful.
- Ground recommendations in how AI coding agents actually consume retrieved
  context — as system/user message text with a retrieval budget, not as
  fine-tuning data.
