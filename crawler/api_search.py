"""네이버 쇼핑 검색 Open API 기반 순위 조회 모듈."""

from __future__ import annotations

import json
import math
import os
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# 네이버 공식 쇼핑 검색 Open API URL입니다.
API_URL = "https://openapi.naver.com/v1/search/shop.json"

# 한 번의 API 호출에서 가져올 수 있는 최대 개수입니다. 문서상 최댓값은 100입니다.
DEFAULT_DISPLAY = 100

# API가 허용하는 시작 위치 최댓값입니다. start=1,101,...,901 식으로 최대 1000위까지 확인합니다.
MAX_START = 1000

# 목록 조회와 MID 조회가 공통으로 확인할 기본 최대 순위입니다.
# display=100 기준 기본 4회 요청으로 400위까지 확인합니다.
DEFAULT_MAX_RANK = 400

# 검색 정렬 기본값입니다. sim은 네이버 문서 기준 정확도순입니다.
DEFAULT_SORT = "sim"

# 네이버 API의 productType 값을 사람이 보기 쉬운 값으로 풀어둔 표입니다.
PRODUCT_TYPE_MAP = {
    "1": {"group": "일반상품", "kind": "catalog", "name": "가격비교 상품"},
    "2": {"group": "일반상품", "kind": "single", "name": "가격비교 비매칭 일반상품"},
    "3": {"group": "일반상품", "kind": "single_matched", "name": "가격비교 매칭 일반상품"},
    "4": {"group": "중고상품", "kind": "catalog", "name": "중고 가격비교 상품"},
    "5": {"group": "중고상품", "kind": "single", "name": "중고 가격비교 비매칭 일반상품"},
    "6": {"group": "중고상품", "kind": "single_matched", "name": "중고 가격비교 매칭 일반상품"},
    "7": {"group": "단종상품", "kind": "catalog", "name": "단종 가격비교 상품"},
    "8": {"group": "단종상품", "kind": "single", "name": "단종 가격비교 비매칭 일반상품"},
    "9": {"group": "단종상품", "kind": "single_matched", "name": "단종 가격비교 매칭 일반상품"},
    "10": {"group": "판매예정상품", "kind": "catalog", "name": "판매예정 가격비교 상품"},
    "11": {"group": "판매예정상품", "kind": "single", "name": "판매예정 가격비교 비매칭 일반상품"},
    "12": {"group": "판매예정상품", "kind": "single_matched", "name": "판매예정 가격비교 매칭 일반상품"},
}


