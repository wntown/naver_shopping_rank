#!/usr/bin/env python
# coding: utf-8
"""네이버쇼핑 Open API 기반 순위 조회 CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crawler import api_search


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """명령줄 옵션을 읽습니다."""
    parser = argparse.ArgumentParser(description="네이버쇼핑 Open API 순위 조회")
    parser.add_argument("--keyword", required=True, help="검색 키워드")
    parser.add_argument("--list", action="store_true", help="키워드의 상품 순위 목록을 출력")
    parser.add_argument("--mid", help="찾을 네이버쇼핑 MID 값")
    parser.add_argument("--max-rank", type=int, default=400, help="확인할 최대 순위. 기본 400위, 최대 1000위")
    parser.add_argument("--display", type=int, default=100, help="API 한 번에 가져올 개수. 기본 100, 최대 100")
    parser.add_argument(
        "--sort",
        choices=["sim", "date", "asc", "dsc"],
        default="sim",
        help="정렬 방식. sim=정확도순, date=날짜순, asc=가격오름차순, dsc=가격내림차순",
    )
    parser.add_argument("--client-id", help="네이버 API Client ID. 없으면 환경변수/.env에서 읽음")
    parser.add_argument("--client-secret", help="네이버 API Client Secret. 없으면 환경변수/.env에서 읽음")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    parser.add_argument("--output", help="출력 결과 저장 경로")

    args = parser.parse_args()
    if not args.list and not args.mid:
        parser.error("조회 방식이 필요합니다. 목록 조회는 --list, MID 순위 조회는 --mid 값을 입력하세요.")
    return args


def render_text(result: dict) -> str:
    """수집 결과를 사람이 읽기 쉬운 텍스트로 만듭니다."""
    data = result.get("data") or {}
    item = data.get("item")
    items = [item] if item else data.get("items") or []
    lines = [
        "모듈: api_search",
        f"검색 키워드: {data.get('keyword')}",
    ]
    if data.get("target_mid"):
        lines.append(f"조회 MID: {data.get('target_mid')}")
    lines.extend([f"수집 개수: {len(items)}", ""])

    if result.get("error"):
        lines.append(f"오류: {result.get('error')}")
        if result.get("error_code"):
            lines.append(f"오류 코드: {result.get('error_code')}")
        if result.get("status"):
            lines.append(f"HTTP 상태: {result.get('status')}")
        lines.append("")

    api_info = data.get("api")
    if api_info:
        lines.append(
            f"API: sort={api_info.get('sort')} / display={api_info.get('display')} "
            f"/ max_rank={api_info.get('max_rank')} / request_count={api_info.get('request_count')}"
        )
        lines.append("")

    for page_info in data.get("pages") or []:
        lines.append(
            f"API 페이지 {page_info.get('page')}: start={page_info.get('start')} "
            f"/ display={page_info.get('display')} / count={page_info.get('product_count')} "
            f"/ total={page_info.get('total')} / reason={page_info.get('reason')}"
        )
    if data.get("pages"):
        lines.append("")

    for item in items:
        lines.append(f"{item.get('rank')}위 - {item.get('title')}")
        lines.append(f"  MID: {item.get('mid')} / 구분: {item.get('product_kind')}")
        lines.append(f"  productType: {item.get('product_type')} / {item.get('product_type_name')}")
        if item.get("mall_name"):
            lines.append(f"  판매처: {item.get('mall_name')}")
        if item.get("price"):
            lines.append(f"  가격: {item.get('price')}")
        if item.get("brand"):
            lines.append(f"  브랜드: {item.get('brand')}")
        if item.get("url"):
            lines.append(f"  URL: {item.get('url')}")
        lines.append("")
    return "\n".join(lines).rstrip()


def emit(text: str, output_path: str | None) -> None:
    """결과를 콘솔로 출력하거나 파일로 저장합니다."""
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8-sig")
        print(f"저장 완료: {output_path}")
        return
    print(text)


def main() -> int:
    """CLI 진입점입니다."""
    args = parse_args()
    result = api_search.collect_products(
        keyword=args.keyword,
        max_rank=args.max_rank,
        target_mid=args.mid,
        client_id=args.client_id,
        client_secret=args.client_secret,
        sort=args.sort,
        display=args.display,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_text(result)
    emit(text, args.output)
    return 0 if result.get("state") else 1


if __name__ == "__main__":
    raise SystemExit(main())
