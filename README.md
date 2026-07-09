# n_shopping_rank

네이버쇼핑 Open API 기반 순위 조회 모듈입니다.


## 구조

- `cli.py`: Open API 기반 메인 CLI
- `crawler/api_search.py`: Open API 조회 엔진

## API 호출 기준

- `display`: API 1회 요청 결과 개수입니다. 기본값은 100이고 최대값도 100입니다.
- `--max-rank`: 확인할 최대 순위입니다. 기본값은 400위, 최대값은 1000위입니다.
- 요청 횟수는 `ceil(max_rank / display)`로 계산합니다.
- 기본값 기준 `display=100`, `max_rank=400`이라 4회 요청합니다.
- `--list`와 `--mid` 모두 같은 `--max-rank` 범위 안에서만 조회합니다.
- API 응답의 `productId`를 MID로 사용합니다.

예시:

```text
--max-rank 400  -> start=1,101,201,301       -> 최대 4회 요청
--max-rank 1000 -> start=1,101,...,901       -> 최대 10회 요청
--display 50 --max-rank 200 -> start=1,51,101,151 -> 최대 4회 요청
```

## productType

- `1`: 가격비교 상품, `product_kind=catalog`
- `2`: 가격비교 비매칭 일반상품, `product_kind=single`
- `3`: 가격비교 매칭 일반상품, `product_kind=single_matched`
- `4~6`: 중고상품
- `7~9`: 단종상품
- `10~12`: 판매예정상품

## 환경 변수

```env
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here
```

명령줄에서 `--client-id`, `--client-secret`으로 직접 넘겨도 됩니다.

## 실행

목록 조회:

```bash
python cli.py --list --keyword "우산"
```

특정 MID 순위 찾기:

```bash
python cli.py --keyword "우산" --mid 12345678901
```

1000위까지 찾기:

```bash
python cli.py --keyword "우산" --mid 12345678901 --max-rank 1000
```

키를 명령줄에서 직접 전달:

```bash
python cli.py --list --keyword "우산" --client-id "CLIENT_ID" --client-secret "CLIENT_SECRET"
```

JSON 출력:

```bash
python cli.py --list --keyword "우산" --json
```

파일 저장:

```bash
python cli.py --list --keyword "우산" --json --output result.txt
```

## 다른 프로젝트에서 가져다 쓰기

웹서버나 다른 프로젝트에서는 CLI를 실행하기보다 `crawler.api_search`를 직접 import해서 쓰는 방식을 권장합니다.

예시 구조:

```text
web/
  api/
    n_shopping_rank/
      crawler/
        api_search.py
      cli.py
```

같은 프로젝트 안에 복사한 경우:

```python
from n_shopping_rank.crawler import api_search

result = api_search.collect_products(
    keyword="우산",
    target_mid="87866577636",
    max_rank=400,
)

if result["state"] and result["data"]["found"]:
    rank = result["data"]["item"]["rank"]
    title = result["data"]["item"]["title"]
```

목록 조회:

```python
from n_shopping_rank.crawler import api_search

result = api_search.collect_products(
    keyword="우산",
    max_rank=400,
)

items = result["data"]["items"] if result["state"] else []
```

FastAPI 예시:

```python
from fastapi import APIRouter
from n_shopping_rank.crawler import api_search

router = APIRouter()

@router.get("/shopping-rank")
def shopping_rank(keyword: str, mid: str, max_rank: int = 400):
    return api_search.collect_products(
        keyword=keyword,
        target_mid=mid,
        max_rank=max_rank,
    )
```

환경변수 또는 `.env`에 아래 값이 있으면 코드에서 키를 따로 넘기지 않아도 됩니다.

```env
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here
```

키를 직접 넘기는 경우:

```python
result = api_search.collect_products(
    keyword="우산",
    target_mid="87866577636",
    max_rank=400,
    client_id="CLIENT_ID",
    client_secret="CLIENT_SECRET",
)
```