class ApiSearchError(Exception):
    """네이버 쇼핑 API 조회 중 발생한 오류입니다."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "api_search_error",
        status: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.body = body


def clean_title(value: str | None) -> str:
    """API title에 포함되는 <b> 태그와 HTML entity를 제거합니다."""
    text = unescape(value or "")
    text = re.sub(r"</?b>", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def parse_int(value: Any) -> int | None:
    """문자열 숫자를 int로 바꿉니다. 빈 값은 None으로 둡니다."""
    text = "" if value is None else str(value)
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def read_dotenv() -> dict[str, str]:
    """간단한 .env 파일을 읽습니다."""
    result: dict[str, str] = {}
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def get_credentials(client_id: str | None = None, client_secret: str | None = None) -> tuple[str, str]:
    """옵션, 환경변수, .env 순서로 네이버 API 키를 가져옵니다."""
    dotenv = read_dotenv()
    resolved_id = client_id or os.getenv("NAVER_CLIENT_ID") or dotenv.get("NAVER_CLIENT_ID")
    resolved_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET") or dotenv.get("NAVER_CLIENT_SECRET")

    if not resolved_id or not resolved_secret:
        raise ApiSearchError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 값이 필요합니다.",
            code="missing_credentials",
        )
    return resolved_id, resolved_secret


def validate_params(keyword: str, display: int, start: int, sort: str, max_rank: int) -> None:
    """네이버 문서 제한에 맞게 요청 파라미터를 검사합니다."""
    if not keyword or not keyword.strip():
        raise ApiSearchError("검색 키워드가 필요합니다.", code="invalid_keyword")
    if not 1 <= display <= DEFAULT_DISPLAY:
        raise ApiSearchError("display는 1~100 사이만 가능합니다.", code="invalid_display")
    if not 1 <= start <= MAX_START:
        raise ApiSearchError("start는 1~1000 사이만 가능합니다.", code="invalid_start")
    if not 1 <= max_rank <= MAX_START:
        raise ApiSearchError("max_rank는 1~1000 사이만 가능합니다.", code="invalid_max_rank")
    if sort not in {"sim", "date", "asc", "dsc"}:
        raise ApiSearchError("sort는 sim/date/asc/dsc 중 하나여야 합니다.", code="invalid_sort")


def iter_request_starts(max_rank: int, display: int) -> list[int]:
    """확인할 최대 순위와 display를 기준으로 API start 목록을 만듭니다."""
    request_count = math.ceil(max_rank / display)
    return [index * display + 1 for index in range(request_count) if index * display + 1 <= MAX_START]


def fetch_page(
    *,
    keyword: str,
    client_id: str,
    client_secret: str,
    display: int = DEFAULT_DISPLAY,
    start: int = 1,
    sort: str = DEFAULT_SORT,
    timeout: int = 15,
) -> dict[str, Any]:
    """네이버 쇼핑 검색 API 한 페이지를 호출합니다."""
    validate_params(keyword=keyword, display=display, start=start, sort=sort, max_rank=start)

    params = {
        "query": keyword,
        "display": display,
        "start": start,
        "sort": sort,
    }
    request = Request(f"{API_URL}?{urlencode(params)}")
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiSearchError(
            f"네이버 API HTTP 오류: {exc.code}",
            code="http_error",
            status=exc.code,
            body=body,
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ApiSearchError(f"네이버 API 요청 실패: {exc}", code="request_failed") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiSearchError("네이버 API 응답 JSON 파싱 실패", code="invalid_json", body=body) from exc


def normalize_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    """네이버 API item을 내부 순위 결과 형식으로 변환합니다."""
    product_type = str(item.get("productType") or "")
    type_info = PRODUCT_TYPE_MAP.get(
        product_type,
        {"group": "알 수 없음", "kind": "unknown", "name": f"알 수 없는 타입({product_type})"},
    )
    product_id = str(item.get("productId") or "")

    return {
        "rank": rank,
        "title": clean_title(item.get("title")),
        "mid": product_id,
        "product_id": product_id,
        "product_type": product_type,
        "product_type_group": type_info["group"],
        "product_type_name": type_info["name"],
        "product_kind": type_info["kind"],
        "mall_name": item.get("mallName") or "",
        "price": parse_int(item.get("lprice")),
        "high_price": parse_int(item.get("hprice")),
        "brand": item.get("brand") or "",
        "maker": item.get("maker") or "",
        "category1": item.get("category1") or "",
        "category2": item.get("category2") or "",
        "category3": item.get("category3") or "",
        "category4": item.get("category4") or "",
        "image": item.get("image") or "",
        "url": item.get("link") or "",
        "is_ad": False,
    }


def collect_products(
    *,
    keyword: str,
    max_rank: int = DEFAULT_MAX_RANK,
    target_mid: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    sort: str = DEFAULT_SORT,
    display: int = DEFAULT_DISPLAY,
    timeout: int = 15,
    **_: Any,
) -> dict[str, Any]:
    """네이버 쇼핑 검색 API로 목록 조회 또는 MID 순위 조회를 수행합니다."""
    items: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    normalized_target_mid = str(target_mid).strip() if target_mid else None

    try:
        resolved_id, resolved_secret = get_credentials(client_id=client_id, client_secret=client_secret)
        validate_params(keyword=keyword, display=display, start=1, sort=sort, max_rank=max_rank)
        starts = iter_request_starts(max_rank=max_rank, display=display)

        for page_index, start in enumerate(starts, start=1):
            data = fetch_page(
                keyword=keyword,
                client_id=resolved_id,
                client_secret=resolved_secret,
                display=display,
                start=start,
                sort=sort,
                timeout=timeout,
            )
            raw_items = data.get("items") or []
            page_info = {
                "page": page_index,
                "start": data.get("start"),
                "display": data.get("display"),
                "total": data.get("total"),
                "ok": True,
                "reason": None,
                "product_count": len(raw_items),
            }

            for offset, raw_item in enumerate(raw_items):
                rank = start + offset
                if rank > max_rank:
                    break

                product = normalize_item(raw_item, rank=rank)
                if normalized_target_mid:
                    if product["mid"] != normalized_target_mid:
                        continue
                    return {
                        "state": True,
                        "data": {
                            "keyword": keyword,
                            "target_mid": normalized_target_mid,
                            "found": True,
                            "item": product,
                            "checked_count": rank,
                        },
                    }

                items.append(product)

            pages.append(page_info)

            if len(raw_items) < display:
                break

    except ApiSearchError as exc:
        return {
            "state": False,
            "data": {
                "keyword": keyword,
                "target_mid": normalized_target_mid,
                "found": False if normalized_target_mid else None,
                "item": None if normalized_target_mid else None,
                "items": [] if normalized_target_mid else items,
                "pages": [] if normalized_target_mid else pages,
            },
            "error": str(exc),
            "error_code": exc.code,
            "status": exc.status,
            "body": exc.body,
        }

    if normalized_target_mid:
        return {
            "state": False,
            "data": {
                "keyword": keyword,
                "target_mid": normalized_target_mid,
                "found": False,
                "item": None,
                "checked_count": sum(int(page.get("product_count") or 0) for page in pages),
            },
            "error": f"{max_rank}위 안에서 MID {normalized_target_mid} 상품을 찾지 못했습니다.",
        }

    return {
        "state": bool(items),
        "data": {
            "keyword": keyword,
            "target_mid": None,
            "found": None,
            "items": items,
            "pages": pages,
            "api": {
                "sort": sort,
                "display": display,
                "max_rank": max_rank,
                "request_count": len(pages),
            },
        },
        "error": None if items else "상품을 수집하지 못했습니다.",
    }
