# Generative AI, LLMs and RAG Knowledge

## Large language models
A large language model is a neural network, usually a transformer, trained on very large text collections to predict the next token. At inference it generates text by repeatedly choosing the next token given the context. Sampling settings such as temperature and top-p control randomness: a low temperature gives more deterministic output.

## Tokens and context window
Models read and write tokens, which are sub-word units. The context window is the maximum number of tokens the model can handle at once, including the prompt and the generated output. Inputs longer than the window must be truncated, summarised or selectively retrieved.

## Prompt engineering
Prompt engineering designs inputs so that a model gives reliable output. Useful techniques are clear instructions, assigning a role, few-shot examples, chain-of-thought or step-by-step reasoning, specifying a structured output format such as JSON, providing relevant context and iterating with tests. Untrusted user text should be clearly delimited because it may contain prompt injection.

## Hallucination
Hallucination is fluent but false or unsupported output. It can be reduced by grounding answers in retrieved documents, asking the model to cite sources or say it does not know, using a lower temperature, requesting structured output and verifying results automatically or with a second evaluation step.

## Embeddings
An embedding maps text to a dense vector so that texts with similar meaning are close together in vector space. Similarity is usually measured with cosine similarity. Sentence-transformer models such as all-MiniLM-L6-v2 produce sentence embeddings that work for semantic search.

## Retrieval-Augmented Generation
RAG first retrieves relevant passages from an external knowledge base and then places them in the prompt so the model answers from that evidence. The pipeline is: load documents, extract text, split into chunks, create embeddings, store them in a vector index such as FAISS or ChromaDB, embed the user query, retrieve the nearest chunks, build a prompt with the retrieved context and generate an answer with source references. RAG reduces hallucination, supports private and frequently updated knowledge without retraining and allows citations.

## Chunking strategy
Chunks that are too large dilute relevance and waste context space; chunks that are too small lose meaning. Moderate chunks of a few hundred tokens, split on natural boundaries such as headings or sentences and with slight overlap, usually work well.

## Fine-tuning versus RAG
Fine-tuning changes a model's weights and is best for style, format and specialised task behaviour; it is not a reliable way to add new facts. RAG is better when knowledge changes often or when answers must cite sources. The two can be combined.

## Evaluating LLM applications
Evaluate with a rubric, a labelled test set and consistent scoring, check groundedness against sources, track latency and cost and keep humans in the loop for high-stakes decisions.

## AI agents
An agent uses an LLM to decide which tool or workflow to run next. Orchestration code routes tasks to specialised components such as retrieval, evaluation or planning, passes shared context between them and handles failures.
