import tiktoken
from typing import List
from datetime import datetime
from rich.console import Console
from rich.table import Table
from src.models import CostMetrics

console = Console()


class CostTracker:
    """Track and report API usage costs"""
    
    PRICING = {
        "claude-sonnet-4": {
            "input": 3.00 / 1_000_000,   # $3 per million input tokens
            "output": 15.00 / 1_000_000   # $15 per million output tokens
        },
        "claude-sonnet-4-5": {
            "input": 3.00 / 1_000_000,
            "output": 15.00 / 1_000_000
        }
    }
    
    def __init__(self):
        self.metrics: List[CostMetrics] = []
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return len(self.encoding.encode(text))
    
    def record_usage(
        self,
        section_name: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "claude-sonnet-4"
    ):
        """Record API usage and calculate cost"""
        pricing = self.PRICING.get(model, self.PRICING["claude-sonnet-4"])
        
        cost = (
            input_tokens * pricing["input"] +
            output_tokens * pricing["output"]
        )
        
        metric = CostMetrics(
            section_name=section_name,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=model
        )
        
        self.metrics.append(metric)
        return cost
    
    def get_total_cost(self) -> float:
        """Calculate total cost across all operations"""
        return sum(m.cost_usd for m in self.metrics)
    
    def get_total_tokens(self) -> tuple[int, int]:
        """Get total input and output tokens"""
        total_input = sum(m.input_tokens for m in self.metrics)
        total_output = sum(m.output_tokens for m in self.metrics)
        return total_input, total_output
    
    def print_summary(self):
        """Print cost summary table"""
        table = Table(title="💰 Cost Tracking Summary")
        
        table.add_column("Section", style="cyan")
        table.add_column("Operation", style="magenta")
        table.add_column("Input Tokens", justify="right", style="green")
        table.add_column("Output Tokens", justify="right", style="yellow")
        table.add_column("Cost (USD)", justify="right", style="red")
        
        for metric in self.metrics:
            table.add_row(
                metric.section_name,
                metric.operation,
                f"{metric.input_tokens:,}",
                f"{metric.output_tokens:,}",
                f"${metric.cost_usd:.4f}"
            )
        
        total_in, total_out = self.get_total_tokens()
        total_cost = self.get_total_cost()
        
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            f"[bold]{total_in:,}[/bold]",
            f"[bold]{total_out:,}[/bold]",
            f"[bold]${total_cost:.2f}[/bold]"
        )
        
        console.print(table)
        
        if total_cost > 5.0:
            console.print(f"[red]⚠️  Warning: Cost ${total_cost:.2f} exceeds target of $5.00[/red]")
        else:
            console.print(f"[green]✓ Cost ${total_cost:.2f} within target ($2-5)[/green]")
