"""
⚙️ Configuration Component

Interface for configuring RAG parameters, model settings, and evaluation configurations.
Allows users to adjust system settings and save configurations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st


def show_configuration_page():
    """Display the configuration interface."""
    st.title("⚙️ Configuration - System Settings")

    st.markdown(
        """
    Configure your RAG pipeline settings, model parameters, and evaluation criteria.
    Changes are saved automatically and can be exported for deployment.
    """
    )

    # Tabs for different configuration sections
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🤖 Model Settings",
            "🔍 Retrieval Config",
            "📊 Evaluation Config",
            "💾 Save/Load Config",
        ]
    )

    with tab1:
        show_model_settings()

    with tab2:
        show_retrieval_config()

    with tab3:
        show_evaluation_config()

    with tab4:
        show_save_load_config()


def show_model_settings():
    """Show model configuration settings."""
    st.markdown("### 🤖 Model Settings")

    # Initialize session state for model config
    if "model_config" not in st.session_state:
        st.session_state.model_config = get_default_model_config()

    config = st.session_state.model_config

    # Language Model Settings
    st.markdown("#### 🧠 Language Model Configuration")

    col1, col2 = st.columns(2)

    with col1:
        # Primary model selection
        primary_model = st.selectbox(
            "Primary Language Model",
            ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "gemini-pro", "llama-2-70b"],
            index=[
                "gpt-4",
                "gpt-3.5-turbo",
                "claude-3-sonnet",
                "gemini-pro",
                "llama-2-70b",
            ].index(config.get("primary_model", "gpt-4")),
        )

        # Fallback model
        fallback_model = st.selectbox(
            "Fallback Model",
            ["gpt-3.5-turbo", "claude-3-haiku", "gemini-flash", "none"],
            index=["gpt-3.5-turbo", "claude-3-haiku", "gemini-flash", "none"].index(
                config.get("fallback_model", "gpt-3.5-turbo")
            ),
        )

        # API settings
        st.markdown("**🔑 API Configuration**")
        api_timeout = st.slider(
            "API Timeout (seconds)",
            min_value=10,
            max_value=120,
            value=config.get("api_timeout", 30),
        )

        max_retries = st.slider(
            "Max Retries", min_value=1, max_value=5, value=config.get("max_retries", 3)
        )

    with col2:
        # Generation parameters
        st.markdown("**📝 Generation Parameters**")

        max_tokens = st.slider(
            "Max Tokens",
            min_value=100,
            max_value=4000,
            value=config.get("max_tokens", 1000),
        )

        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            step=0.1,
            value=config.get("temperature", 0.7),
        )

        top_p = st.slider(
            "Top-P",
            min_value=0.1,
            max_value=1.0,
            step=0.1,
            value=config.get("top_p", 0.9),
        )

        presence_penalty = st.slider(
            "Presence Penalty",
            min_value=-2.0,
            max_value=2.0,
            step=0.1,
            value=config.get("presence_penalty", 0.0),
        )

        frequency_penalty = st.slider(
            "Frequency Penalty",
            min_value=-2.0,
            max_value=2.0,
            step=0.1,
            value=config.get("frequency_penalty", 0.0),
        )

    # Advanced settings
    with st.expander("🔧 Advanced Model Settings"):
        col1, col2 = st.columns(2)

        with col1:
            system_prompt_template = st.text_area(
                "System Prompt Template",
                value=config.get("system_prompt", get_default_system_prompt()),
                height=150,
                help="Use {context} and {query} as placeholders",
            )

            enable_streaming = st.checkbox(
                "Enable Streaming Response", value=config.get("enable_streaming", False)
            )

        with col2:
            response_format = st.selectbox(
                "Response Format",
                ["text", "json", "structured"],
                index=["text", "json", "structured"].index(
                    config.get("response_format", "text")
                ),
            )

            enable_function_calling = st.checkbox(
                "Enable Function Calling",
                value=config.get("enable_function_calling", False),
            )

            if enable_function_calling:
                st.info(
                    "⚡ Function calling allows the model to use external tools and APIs"
                )

    # Update configuration
    st.session_state.model_config.update(
        {
            "primary_model": primary_model,
            "fallback_model": fallback_model,
            "api_timeout": api_timeout,
            "max_retries": max_retries,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "system_prompt": system_prompt_template,
            "enable_streaming": enable_streaming,
            "response_format": response_format,
            "enable_function_calling": enable_function_calling,
        }
    )

    # Save button
    if st.button("💾 Save Model Configuration", type="primary"):
        st.success("✅ Model configuration saved!")


def show_retrieval_config():
    """Show retrieval configuration settings."""
    st.markdown("### 🔍 Retrieval Configuration")

    # Initialize session state for retrieval config
    if "retrieval_config" not in st.session_state:
        st.session_state.retrieval_config = get_default_retrieval_config()

    config = st.session_state.retrieval_config

    # Vector Database Settings
    st.markdown("#### 📊 Vector Database Settings")

    col1, col2 = st.columns(2)

    with col1:
        # Database selection
        vector_db = st.selectbox(
            "Vector Database",
            ["chroma", "pinecone", "weaviate", "qdrant", "milvus"],
            index=["chroma", "pinecone", "weaviate", "qdrant", "milvus"].index(
                config.get("vector_db", "chroma")
            ),
        )

        # Embedding model
        embedding_model = st.selectbox(
            "Embedding Model",
            [
                "text-embedding-ada-002",
                "text-embedding-3-small",
                "text-embedding-3-large",
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
            ],
            index=0,
        )

        # Retrieval parameters
        st.markdown("**🎯 Retrieval Parameters**")
        top_k = st.slider(
            "Top K Documents", min_value=5, max_value=50, value=config.get("top_k", 10)
        )

        similarity_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=config.get("similarity_threshold", 0.7),
        )

    with col2:
        # Search strategy
        st.markdown("**🔍 Search Strategy**")

        search_type = st.selectbox(
            "Search Type",
            ["similarity", "mmr", "similarity_score_threshold"],
            index=["similarity", "mmr", "similarity_score_threshold"].index(
                config.get("search_type", "similarity")
            ),
        )

        if search_type == "mmr":
            mmr_lambda = st.slider(
                "MMR Lambda (Diversity)",
                min_value=0.0,
                max_value=1.0,
                step=0.1,
                value=config.get("mmr_lambda", 0.5),
            )

        # Chunking strategy
        st.markdown("**📄 Document Chunking**")
        chunk_size = st.slider(
            "Chunk Size (characters)",
            min_value=100,
            max_value=2000,
            value=config.get("chunk_size", 1000),
        )

        chunk_overlap = st.slider(
            "Chunk Overlap (characters)",
            min_value=0,
            max_value=500,
            value=config.get("chunk_overlap", 200),
        )

    # Advanced retrieval settings
    with st.expander("🔧 Advanced Retrieval Settings"):
        col1, col2 = st.columns(2)

        with col1:
            # HyDE settings
            st.markdown("**🔮 HyDE (Hypothetical Document Embeddings)**")
            enable_hyde = st.checkbox(
                "Enable HyDE", value=config.get("enable_hyde", True)
            )

            if enable_hyde:
                hyde_model = st.selectbox(
                    "HyDE Generation Model",
                    ["gpt-3.5-turbo", "gpt-4", "claude-3-haiku"],
                    index=0,
                )

                hyde_prompt = st.text_area(
                    "HyDE Prompt Template",
                    value="Please write a passage to answer the question: {query}",
                    height=80,
                )

        with col2:
            # Reranking settings
            st.markdown("**📊 Reranking**")
            enable_reranking = st.checkbox(
                "Enable Reranking", value=config.get("enable_reranking", True)
            )

            if enable_reranking:
                rerank_model = st.selectbox(
                    "Reranking Model",
                    [
                        "cross-encoder/ms-marco-MiniLM-L-6-v2",
                        "BAAI/bge-reranker-base",
                        "custom",
                    ],
                    index=0,
                )

                rerank_top_k = st.slider(
                    "Rerank Top K",
                    min_value=3,
                    max_value=20,
                    value=config.get("rerank_top_k", 5),
                )

    # Metadata filtering
    st.markdown("#### 🏷️ Metadata Filtering")

    col1, col2 = st.columns(2)

    with col1:
        enable_metadata_filter = st.checkbox(
            "Enable Metadata Filtering",
            value=config.get("enable_metadata_filter", False),
        )

        if enable_metadata_filter:
            filter_fields = st.multiselect(
                "Filter Fields",
                ["document_type", "source", "date", "category", "language"],
                default=config.get("filter_fields", []),
            )

    with col2:
        if enable_metadata_filter:
            default_filters = st.text_area(
                "Default Filters (JSON)",
                value=json.dumps(config.get("default_filters", {}), indent=2),
                height=100,
                help="JSON object with default filter values",
            )

    # Update configuration
    retrieval_updates = {
        "vector_db": vector_db,
        "embedding_model": embedding_model,
        "top_k": top_k,
        "similarity_threshold": similarity_threshold,
        "search_type": search_type,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "enable_hyde": enable_hyde,
        "enable_reranking": enable_reranking,
        "enable_metadata_filter": enable_metadata_filter,
    }

    if search_type == "mmr":
        retrieval_updates["mmr_lambda"] = mmr_lambda

    if enable_hyde:
        retrieval_updates.update({"hyde_model": hyde_model, "hyde_prompt": hyde_prompt})

    if enable_reranking:
        retrieval_updates.update(
            {"rerank_model": rerank_model, "rerank_top_k": rerank_top_k}
        )

    if enable_metadata_filter:
        retrieval_updates.update(
            {
                "filter_fields": filter_fields,
                "default_filters": json.loads(default_filters)
                if default_filters
                else {},
            }
        )

    st.session_state.retrieval_config.update(retrieval_updates)

    # Save button
    if st.button("💾 Save Retrieval Configuration", type="primary"):
        st.success("✅ Retrieval configuration saved!")


def show_evaluation_config():
    """Show evaluation configuration settings."""
    st.markdown("### 📊 Evaluation Configuration")

    # Initialize session state for evaluation config
    if "evaluation_config" not in st.session_state:
        st.session_state.evaluation_config = get_default_evaluation_config()

    config = st.session_state.evaluation_config

    # Evaluation Settings
    st.markdown("#### 🎯 Evaluation Settings")

    col1, col2 = st.columns(2)

    with col1:
        # Evaluation modes
        st.markdown("**📋 Evaluation Modes**")

        run_retrieval_eval = st.checkbox(
            "Run Retrieval Evaluation",
            value=config.get("run_retrieval_eval", True),
            help="Evaluate document retrieval quality",
        )

        run_e2e_eval = st.checkbox(
            "Run End-to-End Evaluation",
            value=config.get("run_e2e_eval", True),
            help="Evaluate complete RAG pipeline",
        )

        run_citation_eval = st.checkbox(
            "Run Citation Evaluation",
            value=config.get("run_citation_eval", True),
            help="Evaluate citation accuracy and relevance",
        )

        run_latency_eval = st.checkbox(
            "Run Latency Evaluation",
            value=config.get("run_latency_eval", True),
            help="Measure response times and performance",
        )

    with col2:
        # Batch settings
        st.markdown("**⚡ Batch Processing**")

        batch_size = st.slider(
            "Batch Size", min_value=1, max_value=50, value=config.get("batch_size", 10)
        )

        max_workers = st.slider(
            "Max Concurrent Workers",
            min_value=1,
            max_value=10,
            value=config.get("max_workers", 4),
        )

        timeout_seconds = st.slider(
            "Request Timeout (seconds)",
            min_value=30,
            max_value=300,
            value=config.get("timeout_seconds", 60),
        )

    # Quality Metrics
    st.markdown("#### 🏆 Quality Metrics Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📊 Retrieval Metrics**")

        retrieval_metrics = st.multiselect(
            "Enabled Retrieval Metrics",
            ["recall@5", "recall@10", "precision@5", "precision@10", "mrr", "ndcg@10"],
            default=config.get("retrieval_metrics", ["recall@5", "precision@5"]),
        )

        st.markdown("**📝 Generation Metrics**")

        generation_metrics = st.multiselect(
            "Enabled Generation Metrics",
            [
                "answer_quality",
                "factual_consistency",
                "relevance",
                "completeness",
                "conciseness",
            ],
            default=config.get(
                "generation_metrics", ["answer_quality", "factual_consistency"]
            ),
        )

    with col2:
        st.markdown("**📖 Citation Metrics**")

        citation_metrics = st.multiselect(
            "Enabled Citation Metrics",
            [
                "citation_precision",
                "citation_recall",
                "source_diversity",
                "citation_quality",
            ],
            default=config.get("citation_metrics", ["citation_precision"]),
        )

        st.markdown("**⚡ Performance Metrics**")

        performance_metrics = st.multiselect(
            "Enabled Performance Metrics",
            ["response_time", "throughput", "token_usage", "cost_per_query"],
            default=config.get("performance_metrics", ["response_time"]),
        )

    # Evaluation Criteria
    with st.expander("🔧 Advanced Evaluation Settings"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**🎯 Quality Thresholds**")

            min_quality_score = st.slider(
                "Minimum Quality Score",
                min_value=0.0,
                max_value=1.0,
                step=0.1,
                value=config.get("min_quality_score", 0.7),
            )

            min_citation_precision = st.slider(
                "Minimum Citation Precision",
                min_value=0.0,
                max_value=1.0,
                step=0.1,
                value=config.get("min_citation_precision", 0.8),
            )

            max_response_time = st.slider(
                "Max Response Time (seconds)",
                min_value=1,
                max_value=30,
                value=config.get("max_response_time", 10),
            )

        with col2:
            st.markdown("**🔍 Evaluation Models**")

            quality_evaluator_model = st.selectbox(
                "Quality Evaluator Model",
                ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet"],
                index=0,
            )

            consistency_evaluator_model = st.selectbox(
                "Consistency Evaluator Model",
                ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet"],
                index=0,
            )

            enable_human_eval = st.checkbox(
                "Enable Human Evaluation Integration",
                value=config.get("enable_human_eval", False),
            )

    # Output Settings
    st.markdown("#### 💾 Output Configuration")

    col1, col2 = st.columns(2)

    with col1:
        # Report generation
        generate_html_report = st.checkbox(
            "Generate HTML Report", value=config.get("generate_html_report", True)
        )

        generate_json_report = st.checkbox(
            "Generate JSON Report", value=config.get("generate_json_report", True)
        )

        save_individual_results = st.checkbox(
            "Save Individual Results", value=config.get("save_individual_results", True)
        )

    with col2:
        # Output paths
        output_directory = st.text_input(
            "Output Directory",
            value=config.get("output_directory", "results/evaluation"),
            help="Directory to save evaluation results",
        )

        report_filename_prefix = st.text_input(
            "Report Filename Prefix",
            value=config.get("report_filename_prefix", "rag_evaluation"),
        )

    # Update configuration
    st.session_state.evaluation_config.update(
        {
            "run_retrieval_eval": run_retrieval_eval,
            "run_e2e_eval": run_e2e_eval,
            "run_citation_eval": run_citation_eval,
            "run_latency_eval": run_latency_eval,
            "batch_size": batch_size,
            "max_workers": max_workers,
            "timeout_seconds": timeout_seconds,
            "retrieval_metrics": retrieval_metrics,
            "generation_metrics": generation_metrics,
            "citation_metrics": citation_metrics,
            "performance_metrics": performance_metrics,
            "min_quality_score": min_quality_score,
            "min_citation_precision": min_citation_precision,
            "max_response_time": max_response_time,
            "quality_evaluator_model": quality_evaluator_model,
            "consistency_evaluator_model": consistency_evaluator_model,
            "enable_human_eval": enable_human_eval,
            "generate_html_report": generate_html_report,
            "generate_json_report": generate_json_report,
            "save_individual_results": save_individual_results,
            "output_directory": output_directory,
            "report_filename_prefix": report_filename_prefix,
        }
    )

    # Save button
    if st.button("💾 Save Evaluation Configuration", type="primary"):
        st.success("✅ Evaluation configuration saved!")


def show_save_load_config():
    """Show save/load configuration interface."""
    st.markdown("### 💾 Save/Load Configuration")

    # Current configuration summary
    st.markdown("#### 📋 Current Configuration Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🤖 Model Config**")
        if "model_config" in st.session_state:
            model_config = st.session_state.model_config
            st.metric("Primary Model", model_config.get("primary_model", "Not set"))
            st.metric("Max Tokens", model_config.get("max_tokens", "Not set"))
            st.metric("Temperature", f"{model_config.get('temperature', 'Not set')}")
        else:
            st.info("No model configuration set")

    with col2:
        st.markdown("**🔍 Retrieval Config**")
        if "retrieval_config" in st.session_state:
            retrieval_config = st.session_state.retrieval_config
            st.metric("Vector DB", retrieval_config.get("vector_db", "Not set"))
            st.metric("Top K", retrieval_config.get("top_k", "Not set"))
            st.metric(
                "HyDE Enabled", "✅" if retrieval_config.get("enable_hyde") else "❌"
            )
        else:
            st.info("No retrieval configuration set")

    with col3:
        st.markdown("**📊 Evaluation Config**")
        if "evaluation_config" in st.session_state:
            eval_config = st.session_state.evaluation_config
            st.metric("Batch Size", eval_config.get("batch_size", "Not set"))
            st.metric("Max Workers", eval_config.get("max_workers", "Not set"))
            st.metric(
                "HTML Report", "✅" if eval_config.get("generate_html_report") else "❌"
            )
        else:
            st.info("No evaluation configuration set")

    st.markdown("---")

    # Export configuration
    st.markdown("#### 📤 Export Configuration")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 Export Current Config as JSON"):
            config_data = {
                "model_config": st.session_state.get("model_config", {}),
                "retrieval_config": st.session_state.get("retrieval_config", {}),
                "evaluation_config": st.session_state.get("evaluation_config", {}),
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
            }

            json_str = json.dumps(config_data, indent=2, ensure_ascii=False)

            st.download_button(
                label="⬇️ Download Configuration",
                data=json_str,
                file_name=f"rag_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

    with col2:
        if st.button("📄 Export as Python Config"):
            config_data = {
                "model_config": st.session_state.get("model_config", {}),
                "retrieval_config": st.session_state.get("retrieval_config", {}),
                "evaluation_config": st.session_state.get("evaluation_config", {}),
            }

            python_config = generate_python_config(config_data)

            st.download_button(
                label="⬇️ Download Python Config",
                data=python_config,
                file_name=f"rag_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py",
                mime="text/plain",
            )

    st.markdown("---")

    # Import configuration
    st.markdown("#### 📥 Import Configuration")

    uploaded_config = st.file_uploader(
        "Upload Configuration File",
        type=["json", "py"],
        help="Upload a previously exported configuration file",
    )

    if uploaded_config is not None:
        try:
            if uploaded_config.name.endswith(".json"):
                config_data = json.loads(uploaded_config.getvalue().decode("utf-8"))

                # Update session state with imported config
                if "model_config" in config_data:
                    st.session_state.model_config = config_data["model_config"]

                if "retrieval_config" in config_data:
                    st.session_state.retrieval_config = config_data["retrieval_config"]

                if "evaluation_config" in config_data:
                    st.session_state.evaluation_config = config_data[
                        "evaluation_config"
                    ]

                st.success("✅ Configuration imported successfully!")

                # Show import summary
                with st.expander("📋 Import Summary"):
                    st.json(config_data)

                if st.button("🔄 Apply Imported Configuration"):
                    st.success(
                        "✅ Configuration applied! Navigate to other tabs to see the changes."
                    )
                    st.rerun()

            else:
                st.error(
                    "❌ Python config import not yet supported. Please use JSON format."
                )

        except Exception as e:
            st.error(f"❌ Error importing configuration: {str(e)}")

    # Preset configurations
    st.markdown("---")
    st.markdown("#### 🎯 Preset Configurations")

    preset_configs = {
        "🚀 High Performance": {
            "description": "Optimized for speed and throughput",
            "model_config": {
                "primary_model": "gpt-3.5-turbo",
                "max_tokens": 500,
                "temperature": 0.3,
            },
            "retrieval_config": {
                "top_k": 5,
                "enable_hyde": False,
                "enable_reranking": False,
            },
        },
        "🎯 High Accuracy": {
            "description": "Optimized for accuracy and quality",
            "model_config": {
                "primary_model": "gpt-4",
                "max_tokens": 1500,
                "temperature": 0.7,
            },
            "retrieval_config": {
                "top_k": 15,
                "enable_hyde": True,
                "enable_reranking": True,
            },
        },
        "⚖️ Balanced": {
            "description": "Balanced performance and accuracy",
            "model_config": {
                "primary_model": "gpt-3.5-turbo",
                "max_tokens": 1000,
                "temperature": 0.5,
            },
            "retrieval_config": {
                "top_k": 10,
                "enable_hyde": True,
                "enable_reranking": False,
            },
        },
    }

    col1, col2, col3 = st.columns(3)

    for i, (preset_name, preset_data) in enumerate(preset_configs.items()):
        col = [col1, col2, col3][i]

        with col:
            st.markdown(f"**{preset_name}**")
            st.markdown(preset_data["description"])

            if st.button(f"Apply {preset_name.split(' ', 1)[1]}", key=f"preset_{i}"):
                # Apply preset configuration
                if "model_config" not in st.session_state:
                    st.session_state.model_config = get_default_model_config()
                if "retrieval_config" not in st.session_state:
                    st.session_state.retrieval_config = get_default_retrieval_config()

                st.session_state.model_config.update(
                    preset_data.get("model_config", {})
                )
                st.session_state.retrieval_config.update(
                    preset_data.get("retrieval_config", {})
                )

                st.success(f"✅ {preset_name} configuration applied!")
                st.rerun()


def get_default_model_config() -> Dict[str, Any]:
    """Get default model configuration."""
    return {
        "primary_model": "gpt-4",
        "fallback_model": "gpt-3.5-turbo",
        "api_timeout": 30,
        "max_retries": 3,
        "max_tokens": 1000,
        "temperature": 0.7,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "system_prompt": get_default_system_prompt(),
        "enable_streaming": False,
        "response_format": "text",
        "enable_function_calling": False,
    }


def get_default_retrieval_config() -> Dict[str, Any]:
    """Get default retrieval configuration."""
    return {
        "vector_db": "chroma",
        "embedding_model": "text-embedding-ada-002",
        "top_k": 10,
        "similarity_threshold": 0.7,
        "search_type": "similarity",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "enable_hyde": True,
        "enable_reranking": True,
        "enable_metadata_filter": False,
        "mmr_lambda": 0.5,
        "rerank_top_k": 5,
        "filter_fields": [],
        "default_filters": {},
    }


def get_default_evaluation_config() -> Dict[str, Any]:
    """Get default evaluation configuration."""
    return {
        "run_retrieval_eval": True,
        "run_e2e_eval": True,
        "run_citation_eval": True,
        "run_latency_eval": True,
        "batch_size": 10,
        "max_workers": 4,
        "timeout_seconds": 60,
        "retrieval_metrics": ["recall@5", "precision@5"],
        "generation_metrics": ["answer_quality", "factual_consistency"],
        "citation_metrics": ["citation_precision"],
        "performance_metrics": ["response_time"],
        "min_quality_score": 0.7,
        "min_citation_precision": 0.8,
        "max_response_time": 10,
        "quality_evaluator_model": "gpt-4",
        "consistency_evaluator_model": "gpt-4",
        "enable_human_eval": False,
        "generate_html_report": True,
        "generate_json_report": True,
        "save_individual_results": True,
        "output_directory": "results/evaluation",
        "report_filename_prefix": "rag_evaluation",
    }


def get_default_system_prompt() -> str:
    """Get default system prompt template."""
    return """You are a helpful AI assistant that answers questions based on the provided context.

Instructions:
1. Use only the information provided in the context to answer the question
2. If the context doesn't contain enough information, say so clearly
3. Provide citations for your claims using the format [1], [2], etc.
4. Be accurate, concise, and helpful

Context:
{context}

Question: {query}

Answer:"""


def generate_python_config(config_data: Dict[str, Any]) -> str:
    """Generate Python configuration file."""
    return f'''"""
RAG Pipeline Configuration
Generated on: {datetime.now().isoformat()}
"""

# Model Configuration
MODEL_CONFIG = {json.dumps(config_data.get('model_config', {}), indent=4)}

# Retrieval Configuration
RETRIEVAL_CONFIG = {json.dumps(config_data.get('retrieval_config', {}), indent=4)}

# Evaluation Configuration
EVALUATION_CONFIG = {json.dumps(config_data.get('evaluation_config', {}), indent=4)}

# Usage example:
# from config import MODEL_CONFIG, RETRIEVAL_CONFIG, EVALUATION_CONFIG
#
# pipeline = RAGPipeline(
#     model_config=MODEL_CONFIG,
#     retrieval_config=RETRIEVAL_CONFIG
# )
'''
