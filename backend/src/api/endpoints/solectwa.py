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

AI Act art. 50: podsumowanie jest oznaczone na stronie jako przygotowane
automatycznie i sprawdzone przez redakcję (front, `SolectwoPostPage`).
"""
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import select

from src.auth.dependencies import get_admin_user, get_current_active_user
from src.config import settings
from src.database.connection import async_session
from src.database.schema import Article, SolectwoPost, Source, User
from src.services import roles as role_service
from src.services.time_span import to_local
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
        warning = (
            f"<p style='color:#b91c1c'>⚠️ {post.ai_error}</p>" if post.ai_error else ""
        )
        pii = (
            "<p>Wykryte dane osobowe: " + ", ".join(post.personal_data) + "</p>"
            if post.personal_data else ""
        )
        html = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#1d4ed8;margin-bottom:4px">Ogłoszenie sołectwa czeka na moderację</h2>
          <p style="color:#64748b;font-size:13px;margin-top:0">{post.signed_as}</p>
          <div style="background:#f1f5f9;padding:16px;border-radius:8px">
            <strong>{post.title or '(bez tytułu)'}</strong><br>{post.summary or ''}
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


def _post_out(post: SolectwoPost) -> PostOut:
    return PostOut(
        id=post.id, solectwo=post.solectwo, signed_as=post.signed_as,
        status=post.status, title=post.title, summary=post.summary,
        created_at=post.created_at, published_at=post.published_at,
        reject_reason=post.reject_reason,
        url=post_url(post.id) if post.status == PUBLISHED else None,
    )


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
    return [_post_out(p) for p in rows]


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


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """Naiwny UTC z bazy → ze strefą, żeby front nie czytał go jako czasu
    lokalnego (lekcja `/api/events` z 25.08.2026)."""
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value else None


@router.get("/posts/{post_id}", response_model=PostPublic)
async def public_post(post_id: int):
    async with async_session() as session:
        post = await session.get(SolectwoPost, post_id)
    if not post or post.status != PUBLISHED:
        raise HTTPException(status_code=404, detail="Nie znaleziono ogłoszenia")
    return PostPublic(
        id=post.id, solectwo=post.solectwo, signed_as=post.signed_as,
        title=post.title or post.signed_as, summary=post.summary,
        transcript=post.transcript, doc_type=post.doc_type,
        event_at=_utc(post.event_at), event_until=_utc(post.event_until),
        published_at=_utc(post.published_at),
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
        rows = (await session.execute(query)).all()
    return [
        PostAdmin(
            **_post_out(p).model_dump(),
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
            SolectwoPost.status.in_([PUBLISHED, REJECTED]),
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
