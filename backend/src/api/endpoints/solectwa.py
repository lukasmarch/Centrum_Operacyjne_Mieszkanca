"""
Ogłoszenia sołtysów: zdjęcie pisma → odczyt → moderacja → artykuł.

Cel nadrzędny: ogłoszenie sołtysa ma zobaczyć więcej osób niż na jego profilu
FB. Warunek: sołtys nie zmienia nawyku — zdjęcie pisma i „wyślij".

Przebieg:
  1. `POST /posts` — do `MAX_IMAGES` zdjęć + opcjonalne zdanie od sołtysa.
     Zdjęcia lądują w `PRIVATE_DIR` (NIE w publicznym `/uploads`), status
     `processing`, odczyt rusza w tle.
  2. `ScanReader` (gpt-4o) → przedruk z wyciętymi danymi osób prywatnych,
     tytuł, podsumowanie, termin. Status `pending` + dzwonek do redakcji.
  3. Redakcja widzi zdjęcie obok przedruku, może poprawić tekst,
     zatwierdza albo odrzuca. Sołtys dostaje maila w obu przypadkach.
  4. Zatwierdzenie tworzy wpis w `articles` (źródło `SOURCE_NAME`), więc
     ogłoszenie wchodzi do feedu, briefingu, newslettera, kalendarza i RAG
     tą samą drogą co reszta materiału — bez osobnej ścieżki.
  5. Po publikacji (E7, 12.10.2026): redakcja POPRAWIA albo ODWOŁUJE ogłoszenie,
     zawsze z powodem; każda postać zostaje w `solectwo_post_versions`. Sołtys
     prosi o to ze swojego panelu (`solectwo_post_requests`), publikuje redakcja.
     Odwołanie nie kasuje wiersza — `withdrawn_at` na artykule i wydarzeniu
     wyłącza go w bramkach `feed_policy` (feed, briefing, newsletter, push,
     agenci, kalendarz). Proces decyzyjny (prośba, powód, historia wersji) jest
     sprawą sołtysa i redakcji: mieszkaniec widzi poprawioną treść bez śladu
     zmiany, a pod linkiem odwołanego ogłoszenia — wyłącznie „nieaktualne”.

AI Act art. 50: podsumowanie jest oznaczone na stronie jako przygotowane
automatycznie i sprawdzone przez redakcję (front, `SolectwoPostPage`).
"""
from html import escape as html_escape
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlmodel import select

from src.auth.dependencies import get_admin_user, get_current_active_user
from src.config import settings
from src.database.connection import async_session
from src.database.schema import (
    Article, Event, SolectwoPost, SolectwoPostRequest, SolectwoPostVersion, Source, User,
)
from src.services import roles as role_service
from src.services.time_span import is_all_day, to_local, to_utc
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger

logger = setup_logger("Solectwa")

router = APIRouter(prefix="/api/solectwa", tags=["solectwa"])

SOURCE_NAME = "RybnoLive - Sołectwa"

MAX_IMAGES = 5
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
NOTE_MAX = 500

# Zdjęcie oryginału znika tyle dni po decyzji redakcji (publikacja albo
# odrzucenie). Przedruk zostaje — to on jest publikacją, zdjęcie było
# materiałem roboczym. Obietnica stoi w mailu dla sołtysa.
IMAGE_RETENTION_DAYS = 30

# Poza `/app/uploads` — tamten katalog montuje FastAPI (`/uploads`) i Caddy
# (api.rybnolive.pl/uploads/*), czyli wszystko w nim jest publiczne.
# Na produkcji osobny wolumen `private_uploads` (docker-compose.prod.yml).
PRIVATE_DIR = Path(__file__).parent.parent.parent.parent / "private_uploads" / "solectwa"

PROCESSING = "processing"
PENDING = "pending"
PUBLISHED = "published"
REJECTED = "rejected"
FAILED = "failed"
WITHDRAWN = "withdrawn"

# Rodzaje wersji w `solectwo_post_versions` i próśb sołtysa
V_PUBLICATION = "publication"
V_CORRECTION = "correction"
V_WITHDRAWAL = "withdrawal"
REQUEST_KINDS = (V_CORRECTION, V_WITHDRAWAL)
REQUEST_MAX = 1000


def post_url(post_id: int) -> str:
    return f"{settings.APP_URL.rstrip('/')}/ogloszenie?id={post_id}"


# ── Odczyt w tle ─────────────────────────────────────────────────────────

