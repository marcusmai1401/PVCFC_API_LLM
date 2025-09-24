"""
Report Lab Component - Generate reports from templates
"""

import streamlit as st


def render():
    """Render report lab component"""
    st.header("📄 Report Lab")
    st.caption("Generate structured reports using templates and multiple queries")

    # Main layout
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Report Configuration")

        # Report topic
        topic = st.text_input(
            "Report Topic",
            placeholder="e.g., Thông số vận hành chính KT06101",
            help="Main topic for the report",
        )

        # Sub-queries
        st.write("Sub-queries")
        num_queries = st.number_input("Number of sub-queries", 1, 10, 3)

        sub_queries = []
        for i in range(num_queries):
            query = st.text_input(
                f"Query {i+1}",
                key=f"subquery_{i}",
                placeholder=f"Enter sub-query {i+1}...",
            )
            if query:
                sub_queries.append(query)

        # Template selection
        st.write("Template")
        template_source = st.radio(
            "Template Source", ["Built-in", "Upload", "Custom"], horizontal=True
        )

        if template_source == "Built-in":
            template = st.selectbox(
                "Select Template",
                ["Technical Report", "Summary Report", "Comparison Report"],
            )
        elif template_source == "Upload":
            uploaded_file = st.file_uploader("Upload template (.md)", type=["md"])
        else:
            st.text_area("Custom Template (Markdown + Jinja2)", height=200)

        # Format options
        output_format = st.radio(
            "Output Format", ["Markdown", "HTML", "Word (Phase 2)"], horizontal=True
        )

        # Language
        language = st.radio("Language", ["vi", "en"], horizontal=True)

        # Generate button
        if st.button("📝 Generate Report", type="primary", use_container_width=True):
            if topic and sub_queries:
                with st.spinner("Generating report..."):
                    # TODO: Implement API call in Phase 4
                    st.success(
                        "Report generated! (Phase 4 will implement actual generation)"
                    )
            else:
                st.warning("Please fill in topic and at least one sub-query")

    with col2:
        st.subheader("Report Preview")

        # Preview tabs
        preview_tab, template_tab, export_tab = st.tabs(
            ["Preview", "Template", "Export"]
        )

        with preview_tab:
            st.info("📄 Report preview will appear here after generation")

            # Sample preview placeholder
            with st.expander("Sample Report Structure"):
                st.markdown(
                    """
                # Báo cáo: [Topic]

                ## Tóm tắt
                [Executive summary]

                ## 1. [Sub-query 1]
                [Content with citations]

                ## 2. [Sub-query 2]
                [Content with citations]

                ## Kết luận
                [Conclusions]

                ## Tài liệu tham khảo
                [Citations list]
                """
                )

        with template_tab:
            st.info("📝 Template editor will be available here")
            st.code(
                """
# {{ title }}

## Summary
{{ summary }}

{% for section in sections %}
## {{ loop.index }}. {{ section.heading }}
{{ section.content }}

Citations: {% for cite in section.citations %}
- [{{ cite.doc_id }}] Page {{ cite.page }}
{% endfor %}
{% endfor %}
            """,
                language="jinja2",
            )

        with export_tab:
            st.info("💾 Export options will appear here after generation")

            # Export buttons (disabled for now)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.button("Download Markdown", disabled=True, use_container_width=True)
            with col2:
                st.button("Download HTML", disabled=True, use_container_width=True)
            with col3:
                st.button("Download Word", disabled=True, use_container_width=True)

    # Template library
    st.divider()
    st.subheader("Template Library")
    st.info("📚 Template library and management will be implemented in Phase 4")
