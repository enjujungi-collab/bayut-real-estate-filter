from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from .models import Property, SearchFilters

console = Console()


def print_results(properties: list[Property], total: int, page: int, filters: SearchFilters) -> None:
    if not properties:
        console.print("[yellow]\n결과가 없습니다. 필터 조건을 완화해보세요.[/yellow]")
        return

    # 요약 패널
    summary_parts = [
        f"[cyan]{filters.location_name or '전체 지역'}[/cyan]",
        f"[green]{'매매' if filters.purpose == 'for-sale' else '임대'}[/green]",
        f"[magenta]{', '.join(filters.categories)}[/magenta]",
    ]
    if filters.rooms:
        labels = ["Studio" if r == 0 else f"{r}BR" for r in filters.rooms]
        summary_parts.append(f"[yellow]{'/'.join(labels)}[/yellow]")
    if filters.price_min or filters.price_max:
        pmin = f"{filters.price_min:,}" if filters.price_min else "0"
        pmax = f"{filters.price_max:,}" if filters.price_max else "∞"
        summary_parts.append(f"[blue]{pmin} ~ {pmax} AED[/blue]")

    console.print(Panel(
        " | ".join(summary_parts),
        title=f"[bold]검색 결과  (전체 {total:,}건 중 {len(properties)}건 표시)[/bold]",
        border_style="cyan",
    ))

    # 결과 테이블
    table = Table(
        show_header=True,
        header_style="bold white on dark_blue",
        box=box.ROUNDED,
        border_style="dim blue",
        row_styles=["", "dim"],
    )
    table.add_column("#",         width=4,  justify="right")
    table.add_column("위치",      min_width=22)
    table.add_column("유형",      width=12)
    table.add_column("가격",      width=14, justify="right")
    table.add_column("방",        width=8,  justify="center")
    table.add_column("면적",      width=12, justify="right")
    table.add_column("상태",      width=8,  justify="center")

    for i, p in enumerate(properties, 1):
        status = "[green]완공[/green]" if p.is_completed else "[yellow]분양중[/yellow]" if p.is_completed is False else "-"
        table.add_row(
            str(i),
            p.location,
            p.category,
            f"[bold green]{p.price_formatted}[/bold green]",
            p.bedrooms_label,
            p.area_formatted,
            status,
        )

    console.print(table)
    console.print(f"[dim]페이지 {page + 1} · 25개씩 표시[/dim]\n")


def print_property_detail(p: Property) -> None:
    lines = [
        f"[bold]{p.title}[/bold]",
        "",
        f"  위치:     {p.location}",
        f"  유형:     {p.category}",
        f"  목적:     {'매매' if p.purpose == 'for-sale' else '임대'}",
        f"  가격:     [bold green]{p.price_formatted}[/bold green]",
        f"  방/욕실:  {p.bedrooms_label} / {p.bathrooms or '-'}욕실",
        f"  면적:     {p.area_formatted}",
        f"  완공:     {'완공' if p.is_completed else '미완공' if p.is_completed is False else '미상'}",
    ]
    if p.agent_name:
        lines.append(f"  에이전트: {p.agent_name}" + (f" ({p.agency_name})" if p.agency_name else ""))
    if p.amenities:
        lines.append(f"  시설:     {', '.join(p.amenities[:8])}")
    lines += ["", f"  [link={p.url}][cyan underline]{p.url}[/cyan underline][/link]"]

    console.print(Panel(
        "\n".join(lines),
        title="[bold]매물 상세[/bold]",
        border_style="green",
        padding=(1, 2),
    ))