async def process_post(post_id: int) -> None:
    """Odczyt pisma. Własna sesja — działa po zakończeniu żądania."""
    from src.ai.scan_reader import ScanReader

    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            return
        try:
            images = [(PRIVATE_DIR / name).read_bytes() for name in post.image_files]
            result, tokens_in, tokens_out = await ScanReader().read(images, note=post.note)
            log_api_cost(
                session, model="gpt-4o", tokens_input=tokens_in, tokens_output=tokens_out,
                endpoint="solectwa:scan", user_id=post.user_id,
            )
            post.title = result.title or None
            post.summary = result.summary or None
            post.transcript = result.transcript or None
            post.doc_type = result.doc_type
            post.event_at = result.event_at
            post.event_until = result.event_until
            post.personal_data = result.personal_data
            post.illegible = result.illegible
            # Nie-pismo też idzie do redakcji: sołtys mógł wysłać plakat,
            # który model uznał za „zdjęcie". Decyzję podejmuje człowiek.
            post.ai_error = None if result.is_document else "Na zdjęciu nie rozpoznano pisma"
            post.status = PENDING
        except Exception as exc:  # noqa: BLE001 — błąd zostaje w rekordzie, nie ginie w logu
            logger.error(f"Odczyt ogłoszenia {post_id} nie powiódł się: {exc}", exc_info=True)
            post.status = FAILED
            post.ai_error = str(exc)[:500]
        session.add(post)
        await session.commit()
        await session.refresh(post)

    await _notify_admin(post)


