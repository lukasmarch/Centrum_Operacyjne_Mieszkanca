#!/usr/bin/env python3
"""
Generator workflowów n8n dla RybnoLive (2026-07-25, po rewizji flow).

Dlaczego generator, a nie klikanie w UI: treść i grafiki powstają w backendzie
(`backend/src/services/social_content.py`), więc workflowy są cienkie i praktycznie
identyczne. Trzymanie ich jako kodu daje wersjonowanie w gicie i powtarzalny deploy.

Zasada działania każdego workflow:
    cron ─┐
          ├→ HTTP /api/social/… → Telegram [✅ Publikuj][🔄 Ponów] → Wait → Facebook → Telegram ✔
   webhook ┘  (backend zwraca      (URL przycisku =        (bez timeoutu:
              gotowy `message`)     $execution.resumeUrl)   brak kliknięcia = brak publikacji)

Publikacja idzie WYŁĄCZNIE jednorazowym resumeUrl. Sekret w URL-u webhooka pozwala tylko
wygenerować nową propozycję — nie opublikować, więc jego wyciek nic nie daje.

Użycie:
    python3 automation/n8n/build_workflows.py            # zapisz JSON-y lokalnie
    python3 automation/n8n/build_workflows.py --update   # nadpisz workflowy żyjące w n8n
    python3 automation/n8n/build_workflows.py --push     # utwórz NOWE (nieaktywne)

Do zmian w istniejących flow służy `--update`, nie `--push`: ten drugi tworzy duplikaty,
a sprzątanie po nim to trwały DELETE w n8n API. Sekret nie trafia do plików — w JSON-ach
siedzi placeholder, podstawiany dopiero przy wysyłce.
"""
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent

# ── stałe środowiska (credentiale już istnieją w n8n) ────────────────────────
API = "https://api.rybnolive.pl/api/social"
N8N = os.environ.get("N8N_BASE_URL", "https://n8n.srv1031112.hstgr.cloud")
SECRET = os.environ.get("KAMPANIA_SECRET", "")
SECRET_PLACEHOLDER = "__KAMPANIA_SECRET__"  # w plikach; podstawiany dopiero w drodze do n8n

PAGE_ID = "1266427606545851"
TG_CHAT = "7032918706"
CRED_TG = {"telegramApi": {"id": "6mOEqKTD16kohH87", "name": "RybnoLive Bot"}}
CRED_FB = {"facebookGraphApi": {"id": "DtAT3s4jbcSsRr4q", "name": "RybnoLive Page Token"}}
CRED_HDR = {"httpHeaderAuth": {"id": "YVBUuGjaUmDG4lzc", "name": "RybnoLive Social Token"}}
GRAPH_VERSION = "v23.0"  # zgodnie z tym, co działa na produkcji (README mówił v21.0 — nieprawda)


def nid() -> str:
    return str(uuid.uuid4())


def node(name, type_, version, params, pos, creds=None, webhook=False):
    n = {
        "parameters": params,
        "id": nid(),
        "name": name,
        "type": type_,
        "typeVersion": version,
        "position": pos,
    }
    if creds:
        n["credentials"] = creds
    if webhook:
        n["webhookId"] = nid()
    return n


# ── klocki wielokrotnego użytku ──────────────────────────────────────────────

def cron(name, expressions, pos):
    return node(name, "n8n-nodes-base.scheduleTrigger", 1.2,
                {"rule": {"interval": [{"field": "cronExpression", "expression": e} for e in expressions]}}, pos)


def manual_path(slug: str) -> str:
    """
    Sekret jest CZĘŚCIĄ ścieżki webhooka, nie parametrem `?k=`.

    Przycisk w Telegramie to zwykły link — nie da się wysłać nagłówka, a walidacja
    parametru wymagałaby dodatkowego noda IF w każdym workflow. Ścieżka z sekretem
    jest niezgadywalna i kosztuje zero nodów.

    W plikach zostaje PLACEHOLDER, nie sekret. Do 26.07 generator wpisywał tu prawdziwą
    wartość i JSON-y lądowały z nią w publicznym repo. Publikować się tym nie dało
    (chroni jednorazowy resumeUrl), ale dało się uruchamiać W2 w pętli — a to gpt-4o
    plus ~22 kredyty kie.ai za każdym razem.
    """
    return f"rybnolive-{slug}-{SECRET_PLACEHOLDER}"


def manual_webhook(name, path, pos):
    """Ręczne uruchomienie = również przycisk „wygeneruj ponownie”."""
    return node(name, "n8n-nodes-base.webhook", 2,
                {"httpMethod": "GET", "path": path, "options": {}}, pos, webhook=True)


