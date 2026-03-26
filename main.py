#!/usr/bin/env python3
"""
Bayut 부동산 필터 CLI
실행: python main.py
"""
import sys
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich import print as rprint

console = Console()


def main():
    console.print("\n[bold magenta]🏠 Bayut 부동산 필터 앱[/bold magenta]")
    console.print("[dim]UAE(두바이 등) 매물을 조건에 맞게 검색합니다.[/dim]\n")

    # .env 로드 확인
    try:
        from src import api
        api._get_headers()  # API key 유효성 체크
    except ValueError as e:
        console.print(f"[red bold]설정 오류:[/red bold] {e}")
        sys.exit(1)

    from src.filters import collect_filters
    from src.display import print_results, print_property_detail

    page = 0
    properties = []
    filters = None

    while True:
        if filters is None or page == 0:
            try:
                filters = collect_filters()
            except KeyboardInterrupt:
                console.print("\n[dim]종료합니다.[/dim]")
                sys.exit(0)

        console.print("\n[dim]매물 검색 중...[/dim]")
        try:
            from src import api as bayut_api
            properties, total = bayut_api.search_properties(filters, page=page)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
        except RuntimeError as e:
            console.print(f"[yellow]{e}[/yellow]")
            input("Enter를 눌러 계속...")
            continue
        except Exception as e:
            console.print(f"[red]API 오류: {e}[/red]")
            sys.exit(1)

        print_results(properties, total, page, filters)

        if not properties:
            if Confirm.ask("새로 검색하시겠습니까?", default=True):
                filters = None
                page = 0
                continue
            break

        # 사용자 액션 선택
        console.print("[bold]액션 선택:[/bold]")
        console.print("  [cyan]번호[/cyan]  매물 상세보기 (예: 1, 3)")
        console.print("  [cyan]pdf[/cyan]   PDF 리포트 저장")
        console.print("  [cyan]n[/cyan]     다음 페이지")
        if page > 0:
            console.print("  [cyan]p[/cyan]     이전 페이지")
        console.print("  [cyan]r[/cyan]     새로 검색")
        console.print("  [cyan]q[/cyan]     종료")

        action = Prompt.ask("\n선택", default="q").strip().lower()

        if action == "q":
            console.print("\n[dim]종료합니다. 안녕히 가세요![/dim]\n")
            break
        elif action == "pdf":
            _export_pdf(console, properties, filters)
        elif action == "n":
            page += 1
        elif action == "p" and page > 0:
            page -= 1
        elif action == "r":
            filters = None
            page = 0
        elif action.isdigit():
            idx = int(action) - 1
            if 0 <= idx < len(properties):
                prop = properties[idx]
                console.print("\n[dim]상세 정보 조회 중...[/dim]")
                try:
                    detail = bayut_api.get_property_detail(prop.id)
                    print_property_detail(detail or prop)
                except Exception:
                    print_property_detail(prop)
                input("\nEnter를 눌러 목록으로 돌아가기...")
            else:
                console.print("[yellow]올바른 번호를 입력해주세요.[/yellow]")
        else:
            console.print("[yellow]올바른 명령어를 입력해주세요.[/yellow]")


def _export_pdf(console, properties, filters):
    from src.models import SearchFilters
    from src.pdf_export import generate_pdf

    console.print("\n[bold]PDF에 포함할 매물 선택[/bold]")
    console.print(f"  현재 {len(properties)}개 매물 표시 중")
    console.print("  [dim]예: 1,3,5  /  Enter = 전체 포함[/dim]")

    sel_input = Prompt.ask("번호 입력", default="").strip()

    if sel_input:
        selected = []
        for s in sel_input.split(","):
            s = s.strip()
            if s.isdigit():
                idx = int(s) - 1
                if 0 <= idx < len(properties):
                    selected.append(properties[idx])
        if not selected:
            console.print("[yellow]올바른 번호가 없습니다. 전체 매물로 진행합니다.[/yellow]")
            selected = properties
    else:
        selected = properties

    console.print(f"\n[dim]{len(selected)}개 매물로 PDF 생성 중...[/dim]")
    try:
        path = generate_pdf(selected, filters)
        console.print(f"\n[bold green]✓ PDF 저장 완료![/bold green]")
        console.print(f"  [cyan]{path}[/cyan]")
        # macOS: Finder에서 바로 열기
        import subprocess
        subprocess.Popen(["open", path])
    except Exception as e:
        console.print(f"[red]PDF 생성 오류: {e}[/red]")

    input("\nEnter를 눌러 계속...")


if __name__ == "__main__":
    main()