async def _notify_admin(post: SolectwoPost) -> None:
    """Dzwonek do redakcji — bez niego moderacja jest tylko nazwą (lekcja
    Zgłoszeń 24 z 22.08.2026)."""
    try:
        from src.newsletter.email_service import EmailService

        admin_email = settings.ADMIN_ALERT_EMAIL
        if not admin_email:
            logger.warning("Nowe ogłoszenie sołectwa bez dzwonka — brak ADMIN_ALERT_EMAIL")
            return
        # Tytuł, streszczenie i dane osobowe pochodzą z odczytu zdjęcia przez model —
        # tekst z cudzego pisma nie może stać się HTML-em w skrzynce redakcji
        e = html_escape  # import pod inną nazwą: zmienna lokalna `html` niżej zasłania moduł
        warning = (
            f"<p style='color:#b91c1c'>⚠️ {e(post.ai_error)}</p>" if post.ai_error else ""
        )
        pii = (
            "<p>Wykryte dane osobowe: " + e(", ".join(post.personal_data)) + "</p>"
            if post.personal_data else ""
        )
        html = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1d4ed8;margin-bottom:4px">Ogłoszenie sołectwa czeka na moderację</h2>
          <p style="color:#64748b;font-size:13px;margin-top:0">{e(post.signed_as or '')}</p>
          <div style="background:#f1f5f9;padding:16px;border-radius:8px">
            <strong>{e(post.title or '(bez tytułu)')}</strong><br>{e(post.summary or '')}
          </div>
          {warning}{pii}
          <p><a href="{settings.APP_URL.rstrip('/')}/profil?zakladka=solectwa-admin">
            Przejdź do moderacji →</a></p>
        </div>
        """
        await EmailService().send_email(
            to_email=admin_email,
            subject=f"Ogłoszenie do moderacji: {post.title or post.signed_as}",
            html_content=html,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Dzwonek nie zadzwonił dla ogłoszenia {post.id}: {exc}")


# ── Sołtys ───────────────────────────────────────────────────────────────

class PostOut(BaseModel):
    id: int
    solectwo: str
    signed_as: str
    status: str
    title: Optional[str]
    summary: Optional[str]
    created_at: datetime
    published_at: Optional[datetime]
    reject_reason: Optional[str]
    url: Optional[str]
    version: int = 0
    corrected_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    withdraw_reason: Optional[str] = None
    open_requests: List["RequestOut"] = []


class RequestOut(BaseModel):
    id: int
    kind: str
    message: str
    status: str
    created_at: datetime


PostOut.model_rebuild()


def _post_out(post: SolectwoPost, requests: Optional[list] = None) -> PostOut:
    return PostOut(
        id=post.id, solectwo=post.solectwo, signed_as=post.signed_as,
        status=post.status, title=post.title, summary=post.summary,
        created_at=post.created_at, published_at=post.published_at,
        reject_reason=post.reject_reason,
        # Odwołane też ma stronę — mówi, że ogłoszenie odwołano
        url=post_url(post.id) if post.status in (PUBLISHED, WITHDRAWN) else None,
        version=post.version or 0, corrected_at=post.corrected_at,
        withdrawn_at=post.withdrawn_at, withdraw_reason=post.withdraw_reason,
        open_requests=[
            RequestOut(id=r.id, kind=r.kind, message=r.message, status=r.status, created_at=r.created_at)
            for r in (requests or [])
        ],
    )


async def _open_requests(session, post_ids: list[int]) -> dict[int, list]:
    if not post_ids:
        return {}
    rows = (await session.execute(
        select(SolectwoPostRequest)
        .where(SolectwoPostRequest.post_id.in_(post_ids), SolectwoPostRequest.status == "open")
        .order_by(SolectwoPostRequest.created_at)
    )).scalars().all()
    grouped: dict[int, list] = {}
    for r in rows:
        grouped.setdefault(r.post_id, []).append(r)
    return grouped


def _store_image(data: bytes) -> str:
    from src.ai.scan_reader import shrink

    try:
        jpeg, _ = shrink(data)
    except Exception:  # noqa: BLE001 — Pillow nie rozpozna formatu
        raise HTTPException(
            status_code=400,
            detail="Nie udało się odczytać zdjęcia. Wyślij plik JPG lub PNG.",
        )
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (PRIVATE_DIR / name).write_bytes(jpeg)
    return name


@router.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    note: Optional[str] = Form(None),
    role_id: Optional[int] = Form(None),
    user=Depends(get_current_active_user),
):
    async with async_session() as session:
        account = await session.get(User, user.id)
        allowed = await role_service.role_with_permission(
            session, account, role_service.PERM_SOLECTWO_POST,
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Ogłoszenia dodaje sołtys z potwierdzoną rolą")
        if role_id is not None:
            allowed = [r for r in allowed if r.id == role_id]
            if not allowed:
                raise HTTPException(status_code=403, detail="Ta rola nie należy do Twojego konta")
        role = allowed[0]

        files = [f for f in images if f and f.filename]
        if not files:
            raise HTTPException(status_code=400, detail="Dodaj przynajmniej jedno zdjęcie")
        if len(files) > MAX_IMAGES:
            raise HTTPException(status_code=400, detail=f"Najwyżej {MAX_IMAGES} zdjęć na ogłoszenie")

        stored: list[str] = []
        for upload in files:
            if upload.content_type and upload.content_type not in ALLOWED_TYPES:
                raise HTTPException(status_code=400, detail="Dozwolone są zdjęcia (JPG, PNG, WEBP)")
            data = await upload.read()
            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail="Zdjęcie jest za duże (limit 10 MB)")
            stored.append(_store_image(data))

        post = SolectwoPost(
            user_id=account.id,
            role_id=role.id,
            solectwo=role.scope,
            signed_as=role_service.signed_as(role.role, role.scope),
            status=PROCESSING,
            note=(note or "").strip()[:NOTE_MAX] or None,
            image_files=stored,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

    background_tasks.add_task(process_post, post.id)
    logger.info(f"Nowe ogłoszenie {post.id} od {post.signed_as} ({len(stored)} zdj.)")
    return _post_out(post)


@router.get("/posts/mine", response_model=List[PostOut])
async def my_posts(user=Depends(get_current_active_user)):
    async with async_session() as session:
        rows = (await session.execute(
            select(SolectwoPost)
            .where(SolectwoPost.user_id == user.id)
            .order_by(SolectwoPost.created_at.desc())
            .limit(50)
        )).scalars().all()
        requests = await _open_requests(session, [p.id for p in rows])
    return [_post_out(p, requests.get(p.id)) for p in rows]


class RequestIn(BaseModel):
    kind: Literal["correction", "withdrawal"]
    message: str = Field(min_length=5, max_length=REQUEST_MAX)


@router.post("/posts/{post_id}/requests", response_model=PostOut, status_code=201)
async def request_change(post_id: int, body: RequestIn, user=Depends(get_current_active_user)):
    """Sołtys prosi o korektę albo odwołanie SWOJEGO opublikowanego ogłoszenia.
    Treść niczego sama nie zmienia — decyduje i publikuje redakcja."""
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post or post.user_id != user.id:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        account = await session.get(User, user.id)
        if not await role_service.role_with_permission(session, account, role_service.PERM_SOLECTWO_POST):
            raise HTTPException(status_code=403, detail="Prośbę składa sołtys z potwierdzoną rolą")
        if post.status != PUBLISHED:
            raise HTTPException(status_code=409, detail="Poprawić albo odwołać można tylko opublikowane ogłoszenie")
        pending = (await _open_requests(session, [post.id])).get(post.id, [])
        if any(r.kind == body.kind for r in pending):
            raise HTTPException(status_code=409, detail="Ta prośba już czeka na redakcję")
        request = SolectwoPostRequest(
            post_id=post.id, user_id=user.id, kind=body.kind, message=body.message.strip(),
        )
        session.add(request)
        await session.commit()
        await session.refresh(post)
        requests = await _open_requests(session, [post.id])
    await _notify_admin_request(post, request)
    logger.info(f"Prośba o {body.kind} ogłoszenia {post.id} od {post.signed_as}")
    return _post_out(post, requests.get(post.id))


async def _notify_admin_request(post: SolectwoPost, request: SolectwoPostRequest) -> None:
    """Dzwonek do redakcji o prośbie sołtysa — ta sama droga co przy nowym ogłoszeniu."""
    try:
        from src.newsletter.email_service import EmailService

        admin_email = settings.ADMIN_ALERT_EMAIL
        if not admin_email:
            logger.warning("Prośba sołtysa bez dzwonka — brak ADMIN_ALERT_EMAIL")
            return
        e = html_escape
        what = "korektę" if request.kind == V_CORRECTION else "ODWOŁANIE"
        html = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1d4ed8;margin-bottom:4px">Sołtys prosi o {what} ogłoszenia</h2>
          <p style="color:#64748b;font-size:13px;margin-top:0">{e(post.signed_as or '')}</p>
          <p><strong>{e(post.title or '')}</strong></p>
          <div style="background:#f1f5f9;padding:16px;border-radius:8px">{e(request.message)}</div>
          <p><a href="{settings.APP_URL.rstrip('/')}/profil?zakladka=solectwa-admin">
            Przejdź do redakcji sołectw →</a></p>
        </div>
        """
        await EmailService().send_email(
            to_email=admin_email,
            subject=f"Prośba o {what}: {post.title or post.signed_as}",
            html_content=html,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Dzwonek nie zadzwonił dla prośby {request.id}: {exc}")


# ── Publicznie ───────────────────────────────────────────────────────────

class PostPublic(BaseModel):
    id: int
    solectwo: str
    signed_as: str
    title: str
    summary: Optional[str]
    transcript: Optional[str]
    doc_type: Optional[str]
    event_at: Optional[datetime]
    event_until: Optional[datetime]
    published_at: Optional[datetime]
    # `published` albo `withdrawn`. Nic więcej o procesie: ani powodu, ani dat
    # korekt, ani historii — to rozmowa sołtysa z redakcją, nie mieszkańców.
    status: str = PUBLISHED


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """Naiwny UTC z bazy → ze strefą, żeby front nie czytał go jako czasu
    lokalnego (lekcja `/api/events` z 25.08.2026)."""
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value else None


@router.get("/posts/{post_id}", response_model=PostPublic)
async def public_post(post_id: int):
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post or post.status not in (PUBLISHED, WITHDRAWN):
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
    withdrawn = post.status == WITHDRAWN
    return PostPublic(
        id=post.id, solectwo=post.solectwo, signed_as=post.signed_as,
        # Odwołane: bez tytułu, treści i terminu — inaczej termin z odwołanego
        # ogłoszenia dalej by „obowiązywał”, a tytuł zdradzałby, co odwołano
        title=f"Ogłoszenie sołectwa {post.solectwo}" if withdrawn else (post.title or post.signed_as),
        summary=None if withdrawn else post.summary,
        transcript=None if withdrawn else post.transcript,
        doc_type=post.doc_type,
        event_at=None if withdrawn else _utc(post.event_at),
        event_until=None if withdrawn else _utc(post.event_until),
        published_at=_utc(post.published_at),
        status=post.status,
    )


# ── Redakcja ─────────────────────────────────────────────────────────────

class PostAdmin(PostOut):
    transcript: Optional[str]
    doc_type: Optional[str]
    note: Optional[str]
    event_at: Optional[datetime]
    event_until: Optional[datetime]
    personal_data: Optional[list]
    illegible: Optional[list]
    ai_error: Optional[str]
    image_count: int
    author_email: Optional[str]
    author_name: Optional[str]


@router.get("/admin/posts", response_model=List[PostAdmin])
async def admin_posts(status: Optional[str] = None, admin=Depends(get_admin_user)):
    async with async_session() as session:
        query = (
            select(SolectwoPost, User)
            .join(User, User.id == SolectwoPost.user_id, isouter=True)
            .order_by(SolectwoPost.created_at.desc())
            .limit(100)
        )
        if status:
            query = query.where(SolectwoPost.status == status)
        rows = list((await session.execute(query)).all())
        # Prośba sołtysa o korektę starego ogłoszenia nie może zginąć za limitem
        # stu najnowszych — dociągamy takie ogłoszenia osobno
        seen = {p.id for p, _ in rows}
        waiting = select(SolectwoPostRequest.post_id).where(SolectwoPostRequest.status == "open")
        extra = (await session.execute(
            select(SolectwoPost, User)
            .join(User, User.id == SolectwoPost.user_id, isouter=True)
            .where(SolectwoPost.id.in_(waiting), SolectwoPost.id.notin_(list(seen) or [0]))
        )).all()
        rows = list(extra) + rows
        requests = await _open_requests(session, [p.id for p, _ in rows])
    return [
        PostAdmin(
            **_post_out(p, requests.get(p.id)).model_dump(),
            transcript=p.transcript, doc_type=p.doc_type, note=p.note,
            event_at=_utc(p.event_at), event_until=_utc(p.event_until),
            personal_data=p.personal_data, illegible=p.illegible, ai_error=p.ai_error,
            image_count=0 if p.images_deleted_at else len(p.image_files or []),
            author_email=u.email if u else None, author_name=u.full_name if u else None,
        )
        for p, u in rows
    ]


@router.get("/admin/posts/{post_id}/images/{index}")
async def admin_post_image(post_id: int, index: int, admin=Depends(get_admin_user)):
    """Oryginał tylko dla redakcji — front pobiera go z nagłówkiem autoryzacji
    i pokazuje przez `URL.createObjectURL`, bo `<img src>` nagłówka nie wyśle."""
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
    if not post or post.images_deleted_at or not (0 <= index < len(post.image_files or [])):
        raise HTTPException(status_code=404, detail="Nie ma takiego zdjęcia")
    path = PRIVATE_DIR / post.image_files[index]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Plik zdjęcia nie istnieje")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


class PostEdit(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    summary: Optional[str] = None
    transcript: Optional[str] = None


@router.patch("/admin/posts/{post_id}", response_model=PostOut)
async def edit_post(post_id: int, body: PostEdit, admin=Depends(get_admin_user)):
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        if post.status == PUBLISHED:
            raise HTTPException(status_code=409, detail="Ogłoszenie jest już opublikowane")
        for field_name in ("title", "summary", "transcript"):
            value = getattr(body, field_name)
            if value is not None:
                setattr(post, field_name, value.strip() or None)
        session.add(post)
        await session.commit()
        await session.refresh(post)
    return _post_out(post)


@router.post("/admin/posts/{post_id}/reread", response_model=PostOut)
async def reread_post(
    post_id: int, background_tasks: BackgroundTasks, admin=Depends(get_admin_user),
):
    """Ponowny odczyt — po awarii modelu albo gdy przedruk wyszedł słabo."""
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post or post.status == PUBLISHED or post.images_deleted_at:
            raise HTTPException(status_code=409, detail="Tego ogłoszenia nie da się odczytać ponownie")
        post.status = PROCESSING
        post.ai_error = None
        session.add(post)
        await session.commit()
        await session.refresh(post)
    background_tasks.add_task(process_post, post.id)
    return _post_out(post)


async def _publish_article(session, post: SolectwoPost, now: datetime) -> Article:
    """Ogłoszenie → `articles`. Kategoryzację robi ten sam `ArticleProcessor`
    co dla reszty materiału, ale tytuł, podsumowanie i termin zatwierdził
    człowiek — te pola wracają po kategoryzacji na wartości z moderacji."""
    from src.ai.article_processor import ArticleProcessor

    source = (await session.execute(
        select(Source).where(Source.name == SOURCE_NAME)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=500,
            detail=f"Brak źródła „{SOURCE_NAME}” — uruchom migrację add_user_roles_and_solectwo_posts",
        )

    article = Article(
        source_id=source.id,
        external_id=f"solectwo-post-{post.id}",
        title=post.title or post.signed_as,
        content=post.transcript or post.summary or "",
        summary=post.summary,
        url=post_url(post.id),
        author=post.signed_as,
        published_at=now,
        scraped_at=now,
        event_at=post.event_at,
        event_until=post.event_until,
        processed=False,
    )
    session.add(article)
    await session.commit()
    await session.refresh(article)

    try:
        await ArticleProcessor().process_article(article, session)
    except Exception as exc:  # noqa: BLE001 — publikacja nie czeka na kategoryzację;
        # nieprzetworzony wpis podejmie przebieg o :15 (`run_categorization_catchup`)
        logger.error(f"Kategoryzacja ogłoszenia {post.id} nie powiodła się: {exc}")
        await session.rollback()
        article = await session.get(Article, article.id)

    article.display_title = post.title or article.display_title
    article.summary = post.summary or article.summary
    if post.event_at:
        article.event_at = post.event_at
        article.event_until = post.event_until
    # Człowiek zatwierdził publikację — heurystyka zapychacza nie ma jej cofać
    article.is_filler = False
    article.is_promotional = False
    session.add(article)
    await session.commit()
    return article


@router.post("/admin/posts/{post_id}/approve", response_model=PostOut)
async def approve_post(
    post_id: int, background_tasks: BackgroundTasks, admin=Depends(get_admin_user),
):
    now = datetime.utcnow()
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        if post.status not in (PENDING, FAILED):
            raise HTTPException(status_code=409, detail="To ogłoszenie nie czeka na decyzję")
        if not (post.title and (post.summary or post.transcript)):
            raise HTTPException(status_code=400, detail="Uzupełnij tytuł i treść przed publikacją")

        article = await _publish_article(session, post, now)
        post = await session.get(SolectwoPost, post_id)
        post.status = PUBLISHED
        post.article_id = article.id
        post.published_at = now
        post.moderated_by = admin.email
        post.moderated_at = now
        _record_version(session, post, V_PUBLICATION, None, admin.email, now)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        author = await session.get(User, post.user_id) if post.user_id else None

    if author:
        background_tasks.add_task(_mail_decision, author.email, post.title, True, post.id, None)
    logger.info(f"Ogłoszenie {post.id} opublikowane jako artykuł {article.id}")
    return _post_out(post)


class RejectBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post("/admin/posts/{post_id}/reject", response_model=PostOut)
async def reject_post(
    post_id: int, body: RejectBody, background_tasks: BackgroundTasks,
    admin=Depends(get_admin_user),
):
    now = datetime.utcnow()
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        if post.status == PUBLISHED:
            raise HTTPException(status_code=409, detail="Ogłoszenie jest już opublikowane")
        post.status = REJECTED
        post.reject_reason = (body.reason or "").strip() or None
        post.moderated_by = admin.email
        post.moderated_at = now
        session.add(post)
        await session.commit()
        await session.refresh(post)
        author = await session.get(User, post.user_id) if post.user_id else None

    if author:
        background_tasks.add_task(
            _mail_decision, author.email, post.title or "Twoje ogłoszenie", False, post.id,
            post.reject_reason,
        )
    return _post_out(post)


# ── Po publikacji: korekta i odwołanie (E7) ──────────────────────────────

def _record_version(
    session, post: SolectwoPost, kind: str, reason: Optional[str],
    changed_by: Optional[str], now: datetime,
) -> SolectwoPostVersion:
    """Opublikowana postać ogłoszenia w historii. Numer rośnie o jeden;
    `post.version` wskazuje ostatni wiersz."""
    post.version = (post.version or 0) + 1
    version = SolectwoPostVersion(
        post_id=post.id, version=post.version, kind=kind,
        title=post.title, summary=post.summary, transcript=post.transcript,
        event_at=post.event_at, event_until=post.event_until,
        reason=reason, changed_by=changed_by, created_at=now,
    )
    session.add(version)
    return version


async def _forget_chunks(session, source_type: str, source_id: int) -> None:
    """Stare chunki RAG znikają w chwili zmiany — agent nie może cytować
    treści, którą redakcja właśnie poprawiła albo odwołała."""
    await session.execute(
        sql_text("DELETE FROM document_embeddings WHERE source_type = :t AND source_id = :i"),
        {"t": source_type, "i": source_id},
    )


async def _article_events(session, article_id: Optional[int]) -> list[Event]:
    if not article_id:
        return []
    return list((await session.execute(
        select(Event).where(Event.source_article_id == article_id)
    )).scalars().all())


async def _withdraw_event(session, event: Event, now: datetime) -> None:
    """Wydarzenie z odwołanego ogłoszenia znika z kalendarza. Jeśli to ten sam
    termin ogłosiło też inne źródło (powtórki wskazują nasz wpis przez
    `canonical_id`), najstarsza powtórka przejmuje rolę wpisu głównego —
    cudza publikacja nie może zniknąć razem z naszą."""
    event.withdrawn_at = now
    event.updated_at = now
    session.add(event)
    await _forget_chunks(session, "event", event.id)
    if event.canonical_id is not None:
        return
    duplicates = list((await session.execute(
        select(Event).where(Event.canonical_id == event.id, Event.withdrawn_at.is_(None))
        .order_by(Event.created_at, Event.id)
    )).scalars().all())
    if not duplicates:
        return
    head, rest = duplicates[0], duplicates[1:]
    head.canonical_id = None
    head.embedded = False  # powtórki nie mają chunku — job osadzi nowy wpis główny
    session.add(head)
    for other in rest:
        other.canonical_id = head.id
        session.add(other)
    logger.info(f"Wydarzenie #{event.id} odwołane — wpisem głównym zostaje #{head.id}")


async def _close_request(session, post: SolectwoPost, request_id: Optional[int], admin_email: str, now: datetime) -> None:
    if request_id is None:
        return
    request = await session.get(SolectwoPostRequest, request_id)
    if not request or request.post_id != post.id:
        raise HTTPException(status_code=404, detail="Nie znaleziono prośby sołtysa")
    request.status = "done"
    request.handled_by = admin_email
    request.handled_at = now
    session.add(request)


class TermIn(BaseModel):
    """Termin w czasie LOKALNYM, tak jak go wpisuje redakcja. Bez godziny =
    wydarzenie całodniowe, czyli lokalna północ — konwencja całego projektu."""
    day: date
    start: Optional[time] = None
    end: Optional[time] = None


def _term_utc(term: TermIn) -> tuple[datetime, Optional[datetime]]:
    start_local = datetime.combine(term.day, term.start or time(0, 0))
    end_utc = None
    if term.end is not None:
        if term.start is None:
            raise HTTPException(status_code=400, detail="Godzina końca wymaga godziny rozpoczęcia")
        end_local = datetime.combine(term.day, term.end)
        if end_local <= start_local:
            raise HTTPException(status_code=400, detail="Koniec musi być po rozpoczęciu")
        end_utc = to_utc(end_local)
    return to_utc(start_local), end_utc


class PostCorrection(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    summary: Optional[str] = None
    transcript: Optional[str] = None
    # keep = termin bez zmian; set = nowy termin z `term`; clear = bez terminu
    term_action: Literal["keep", "set", "clear"] = "keep"
    term: Optional[TermIn] = None
    reason: str = Field(min_length=3, max_length=500)
    request_id: Optional[int] = None


@router.post("/admin/posts/{post_id}/correct", response_model=PostOut)
async def correct_post(
    post_id: int, body: PostCorrection, background_tasks: BackgroundTasks,
    admin=Depends(get_admin_user),
):
    """Korekta opublikowanego ogłoszenia: nowa wersja w historii, poprawiony
    artykuł, termin wydarzenia w kalendarzu, świeże osadzenie RAG. Zmiana
    TERMINU wraca do najbliższego briefingu z etykietą „KOREKTA”."""
    now = datetime.utcnow()
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        if post.status != PUBLISHED:
            raise HTTPException(status_code=409, detail="Poprawić można tylko opublikowane ogłoszenie")

        before = (post.title, post.summary, post.transcript, post.event_at, post.event_until)
        for field_name in ("title", "summary", "transcript"):
            value = getattr(body, field_name)
            if value is not None:
                setattr(post, field_name, value.strip() or None)
        if not (post.title and (post.summary or post.transcript)):
            raise HTTPException(status_code=400, detail="Ogłoszenie musi mieć tytuł i treść")
        if body.term_action == "set":
            if body.term is None:
                raise HTTPException(status_code=400, detail="Podaj nowy termin")
            post.event_at, post.event_until = _term_utc(body.term)
        elif body.term_action == "clear":
            post.event_at, post.event_until = None, None

        after = (post.title, post.summary, post.transcript, post.event_at, post.event_until)
        if after == before:
            raise HTTPException(status_code=400, detail="Korekta niczego nie zmienia")
        term_changed = after[3:] != before[3:]
        title_changed = after[0] != before[0]

        post.corrected_at = now
        _record_version(session, post, V_CORRECTION, body.reason.strip(), admin.email, now)
        await _close_request(session, post, body.request_id, admin.email, now)

        article = await session.get(Article, post.article_id) if post.article_id else None
        if article:
            article.title = post.title or post.signed_as
            article.display_title = post.title or article.display_title
            article.summary = post.summary
            article.content = post.transcript or post.summary or ""
            article.event_at = post.event_at
            article.event_until = post.event_until
            if term_changed:
                article.term_corrected_at = now
            # `scraped_at` = chwila, w której mamy tę treść — job osadzania
            # (okno 3 dni) jest siatką, gdyby osadzenie w tle się nie udało
            article.scraped_at = now
            article.embedded = False
            session.add(article)
            await _forget_chunks(session, "article", article.id)

            for event in await _article_events(session, article.id):
                if event.withdrawn_at:
                    continue
                if term_changed and post.event_at is None:
                    # Bez terminu nie ma czego trzymać w kalendarzu
                    await _withdraw_event(session, event, now)
                    continue
                if term_changed:
                    event.event_date = post.event_at
                    event.end_date = post.event_until
                    event.event_time = (
                        None if is_all_day(post.event_at, post.event_until)
                        else to_local(post.event_at).strftime("%H:%M")
                    )
                if title_changed:
                    event.title = post.title
                # Opis wydarzenia pisał model z PIERWSZEJ wersji — mógł nieść
                # starą datę. Podsumowanie zatwierdził człowiek.
                if post.summary:
                    event.description = post.summary
                    event.short_description = post.summary[:300]
                event.updated_at = now
                event.embedded = False
                session.add(event)
                await _forget_chunks(session, "event", event.id)

        session.add(post)
        await session.commit()
        await session.refresh(post)
        requests = await _open_requests(session, [post.id])
        author = await session.get(User, post.user_id) if post.user_id else None

    if post.article_id:
        background_tasks.add_task(_reembed_article, post.article_id)
    if author:
        background_tasks.add_task(
            _mail_change, author.email, post.title, V_CORRECTION, post.id, body.reason.strip(),
        )
    logger.info(f"Ogłoszenie {post.id} poprawione (wersja {post.version}, termin zmieniony: {term_changed})")
    return _post_out(post, requests.get(post.id))


class PostWithdraw(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    request_id: Optional[int] = None


@router.post("/admin/posts/{post_id}/withdraw", response_model=PostOut)
async def withdraw_post(
    post_id: int, body: PostWithdraw, background_tasks: BackgroundTasks,
    admin=Depends(get_admin_user),
):
    """Odwołanie: wpis znika z feedu, briefingu, newslettera, pusha, agentów
    i kalendarza, a strona ogłoszenia mówi, że je odwołano i dlaczego.
    Nic nie jest kasowane — historia zostaje."""
    now = datetime.utcnow()
    reason = body.reason.strip()
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
        if post.status != PUBLISHED:
            raise HTTPException(status_code=409, detail="Odwołać można tylko opublikowane ogłoszenie")
        post.status = WITHDRAWN
        post.withdrawn_at = now
        post.withdraw_reason = reason
        _record_version(session, post, V_WITHDRAWAL, reason, admin.email, now)
        await _close_request(session, post, body.request_id, admin.email, now)

        article = await session.get(Article, post.article_id) if post.article_id else None
        if article:
            article.withdrawn_at = now
            session.add(article)
            await _forget_chunks(session, "article", article.id)
            for event in await _article_events(session, article.id):
                if not event.withdrawn_at:
                    await _withdraw_event(session, event, now)

        session.add(post)
        await session.commit()
        await session.refresh(post)
        requests = await _open_requests(session, [post.id])
        author = await session.get(User, post.user_id) if post.user_id else None

    if author:
        background_tasks.add_task(_mail_change, author.email, post.title, V_WITHDRAWAL, post.id, reason)
    logger.info(f"Ogłoszenie {post.id} odwołane: {reason}")
    return _post_out(post, requests.get(post.id))


class RequestDismiss(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post("/admin/requests/{request_id}/dismiss", response_model=PostOut)
async def dismiss_request(
    request_id: int, body: RequestDismiss, background_tasks: BackgroundTasks,
    admin=Depends(get_admin_user),
):
    """Prośba bez zmiany ogłoszenia (np. sprawa wyjaśniona telefonicznie).
    Sołtys dostaje odpowiedź — prośba, która znika bez słowa, wraca jutro."""
    now = datetime.utcnow()
    async with async_session() as session:
        request = await session.get(SolectwoPostRequest, request_id)
        if not request or request.status != "open":
            raise HTTPException(status_code=404, detail="Nie znaleziono otwartej prośby")
        request.status = "dismissed"
        request.handled_by = admin.email
        request.handled_at = now
        session.add(request)
        post = await session.get(SolectwoPost, request.post_id)
        await session.commit()
        await session.refresh(post)
        requests = await _open_requests(session, [post.id])
        author = await session.get(User, request.user_id) if request.user_id else None
    if author:
        background_tasks.add_task(
            _mail_change, author.email, post.title, "dismissed", post.id, (body.reason or "").strip() or None,
        )
    return _post_out(post, requests.get(post.id))


class VersionOut(BaseModel):
    version: int
    kind: str
    title: Optional[str]
    summary: Optional[str]
    transcript: Optional[str]
    event_at: Optional[datetime]
    event_until: Optional[datetime]
    reason: Optional[str]
    changed_by: Optional[str]
    created_at: datetime


@router.get("/admin/posts/{post_id}/versions", response_model=List[VersionOut])
async def post_versions(post_id: int, admin=Depends(get_admin_user)):
    """Pełna historia — tylko dla redakcji (stare wersje mogą nieść błąd,
    a proces decyzyjny nie jest widoczny dla mieszkańców)."""
    async with async_session() as session:
        rows = (await session.execute(
            select(SolectwoPostVersion).where(SolectwoPostVersion.post_id == post_id)
            .order_by(SolectwoPostVersion.version)
        )).scalars().all()
    return [
        VersionOut(
            version=v.version, kind=v.kind, title=v.title, summary=v.summary,
            transcript=v.transcript, event_at=_utc(v.event_at), event_until=_utc(v.event_until),
            reason=v.reason, changed_by=v.changed_by, created_at=_utc(v.created_at),
        )
        for v in rows
    ]


async def _reembed_article(article_id: int) -> None:
    """Osadzenie poprawionej treści od razu, nie o 6:50. Błąd nie jest
    groźny: wpis ma `embedded=False` i świeże `scraped_at`, więc najbliższy
    przebieg jobu go podejmie."""
    from src.scheduler.embedding_job import embed_article

    try:
        async with async_session() as session:
            row = (await session.execute(
                select(Article, Source.name).join(Source, Article.source_id == Source.id)
                .where(Article.id == article_id)
            )).first()
            if not row or row[0].withdrawn_at or row[0].embedded:
                return
            await embed_article(session, row[0], row[1])
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Osadzenie poprawionego artykułu {article_id} nie wyszło (podejmie job): {exc}")


async def _mail_change(
    email: str, title: Optional[str], kind: str, post_id: int, reason: Optional[str],
) -> None:
    try:
        from src.newsletter.email_service import EmailService
        await EmailService().send_solectwo_post_change(
            to_email=email, title=title or "Twoje ogłoszenie", kind=kind,
            post_url=post_url(post_id), reason=reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Mail o zmianie ogłoszenia {post_id} nie wyszedł: {exc}")


async def _mail_decision(
    email: str, title: str, approved: bool, post_id: int, reason: Optional[str],
) -> None:
    try:
        from src.newsletter.email_service import EmailService
        await EmailService().send_solectwo_post_decision(
            to_email=email, title=title, approved=approved,
            post_url=post_url(post_id) if approved else None, reason=reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Mail o decyzji dla ogłoszenia {post_id} nie wyszedł: {exc}")


# ── Retencja ─────────────────────────────────────────────────────────────

async def purge_old_images(session, now: Optional[datetime] = None) -> int:
    """Kasuje zdjęcia oryginałów `IMAGE_RETENTION_DAYS` po decyzji redakcji.
    Woła `retention_job`. Zwraca liczbę ogłoszeń, którym zdjęcia skasowano."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=IMAGE_RETENTION_DAYS)
    rows = (await session.execute(
        select(SolectwoPost).where(
            SolectwoPost.images_deleted_at.is_(None),
            SolectwoPost.status.in_([PUBLISHED, REJECTED, WITHDRAWN]),
            SolectwoPost.moderated_at < cutoff,
        )
    )).scalars().all()
    for post in rows:
        delete_images(post)
        post.images_deleted_at = now
        session.add(post)
    return len(rows)


def delete_images(post: SolectwoPost) -> None:
    for name in post.image_files or []:
        try:
            (PRIVATE_DIR / name).unlink(missing_ok=True)
        except OSError as exc:
            logger.error(f"Nie skasowano zdjęcia {name}: {exc}")