def http_get(name, url, pos, timeout_ms=30000):
    return node(name, "n8n-nodes-base.httpRequest", 4.2, {
        "url": url,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": timeout_ms},
    }, pos, creds=CRED_HDR)


def wait_for_click(name, pos):
    """
    Wstrzymuje egzekucję do kliknięcia przycisku. Świadomie BEZ limitu czasu:
    limit sprawiłby, że po jego upływie przepływ ruszyłby dalej i opublikował post
    bez akceptacji. Brak kliknięcia = egzekucja zostaje w „waiting” i nic nie robi.
    """
    return node(name, "n8n-nodes-base.wait", 1.1,
                {"resume": "webhook", "httpMethod": "GET", "options": {}}, pos, webhook=True)


def tg_buttons(regen_path, regen_label="🔄 Wygeneruj ponownie"):
    return {"rows": [{"row": {"buttons": [
        {"text": "✅ Publikuj na Facebooku", "additionalFields": {"url": "={{ $execution.resumeUrl }}"}},
        {"text": regen_label, "additionalFields": {"url": f"{N8N}/webhook/{regen_path}"}},
    ]}}]}


def tg_confirm(name, text, pos):
    return node(name, "n8n-nodes-base.telegram", 1.2, {
        "operation": "sendMessage", "chatId": TG_CHAT, "text": text,
        "additionalFields": {"appendAttribution": False},
    }, pos, creds=CRED_TG)


def fb_publish(name, edge, params, pos):
    return node(name, "n8n-nodes-base.facebookGraphApi", 1, {
        "httpRequestMethod": "POST",
        "graphApiVersion": GRAPH_VERSION,
        "node": PAGE_ID,
        "edge": edge,
        "options": {"queryParameters": {"parameter": params}},
    }, pos, creds=CRED_FB)


def wire(*pairs):
    conns = {}
    for src, dst in pairs:
        conns.setdefault(src, {"main": [[]]})["main"][0].append({"node": dst, "type": "main", "index": 0})
    return conns


