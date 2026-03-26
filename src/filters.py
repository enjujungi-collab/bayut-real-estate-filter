from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich import print as rprint
from .models import SearchFilters
from . import api

console = Console()

CATEGORIES = {
    "1": "apartments",
    "2": "villas",
    "3": "townhouses",
    "4": "penthouses",
    "5": "studios",
    "6": "offices",
    "7": "retail",
}

SORT_OPTIONS = {
    "1": ("popular",       "인기순"),
    "2": ("latest",        "최신순"),
    "3": ("lowest_price",  "가격 낮은순"),
    "4": ("highest_price", "가격 높은순"),
    "5": ("verified",      "인증 매물 우선"),
}


def collect_filters() -> SearchFilters:
    filters = SearchFilters()

    console.rule("[bold cyan]Bayut 매물 필터 설정[/bold cyan]")

    # 1. 목적
    purpose_input = Prompt.ask(
        "\n[bold]매매 또는 임대?[/bold]",
        choices=["매매", "임대"],
        default="매매",
    )
    filters.purpose = "for-sale" if purpose_input == "매매" else "for-rent"

    # 2. 카테고리
    console.print("\n[bold]부동산 유형[/bold]")
    for k, v in CATEGORIES.items():
        console.print(f"  {k}. {v}")
    cat_input = Prompt.ask("선택 (번호, 기본값=1)", default="1")
    filters.categories = [CATEGORIES.get(cat_input.strip(), "apartments")]

    # 3. 위치
    while True:
        loc_query = Prompt.ask("\n[bold]위치 검색[/bold] (예: Dubai Marina, JBR, Abu Dhabi)")
        try:
            results = api.search_locations(loc_query)
        except Exception as e:
            console.print(f"[red]위치 검색 오류: {e}[/red]")
            continue

        if not results:
            console.print("[yellow]결과 없음. 다시 시도해주세요.[/yellow]")
            continue

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", width=4)
        table.add_column("이름", min_width=20)
        table.add_column("유형", min_width=12)

        for i, loc in enumerate(results[:8], 1):
            table.add_row(
                str(i),
                loc.get("name_en") or loc.get("name") or "-",
                loc.get("level") or loc.get("type") or "-",
            )
        console.print(table)

        choice = Prompt.ask("번호 선택 (0=다시 검색)", default="1")
        if choice == "0":
            continue

        idx = int(choice) - 1
        if 0 <= idx < len(results[:8]):
            selected = results[idx]
            filters.locations_ids = [selected["id"]]
            filters.location_name = selected.get("name_en") or selected.get("name") or ""
            console.print(f"[green]✓ 선택: {filters.location_name}[/green]")
            break
        else:
            console.print("[yellow]올바른 번호를 입력해주세요.[/yellow]")

    # 4. 가격 범위
    console.print("\n[bold]가격 범위[/bold] (AED, 0 = 제한없음)")
    price_min_input = Prompt.ask("최저 가격 (예: 500000)", default="0")
    price_max_input = Prompt.ask("최고 가격 (예: 2000000)", default="0")
    filters.price_min = int(price_min_input) or None
    filters.price_max = int(price_max_input) or None

    # 5. 방 개수
    console.print("\n[bold]방 개수[/bold] (복수 선택 가능, 예: 1,2,3 / 0=Studio / Enter=상관없음)")
    rooms_input = Prompt.ask("방 개수", default="")
    if rooms_input.strip():
        rooms = []
        for r in rooms_input.split(","):
            r = r.strip()
            if r.isdigit():
                rooms.append(int(r))
        filters.rooms = rooms if rooms else None

    # 6. 면적 범위
    console.print("\n[bold]면적 범위[/bold] (sqft, 0 = 제한없음)")
    area_min_input = Prompt.ask("최소 면적", default="0")
    area_max_input = Prompt.ask("최대 면적", default="0")
    filters.area_min = float(area_min_input) or None
    filters.area_max = float(area_max_input) or None

    # 7. 완공 여부
    completed_input = Prompt.ask(
        "\n[bold]완공 여부[/bold]",
        choices=["완공", "미완공", "상관없음"],
        default="상관없음",
    )
    if completed_input == "완공":
        filters.is_completed = True
    elif completed_input == "미완공":
        filters.is_completed = False

    # 8. 정렬
    console.print("\n[bold]정렬 기준[/bold]")
    for k, (_, label) in SORT_OPTIONS.items():
        console.print(f"  {k}. {label}")
    sort_input = Prompt.ask("선택", default="1")
    filters.sort_by = SORT_OPTIONS.get(sort_input, SORT_OPTIONS["1"])[0]

    return filters
