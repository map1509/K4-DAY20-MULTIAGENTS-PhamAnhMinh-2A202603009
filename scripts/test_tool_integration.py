"""Part 4.5: local worker/tool collaboration, without model calls."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

from agents import DataAgent, CodeAgent, EvaluatorAgent
from coordinator import Coordinator


def main():
    outputs = Path(__file__).resolve().parents[1] / "outputs"
    outputs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        with closing(sqlite3.connect(Path(directory) / "sales.db")) as connection:
            connection.execute("CREATE TABLE sales (year INTEGER, amount REAL)")
            connection.executemany("INSERT INTO sales VALUES (?, ?)", [(2026, index + 1) for index in range(50)])
            connection.commit()
        data = DataAgent(db_connection="sales.db", workspace=directory)
        code = CodeAgent(workspace=outputs)
        evaluator = EvaluatorAgent(workspace=outputs)
        coordinator = Coordinator(worker_agents=[data, code, evaluator])
        try:
            result = coordinator.process({"task_type": "data_analysis", "parameters": {
                "operation": "query_database", "query": "SELECT * FROM sales WHERE year=2026"}})
            assert result["status"] == "success", result
            sales = result["data"]
            assert sales["rows"] == 50
            print('Test: Data Agent queries database\n  SQL: SELECT * FROM sales WHERE year=2026\n  Result: 50 rows returned PASS')
            amounts = [row["amount"] for row in sales["data"]]
            plot_code = (
                "import matplotlib.pyplot as plt\n"
                f"amounts = {amounts!r}\n"
                "plt.figure()\nplt.plot(range(1, len(amounts) + 1), amounts)\n"
                "plt.title('Sales 2026')\nplt.xlabel('Record')\nplt.ylabel('Amount')\n"
                "plt.savefig('sales_chart.png')\nplt.close()\nprint('Chart created')\n"
            )
            result = coordinator.process({"task_type": "code_generation", "parameters": {
                "operation": "python_repl", "code": plot_code}})
            assert result["status"] == "success" and result["code"]["status"] == "success", result
            chart = outputs / "sales_chart.png"
            assert chart.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            print('Test: Code Agent creates visualization\n  Python: matplotlib plot from queried sales\n  REPL: executed successfully\n  File: outputs/sales_chart.png PASS')
            result = coordinator.process({"task_type": "evaluation", "parameters": {
                "operation": "score_result", "result": "Sales 2026: 50 rows; chart generated",
                "scores": {"accuracy": 85, "completeness": 90, "clarity": 80, "performance": 82.5}}})
            assert result["status"] == "success", result
            scoring = result["evaluation"]
            assert scoring["weighted_score"] == 85 and scoring["grade"] == "B"
            valid = evaluator.validation_tool.invoke({"result": scoring, "required_fields": ["scores", "weighted_score", "grade"]})
            assert valid["valid"]
            print('Test: Evaluator scores the result\n  Supplied rubric scores: accuracy=85, completeness=90, clarity=80, performance=82.5\n  Overall: 85/100 (B) PASS')
            print("All tool tests passed! (3/3)")
        finally:
            data.close()
            code.close()


if __name__ == "__main__":
    main()