def workflow(name, nodes, connections):
    return {"name": name, "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}}


# ── W1: post tekstowy (dzienne podsumowanie AI) ──────────────────────────────

def build_text_workflow():
    n = [
        cron("Codziennie 7:45", ["45 7 * * *"], [-220, 0]),
        manual_webhook("Uruchom teraz", manual_path("post-tekst"), [-220, 180]),
        http_get("Propozycja", f"{API}/proposal?kind=text", [0, 80]),
        node("Do akceptacji (TG)", "n8n-nodes-base.telegram", 1.2, {
            # sendPhoto, nie sendMessage: od 26.07 backend dołącza kartę dnia (grafika
            # składana lokalnie z nagłówka), więc na Telegramie ma być widać dokładnie
            # to, co pójdzie na fanpage — razem z obrazkiem.
            "operation": "sendPhoto",
            "chatId": TG_CHAT,
            "file": "={{ $json.image_url }}",
            "additionalFields": {
                # Limit podpisu na Telegramie to 1024 znaki; podsumowanie bywa dłuższe.
                "caption": "={{ ('📝 Propozycja posta na FB (' + $json.date + ')\\n\\n' + $json.message).slice(0, 900) }}",
                "appendAttribution": False,
            },
            # Bez parse_mode: treść jest generowana przez AI i mogłaby zawierać
            # niedomknięte * lub _, na czym Telegram wywala 400.
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": tg_buttons(manual_path("post-tekst")),
        }, [220, 80], creds=CRED_TG),
        wait_for_click("Czekaj na akceptację", [440, 80]),
        # photos, nie feed: post ze zdjęciem bije w feedzie kartę linku, a przy okazji
        # znika pusta miniatura OG, którą FB rysował dla parametru `link`.
        # Adres rybnolive.pl zostaje w treści posta (dokłada go build_text_post).
        fb_publish("Publikuj na FB", "photos", [
            {"name": "url", "value": "={{ $('Propozycja').first().json.image_url }}"},
            {"name": "caption", "value": "={{ $('Propozycja').first().json.message }}"},
        ], [660, 80]),
        tg_confirm("Potwierdzenie", "✅ Post tekstowy opublikowany na fanpage'u RybnoLive.", [880, 80]),
    ]
    c = wire(
        ("Codziennie 7:45", "Propozycja"),
        ("Uruchom teraz", "Propozycja"),
        ("Propozycja", "Do akceptacji (TG)"),
        ("Do akceptacji (TG)", "Czekaj na akceptację"),
        ("Czekaj na akceptację", "Publikuj na FB"),
        ("Publikuj na FB", "Potwierdzenie"),
    )
    return workflow("RybnoLive — post tekstowy (podsumowanie AI)", n, c)


# ── W2: post graficzny (kie.ai) ──────────────────────────────────────────────

def build_photo_workflow():
    n = [
        # Wtorek i czwartek. Czwartek był wyłączony na czas kampanii, bo przebieg
        # o 17:00 wchodził na Reels animowany publikowany ręcznie 30.07 o tej samej
        # godzinie. Powód wygasł: w CAMPAIGN_PLAN czwartki są puste (najbliższe
        # pozycje to pt 07.08 i KPI-check 10.08), więc kolizji nie ma.
        # Koszt: ~22 kredyty kie.ai za post, drugi przebieg w tygodniu podwaja
        # tę pozycję — grafiki W2 to jedyne miejsce, gdzie projekt płaci za obraz.
        cron("Wtorki i czwartki 17:00", ["0 17 * * 2,4"], [-220, 0]),
        manual_webhook("Uruchom / ponów", manual_path("post-grafika"), [-220, 180]),
        # generowanie grafiki trwa 20-60 s → podniesiony timeout
        http_get("Propozycja + grafika", f"{API}/proposal?kind=photo", [0, 80], timeout_ms=200000),
        node("Do akceptacji (TG)", "n8n-nodes-base.telegram", 1.2, {
            "operation": "sendPhoto",
            "chatId": TG_CHAT,
            "file": "={{ $json.image_url }}",
            "additionalFields": {
                "caption": "={{ ('🖼 Propozycja posta z grafiką\\n\\n' + $json.message).slice(0, 900) }}",
                "appendAttribution": False,
            },
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": tg_buttons(manual_path("post-grafika"), "🎨 Inna grafika"),
        }, [220, 80], creds=CRED_TG),
        wait_for_click("Czekaj na akceptację", [440, 80]),
        fb_publish("Publikuj grafikę na FB", "photos", [
            {"name": "url", "value": "={{ $('Propozycja + grafika').first().json.image_url }}"},
            {"name": "caption", "value": "={{ $('Propozycja + grafika').first().json.message }}"},
        ], [660, 80]),
        tg_confirm("Potwierdzenie", "✅ Post z grafiką opublikowany na fanpage'u RybnoLive.", [880, 80]),
    ]
    c = wire(
        ("Wtorki i czwartki 17:00", "Propozycja + grafika"),
        ("Uruchom / ponów", "Propozycja + grafika"),
        ("Propozycja + grafika", "Do akceptacji (TG)"),
        ("Do akceptacji (TG)", "Czekaj na akceptację"),
        ("Czekaj na akceptację", "Publikuj grafikę na FB"),
        ("Publikuj grafikę na FB", "Potwierdzenie"),
    )
    return workflow("RybnoLive — post graficzny (kie.ai)", n, c)


# ── W3: kampania „Twoja gmina. Na żywo.” 27.07–10.08 ─────────────────────────

def build_campaign_workflow():
    # Godziny emisji z planu kampanii. Backend decyduje, czy coś przypada —
    # dzięki temu zmiana dat nie wymaga dotykania n8n.
    hours = ["45 7 * * *", "30 8 * * *", "0 9 * * *", "45 9 * * *", "0 10 * * *",
             "0 12 * * *", "45 16 * * *", "0 17 * * *", "0 18 * * *"]

    switch_params = {
        "rules": {"values": [
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [{
                        "id": nid(), "leftValue": "={{ $json.kind }}", "rightValue": "post",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True, "outputKey": "post",
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [{
                        "id": nid(), "leftValue": "={{ $json.kind }}", "rightValue": "reminder",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True, "outputKey": "reminder",
            },
        ]},
        # Gdy nic nie przypada, backend zwraca {"due": false} bez pola `kind` —
        # żadna reguła nie pasuje i egzekucja kończy się tutaj. Dlatego nie ma osobnego IF-a.
        "options": {},
    }

    n = [
        cron("Godziny emisji", hours, [-220, 0]),
        http_get("Co dziś?", f"{API}/campaign/due", [0, 0]),
        node("Post czy przypomnienie?", "n8n-nodes-base.switch", 3.2, switch_params, [220, 0]),
        node("Propozycja postu (TG)", "n8n-nodes-base.telegram", 1.2, {
            "operation": "sendPhoto",
            "chatId": TG_CHAT,
            "file": "={{ $json.image_url }}",
            "additionalFields": {
                "caption": "={{ ('📣 ' + $json.title + '\\n\\n' + $json.message + ($json.note ? '\\n\\nℹ️ ' + $json.note : '')).slice(0, 900) }}",
                "appendAttribution": False,
            },
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": {"rows": [{"row": {"buttons": [
                {"text": "✅ Publikuj na Facebooku", "additionalFields": {"url": "={{ $execution.resumeUrl }}"}},
            ]}}]},
        }, [440, -100], creds=CRED_TG),
        node("Przypomnienie (TG)", "n8n-nodes-base.telegram", 1.2, {
            "operation": "sendMessage",
            "chatId": TG_CHAT,
            "text": "={{ $json.message }}",
            # Treść przypomnień piszę sam (nie AI), więc Markdown jest bezpieczny.
            "additionalFields": {"parse_mode": "Markdown", "appendAttribution": False},
        }, [440, 120], creds=CRED_TG),
        wait_for_click("Czekaj na akceptację", [660, -100]),
        fb_publish("Publikuj na FB", "photos", [
            {"name": "url", "value": "={{ $('Co dziś?').first().json.image_url }}"},
            {"name": "caption", "value": "={{ $('Co dziś?').first().json.message }}"},
        ], [880, -100]),
        tg_confirm("Potwierdzenie", "={{ '✅ Opublikowano: ' + $('Co dziś?').first().json.title }}", [1100, -100]),
    ]

    conns = {
        "Godziny emisji": {"main": [[{"node": "Co dziś?", "type": "main", "index": 0}]]},
        "Co dziś?": {"main": [[{"node": "Post czy przypomnienie?", "type": "main", "index": 0}]]},
        # wyjście 0 = post, wyjście 1 = przypomnienie
        "Post czy przypomnienie?": {"main": [
            [{"node": "Propozycja postu (TG)", "type": "main", "index": 0}],
            [{"node": "Przypomnienie (TG)", "type": "main", "index": 0}],
        ]},
        "Propozycja postu (TG)": {"main": [[{"node": "Czekaj na akceptację", "type": "main", "index": 0}]]},
        "Czekaj na akceptację": {"main": [[{"node": "Publikuj na FB", "type": "main", "index": 0}]]},
        "Publikuj na FB": {"main": [[{"node": "Potwierdzenie", "type": "main", "index": 0}]]},
    }
    return workflow("RybnoLive — kampania 27.07–10.08", n, conns)


