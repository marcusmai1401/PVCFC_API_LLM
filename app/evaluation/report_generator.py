"""
HTML Report Generator for Evaluation Results
Creates comprehensive HTML reports with visualizations and insights.
"""
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class HTMLReportGenerator:
    """Generate HTML evaluation reports."""

    def __init__(self):
        self.logger = logger.bind(component="html_report_generator")

    async def generate_report(
        self,
        metrics: Dict[str, Any],
        results: List[Any],
        config: Any,
        output_path: Path,
    ) -> Path:
        """Generate comprehensive HTML report."""
        self.logger.info(f"Generating HTML report: {output_path}")

        try:
            html_content = self._generate_html_content(metrics, results, config)
            # Also generate a Markdown summary alongside HTML
            md_path = output_path.with_suffix(".md")
            md_content = self._generate_markdown_summary(metrics, config)
            with open(md_path, "w", encoding="utf-8") as fmd:
                fmd.write(md_content)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            self.logger.info(f"📄 HTML report saved: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to generate HTML report: {e}")
            raise

    def _generate_html_content(
        self, metrics: Dict[str, Any], results: List[Any], config: Any
    ) -> str:
        """Generate complete HTML content."""

        # Extract key metrics
        overall = metrics.get("overall", {})
        retrieval = metrics.get("retrieval", {})
        e2e = metrics.get("e2e", {})
        latency = metrics.get("latency", {})
        behavior = metrics.get("behavior_validation", {})

        breakdown_by_intent = metrics.get("breakdown_by_intent", {})
        breakdown_by_doc = metrics.get("breakdown_by_doc_category", {})

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG Evaluation Report</title>
    <style>
        {self._get_css_styles()}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>🎯 RAG Evaluation Report</h1>
            <div class="meta-info">
                <span>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                <span>QA Dataset: {Path(config.qa_file).name}</span>
            </div>
        </header>

        <!-- Executive Summary -->
        <section class="section">
            <h2>📊 Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="metric-value">{overall.get('total_questions', 0)}</div>
                    <div class="metric-label">Total Questions</div>
                </div>
                <div class="summary-card">
                    <div class="metric-value">{overall.get('success_rate', 0):.1%}</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="summary-card">
                    <div class="metric-value">{retrieval.get('avg_recall_at_5', 0):.3f}</div>
                    <div class="metric-label">Avg Recall@5</div>
                </div>
                <div class="summary-card">
                    <div class="metric-value">{e2e.get('avg_citation_rate', 0):.3f}</div>
                    <div class="metric-label">Avg Citation Rate</div>
                </div>
                <div class="summary-card">
                    <div class="metric-value">{latency.get('avg_total_latency_ms', 0):.0f}ms</div>
                    <div class="metric-label">Avg Latency</div>
                </div>
                <div class="summary-card">
                    <div class="metric-value">{behavior.get('behavior_compliance_rate', 0):.1%}</div>
                    <div class="metric-label">Behavior Compliance</div>
                </div>
            </div>
        </section>

        <!-- Performance Metrics -->
        <section class="section">
            <h2>🔍 Performance Metrics</h2>
            <div class="metrics-grid">

                <!-- Retrieval Performance -->
                <div class="metric-card">
                    <h3>Retrieval Performance</h3>
                    <div class="metric-row">
                        <span>Recall@5:</span>
                        <span class="metric-val">{retrieval.get('avg_recall_at_5', 0):.3f}</span>
                    </div>
                    <div class="metric-row">
                        <span>Recall@10:</span>
                        <span class="metric-val">{retrieval.get('avg_recall_at_10', 0):.3f}</span>
                    </div>
                    <div class="metric-row">
                        <span>Precision@5:</span>
                        <span class="metric-val">{retrieval.get('avg_precision_at_5', 0):.3f}</span>
                    </div>
                </div>

                <!-- E2E Performance -->
                <div class="metric-card">
                    <h3>End-to-End Performance</h3>
                    <div class="metric-row">
                        <span>Citation Rate:</span>
                        <span class="metric-val">{e2e.get('avg_citation_rate', 0):.3f}</span>
                    </div>
                    <div class="metric-row">
                        <span>Answer Quality:</span>
                        <span class="metric-val">{e2e.get('avg_answer_quality', 0):.3f}</span>
                    </div>
                    <div class="metric-row">
                        <span>CoVe Score:</span>
                        <span class="metric-val">{e2e.get('avg_cove_score', 0):.3f}</span>
                    </div>
                </div>

                <!-- Latency Performance -->
                <div class="metric-card">
                    <h3>Latency Performance</h3>
                    <div class="metric-row">
                        <span>Avg Total:</span>
                        <span class="metric-val">{latency.get('avg_total_latency_ms', 0):.0f}ms</span>
                    </div>
                    <div class="metric-row">
                        <span>P95:</span>
                        <span class="metric-val">{latency.get('p95_total_latency_ms', 0):.0f}ms</span>
                    </div>
                    <div class="metric-row">
                        <span>P99:</span>
                        <span class="metric-val">{latency.get('p99_total_latency_ms', 0):.0f}ms</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Breakdowns -->
        <section class="section">
            <h2>📈 Performance Breakdown</h2>

            <div class="breakdown-container">
                <div class="breakdown-section">
                    <h3>By Intent</h3>
                    <div class="breakdown-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Intent</th>
                                    <th>Count</th>
                                    <th>Citation Rate</th>
                                    <th>Avg Latency</th>
                                    <th>Compliance</th>
                                </tr>
                            </thead>
                            <tbody>
                                {self._generate_breakdown_rows(breakdown_by_intent)}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="breakdown-section">
                    <h3>By Document Category</h3>
                    <div class="breakdown-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Doc Category</th>
                                    <th>Count</th>
                                    <th>Citation Rate</th>
                                    <th>Avg Latency</th>
                                    <th>Compliance</th>
                                </tr>
                            </thead>
                            <tbody>
                                {self._generate_breakdown_rows(breakdown_by_doc)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- Sample Results -->
        {self._generate_sample_results_section(results)}

        <!-- Configuration Details -->
        <section class="section">
            <h2>⚙️ Configuration</h2>
            <div class="config-details">
                <div class="config-row">
                    <span>QA File:</span>
                    <span>{config.qa_file}</span>
                </div>
                <div class="config-row">
                    <span>Max Workers:</span>
                    <span>{config.max_workers}</span>
                </div>
                <div class="config-row">
                    <span>Batch Size:</span>
                    <span>{config.batch_size}</span>
                </div>
                <div class="config-row">
                    <span>Sample Size:</span>
                    <span>{config.sample_size or 'All'}</span>
                </div>
                <div class="config-row">
                    <span>Retrieval Endpoint:</span>
                    <span>{config.retrieval_endpoint or 'Simulation'}</span>
                </div>
                <div class="config-row">
                    <span>RAG Endpoint:</span>
                    <span>{config.rag_endpoint or 'Simulation'}</span>
                </div>
            </div>
        </section>

        <footer class="footer">
            <p>Generated by RAG Evaluation System</p>
        </footer>
    </div>
</body>
</html>
        """

        return html

    def _generate_markdown_summary(self, metrics: Dict[str, Any], config: Any) -> str:
        """Generate a concise Markdown summary aligned with phase3_report_template.md."""
        overall = metrics.get("overall", {})
        retrieval = metrics.get("retrieval", {})
        e2e = metrics.get("e2e", {})
        latency = metrics.get("latency", {})
        breakdown_intent = metrics.get("breakdown_by_intent", {})
        breakdown_doc = metrics.get("breakdown_by_doc_category", {})

        def row_intent(intent, data):
            return f"| {intent} | {data.get('count',0)} | {data.get('avg_citation_rate',0):.3f} | {data.get('avg_total_latency_ms',0):.0f} | {data.get('behavior_compliance_rate',0):.1%} |"

        def row_doc(cat, data):
            return f"| {cat} | {data.get('count',0)} | {data.get('avg_citation_rate',0):.3f} | {data.get('avg_total_latency_ms',0):.0f} | {data.get('behavior_compliance_rate',0):.1%} |"

        md = []
        md.append(f"## Phase 3 — Batch Evaluation Report")
        md.append("")
        md.append("### 1) Summary")
        md.append(
            f"- QA dataset: {getattr(config,'qa_file','')}\n- Total questions: {overall.get('total_questions',0)}\n- Success rate: {overall.get('success_rate',0):.1%}"
        )
        md.append("")
        md.append("### 2) Retrieval Performance")
        md.append(f"- Recall@5: {retrieval.get('avg_recall_at_5',0):.3f}")
        md.append(f"- Recall@10: {retrieval.get('avg_recall_at_10',0):.3f}")
        md.append(f"- Precision@5: {retrieval.get('avg_precision_at_5',0):.3f}")
        md.append("")
        md.append("### 3) End-to-End Performance")
        md.append(f"- Citation Rate: {e2e.get('avg_citation_rate',0):.3f}")
        md.append(f"- Answer Quality: {e2e.get('avg_answer_quality',0):.3f}")
        md.append(f"- CoVe Score: {e2e.get('avg_cove_score',0):.3f}")
        md.append("")
        md.append("### 4) Latency")
        md.append(
            f"- Avg Total Latency: {latency.get('avg_total_latency_ms',0):.0f} ms"
        )
        md.append(f"- P95: {latency.get('p95_total_latency_ms',0):.0f} ms")
        md.append(f"- P99: {latency.get('p99_total_latency_ms',0):.0f} ms")
        md.append("")
        md.append("### 5) Breakdown by Intent")
        md.append("| Intent | Count | Citation Rate | Avg Latency | Compliance |")
        md.append("|---|---:|---:|---:|---:|")
        for intent, data in (breakdown_intent or {}).items():
            md.append(row_intent(intent, data))
        md.append("")
        md.append("### 6) Breakdown by Document Category")
        md.append("| Doc Category | Count | Citation Rate | Avg Latency | Compliance |")
        md.append("|---|---:|---:|---:|---:|")
        for cat, data in (breakdown_doc or {}).items():
            md.append(row_doc(cat, data))
        md.append("")
        md.append("### 7) Configuration")
        md.append(
            f"- Max workers: {getattr(config,'max_workers','')}\n- Batch size: {getattr(config,'batch_size','')}\n- Sample size: {getattr(config,'sample_size','All')}\n- Retrieval endpoint: {getattr(config,'retrieval_endpoint','Simulation')}\n- RAG endpoint: {getattr(config,'rag_endpoint','Simulation')}"
        )
        md.append("")
        return "\n".join(md)

    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report."""
        return """
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f5f5f5;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
            }

            .meta-info {
                display: flex;
                justify-content: center;
                gap: 30px;
                font-size: 0.9rem;
                opacity: 0.9;
            }

            .section {
                background: white;
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }

            .section h2 {
                color: #2d3748;
                margin-bottom: 20px;
                font-size: 1.8rem;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
            }

            .summary-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }

            .summary-card {
                text-align: center;
                padding: 20px;
                border-radius: 8px;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
            }

            .metric-value {
                font-size: 2rem;
                font-weight: bold;
                margin-bottom: 5px;
            }

            .metric-label {
                font-size: 0.9rem;
                opacity: 0.9;
            }

            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }

            .metric-card {
                border: 1px solid #e2e8f0;
                padding: 20px;
                border-radius: 8px;
                background: #f9f9f9;
            }

            .metric-card h3 {
                color: #4a5568;
                margin-bottom: 15px;
                font-size: 1.2rem;
            }

            .metric-row {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e2e8f0;
            }

            .metric-row:last-child {
                border-bottom: none;
            }

            .metric-val {
                font-weight: bold;
                color: #2d3748;
            }

            .breakdown-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 30px;
            }

            .breakdown-section h3 {
                color: #4a5568;
                margin-bottom: 15px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }

            th, td {
                text-align: left;
                padding: 12px;
                border-bottom: 1px solid #e2e8f0;
            }

            th {
                background-color: #f7fafc;
                font-weight: 600;
                color: #4a5568;
            }

            tbody tr:hover {
                background-color: #f7fafc;
            }

            .sample-results {
                margin-top: 20px;
            }

            .sample-item {
                border: 1px solid #e2e8f0;
                padding: 15px;
                margin-bottom: 15px;
                border-radius: 6px;
                background: #fafafa;
            }

            .sample-query {
                font-weight: bold;
                color: #2d3748;
                margin-bottom: 8px;
            }

            .sample-meta {
                font-size: 0.8rem;
                color: #718096;
                display: flex;
                gap: 15px;
                margin-bottom: 8px;
            }

            .sample-answer {
                font-size: 0.9rem;
                line-height: 1.5;
                color: #4a5568;
            }

            .config-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 15px;
            }

            .config-row {
                display: flex;
                justify-content: space-between;
                padding: 10px;
                background: #f7fafc;
                border-radius: 6px;
            }

            .footer {
                text-align: center;
                padding: 20px;
                color: #718096;
                font-size: 0.9rem;
            }

            @media (max-width: 768px) {
                .container {
                    padding: 15px;
                }

                .header h1 {
                    font-size: 2rem;
                }

                .meta-info {
                    flex-direction: column;
                    gap: 10px;
                }

                .summary-grid {
                    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                }

                .breakdown-container {
                    grid-template-columns: 1fr;
                }
            }
        """

    def _generate_breakdown_rows(
        self, breakdown_data: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate table rows for breakdown data."""
        if not breakdown_data:
            return "<tr><td colspan='5'>No data available</td></tr>"

        rows = []
        for category, data in breakdown_data.items():
            count = data.get("count", 0)
            citation_rate = data.get("avg_citation_rate", 0)
            latency = data.get("avg_total_latency_ms", 0)
            compliance = data.get("behavior_compliance_rate", 0)

            row = f"""
                <tr>
                    <td>{category or 'N/A'}</td>
                    <td>{count}</td>
                    <td>{citation_rate:.3f}</td>
                    <td>{latency:.0f}ms</td>
                    <td>{compliance:.1%}</td>
                </tr>
            """
            rows.append(row)

        return "".join(rows)

    def _generate_sample_results_section(self, results: List[Any]) -> str:
        """Generate sample results section."""
        if not results:
            return ""

        # Show first 5 interesting results
        sample_results = results[:5]

        sample_html = """
        <section class="section">
            <h2>🔍 Sample Results</h2>
            <div class="sample-results">
        """

        for result in sample_results:
            if hasattr(result, "to_dict"):
                result_dict = result.to_dict()
            else:
                result_dict = result

            query = result_dict.get("query", "N/A")[:100]
            qa_id = result_dict.get("qa_id", "N/A")
            intent = result_dict.get("intent", "N/A")
            citation_rate = result_dict.get("citation_rate", 0)
            answer = result_dict.get("generated_answer", "N/A")[:200]

            sample_html += f"""
                <div class="sample-item">
                    <div class="sample-query">{query}...</div>
                    <div class="sample-meta">
                        <span>ID: {qa_id}</span>
                        <span>Intent: {intent}</span>
                        <span>Citation Rate: {citation_rate:.2f}</span>
                    </div>
                    <div class="sample-answer">{answer}...</div>
                </div>
            """

        sample_html += """
            </div>
        </section>
        """

        return sample_html
