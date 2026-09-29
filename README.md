# Job Hunter AI Agent

## Open-Weights-AI Local Hunter (No ChatGPT, Claude, Anthropic..)

Run your own AI locally in your computer and let it find an adequated job position.

An automated, local-first job evaluation pipeline built with **Python**, **Streamlit**, and **Ollama**.

What does this tool:

- **Search job postings** across tech & engineering boards (Remotive, RemoteOK, WeWorkRemotely in `web_search.py`) -> But you can customize to your will in code.
- **Uses open-weight LLMs** (`Qwen2.5-7B`, `Llama3.2-3B`) to rank candidate fit using strict JSON evaluations -> keeps your privacy and it is independent from the big-tech AIs.

---

## 🛠 Project Architecture & File Structure

```text
├── app.py              # Interactive Streamlit frontend UI
├── main_locally.py     # Local job evaluation & Ollama JSON parsing pipeline
├── web_search.py       # Data fetching functions for external job APIs/RSS
├── flake.nix           # NixOS dev shell configuration
├── flake.lock          # Pin dependencies for Nix flake reproducibility
├── requirements.txt    # Python dependencies managed inside local .venv
└── .gitignore          # Excludes VRAM caches, local .venv, PDFs, and secrets
```

## Setup, Installation and Launch

1. **NixOS Environment Setup (Recommended)**
    If you are on NixOS or using Nix Flakes, enter the environment to load system-level dependencies (`Python 3.11`, `OpenSSL`, `glibc`):

    ```bash
        nix develop
    ```

    **Note on Python version**: *Python version 3.11 is chosen concretely to avoid future conflicts with packages that are not entirely fitting in NixOs. For Machine Learning purposes that version is a stable choice for other improved modules (such as tensorflow, scikit-learn...) as I experienced*
    - `flake.nix` contains `pip` and `virtualenv` to allow precisely to install manually modules like `pypdf` `streamlit` `requests` `pandas`


    **Note on Virtual Environment:** To bypass Python packaging issues on NixOS, create and activate a local virtual environment inside the shell:

    ```python
        python -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    ```

2. **Pulling Open-Weight Models via Ollama**
    Ensure the Ollama service is running locally (`localhost:11434`), then pull the required models:

    ```bash
        # Pull primary evaluation model
        ollama pull qwen2.5:7b

        # (Optional) Pull secondary heavyweight model
        ollama pull deepseek-r1:7b

        # (Optional) Pull lightweight model
        ollama pull llama3.2:3b
    ```

    Depending on the search one model would be better than other. One can have the three model at hand and then choose the convenient.

3. **Launching the App**
    Start the Streamlit dashboard:

    ```bash
        streamlit run app.py
    ```

## Key Caveats & Hardware Considerations

As the AI Agent runs entirely in your computer, some considerations should be taken:

1. **Memory Bandwidth & VRAM Bottlenecks**
    - **VRAM Capacity:** Models run fastest when fully offloaded to GPU VRAM (~4.5 GB for `qwen2.5:7b`). If VRAM overflows into system RAM, token generation speed drops dramatically.

    - **Context Length Allocation:** Job evaluations use up to 8192 tokens (`num_ctx: 8192`) to parse entire CVs and job postings. Large context windows consume additional KV-cache memory in VRAM.

2. **Ollama Environment Optimization**
    To handle concurrent evaluations without timeouts, set environment variables before starting Ollama:

    ```bash
        # Enable 2 parallel request streams in Ollama
        export OLLAMA_NUM_PARALLEL=2

        # Keep models loaded in VRAM between requests (prevents disk reload delay)
        export OLLAMA_KEEP_ALIVE=-1
    ```

    You can add those commands directly on the command window or, if you are using NixOs, add them direcly in the Ollama configuraion in the `configuration.nix` file

3. **Rate Limits & Web Sources**
    External job sources (e.g., `RemoteOK`) enforce strict API rate limits. Sequential polling is built into web_search.py to prevent IP blocks.

    *By adding small pauses (`time.sleep()`) and fetching one API after another sequentially, the network traffic looks like normal human browsing rather than a automated bot, trying to keep the IP safe from blocks.*
