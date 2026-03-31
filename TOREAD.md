Core concepts powering the Archive feature

1. Word Embeddings & Sentence Embeddings

Why it matters here: Every article gets converted to a vector via nomic-embed-text. That vector is what makes "semantic" similarity possible — two articles about the same idea end up close together in space even if they
share no words.

Good starting points: "Word2Vec explained", "Sentence-BERT (SBERT)", "what are embeddings?"

---
2. Cosine Similarity

Why it matters here: The search feature ranks results by how close the query vector is to each article's vector. Cosine similarity is the measure used — it ignores vector magnitude and only cares about direction (angle
between vectors).

Good starting points: "cosine similarity vs euclidean distance", "why cosine for NLP"

---
3. Hierarchical Agglomerative Clustering (HAC)

Why it matters here: tree_builder.py uses scipy linkage to group articles into a tree. HAC starts with every article as its own cluster and merges the closest pair repeatedly until you have one root — you cut the tree
at a chosen depth to get your clusters.

Good starting points: "hierarchical clustering explained", "Ward linkage", "dendrogram"

---
4. k-Nearest Neighbors (k-NN)

Why it matters here: The search fallback and the "k-closest articles" idea are both k-NN over an embedding space. Right now it's brute-force (compare query to every vector). At larger scale you'd need an index.

Good starting points: "k-nearest neighbors intuition", "approximate nearest neighbor search"

---
5. Vector Databases / ANN Indexes

Why it matters here: At 500 articles, brute-force cosine is fine. At 50,000 it becomes slow. Libraries like FAISS, Annoy, or HNSW solve this with approximate nearest neighbor indexes — they trade a tiny bit of accuracy
for huge speed gains.

Good starting points: "FAISS by Meta", "HNSW algorithm", "vector database vs traditional database"

---
6. RAG — Retrieval Augmented Generation

Why it matters here: The search + LLM labeling combo in this project is essentially a mini-RAG pipeline. RAG is the broader pattern: retrieve relevant documents using embeddings, then feed them to an LLM for synthesis.
Understanding RAG will give you ideas for features like "summarize what I've read about X across all time".

Good starting points: "RAG explained", "LangChain RAG tutorial" (just for conceptual overview)

---
7. Graph Data Structures & Tree Traversal

Why it matters here: The Explore tab is literally a tree you traverse. Understanding how trees differ from graphs, and how BFS/DFS traversal works, helps reason about navigation depth, node labeling strategy, and future
features like "related articles" links (which would make it a graph, not a tree).

Good starting points: "tree vs graph data structures", "BFS vs DFS", "trie for prefix search"

---
8. TF-IDF (Term Frequency–Inverse Document Frequency)

Why it matters here: This is the classical alternative to embeddings for search. It's simpler, fully local, no model needed, and still works well for the text-fallback search path. Good to understand the tradeoff:
TF-IDF is fast and interpretable, embeddings capture meaning better.

Good starting points: "TF-IDF intuitive explanation", "BM25" (the improved version used by Elasticsearch)

---
9. RSS & Feed Parsing

Why it matters here: It's the entire data ingestion layer. Understanding feed formats (RSS 2.0 vs Atom), entry deduplication strategies, and feedparser edge cases will help you extend to new source types.

Good starting points: "RSS 2.0 spec", "Atom feed format", "feedparser Python docs"

---
Bonus: if you want to go deeper on future features

┌───────────────────────────────────────────────────────────┬────────────────────────────────────────────────────┐
│                       Feature idea                        │                  Concept to study                  │
├───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ "Suggest related articles"                                │ Graph traversal, edge weights by cosine similarity │
├───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ "What did I read about X last month?"                     │ Temporal filtering + vector search                 │
├───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ "Auto-suggest new RSS feeds"                              │ LLM function calling, web search APIs              │
├───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ "Cluster drift detection" (tree stays accurate over time) │ Online clustering, concept drift                   │
├───────────────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Podcast/YouTube summaries                                 │ Whisper (ASR), transcript chunking                 │
└───────────────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
