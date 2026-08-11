# generate_report.py
from rich.console import Console
from src.reporter import ReportGenerator

console = Console()


def main():
    console.print("[bold cyan]Aggregating raw logs...[/bold cyan]")

    reporter = ReportGenerator()
    report_path = reporter.generate_html_report()

    if report_path:
        console.print(f"[bold green]✅ Report successfully generated![/bold green]")
        console.print(
            f"Open this file in your browser to view it: [bold underline]{report_path}[/bold underline]"
        )


if __name__ == "__main__":
    main()