# ── zapis / wysyłka ──────────────────────────────────────────────────────────

BUILDERS = {
    "W1_post_tekstowy.json": build_text_workflow,
    "W2_post_graficzny.json": build_photo_workflow,
    "W3_kampania.json": build_campaign_workflow,
}

# ID workflowów żyjących w n8n — cel dla `--update`. Bez nich każda wysyłka tworzyłaby
# duplikat, a starą wersję trzeba by kasować ręcznie (DELETE w n8n API jest trwały).
LIVE_IDS = {
    "W1_post_tekstowy.json": "XVyOeaFWiNuESBkZ",
    "W2_post_graficzny.json": "UoR37sQDJniUJJw4",
    "W3_kampania.json": "ZgLqKnVckwmCema8",
}


def with_secret(payload: dict) -> dict:
    """Podstaw prawdziwy sekret w miejsce placeholdera — tylko w drodze do n8n."""
    filled = json.dumps(payload, ensure_ascii=False).replace(SECRET_PLACEHOLDER, SECRET)
    return json.loads(filled)


def _send(url: str, payload: dict, method: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(with_secret(payload), ensure_ascii=False).encode(),
        headers={"X-N8N-API-KEY": os.environ["N8N_API_KEY"], "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"n8n odrzuciło {payload['name']}: {exc.read().decode()[:400]}")


def push(payload: dict) -> str:
    """Utwórz NOWY workflow (nieaktywny). Duplikuje, jeśli taki już istnieje."""
    return _send(f"{N8N}/api/v1/workflows", payload, "POST")["id"]


def update(workflow_id: str, payload: dict) -> str:
    """Nadpisz istniejący workflow. Zachowuje id i stan aktywności."""
    return _send(f"{N8N}/api/v1/workflows/{workflow_id}", payload, "PUT")["id"]


if __name__ == "__main__":
    if not SECRET:
        raise SystemExit("Brak KAMPANIA_SECRET w środowisku — załaduj automation/.env")

    do_push = "--push" in sys.argv
    do_update = "--update" in sys.argv
    for filename, builder in BUILDERS.items():
        wf = builder()
        (HERE / filename).write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
        line = f"✔ {filename:26} {len(wf['nodes'])} nodów"
        if do_update:
            line += f"  →  zaktualizowany w n8n ({update(LIVE_IDS[filename], wf)})"
        if do_push:
            line += f"  →  n8n id {push(wf)}"
        print(line)
