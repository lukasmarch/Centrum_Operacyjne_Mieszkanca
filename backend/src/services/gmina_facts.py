"""
Karta gminy — fakty fundamentalne, które agent dostaje ZAWSZE.

Dlaczego to nie jest RAG. 3.08.2026 na pytanie „gmina rybno ile ma sołectw"
asystent odpowiedział „nie posiadam danych, proszę skontaktować się z urzędem"
i dorzucił wykres ludności. Odpowiedź na takie pytanie nie może zależeć od tego,
czy retrieval trafi powyżej progu podobieństwa — to fundament, nie materiał
źródłowy. Dlatego karta wchodzi do promptu bezwarunkowo, każdemu agentowi,
przy każdym zapytaniu (~450 tokenów, przy obecnym ruchu grosze rocznie).

Co tu NIE wchodzi. Kryterium jest zawężające i celowo trudne do spełnienia:
fakt musi zmieniać się rzadziej niż raz na rok, mieścić się w jednej linijce
i być czymś, o co ludzie realnie pytają. Stawki podatków, harmonogramy,
obwieszczenia, godziny przyjęć — to warstwa RAG (`bip_static` / `article`).
Karta rozdęta do kilku kilobajtów zacznie konkurować o uwagę modelu
z materiałem źródłowym i pogorszy odpowiedzi na pytania bieżące, dlatego
`scripts/test_gmina_facts.py` pilnuje limitu MAX_FACTS_BYTES.

Źródło: BIP Gminy Rybno (bip.gminarybno.pl), zweryfikowane 3.08.2026 —
działy /147/ (jednostki pomocnicze), /2/ (jednostki organizacyjne),
/10040/ i /10042/ (organy gminy), /19/ (dane podstawowe).

⚠️ Sołectw jest 20, a `alert_policy.GMINA_RYBNO_PLACES` wylicza 22 nazwy —
to NIE jest ta sama lista i nie wolno jej tu podstawić. Alert_policy opisuje
miejscowości, w których może wypaść awaria (stąd Groszki, Wery i samo Gralewo),
a sołectwo to jednostka pomocnicza gminy. Karta idzie prosto do odpowiedzi
dla mieszkańca, więc trzyma się nazewnictwa z BIP.
"""

# Limit rozmiaru — patrz docstring. Podniesienie go to decyzja projektowa,
# nie sposób na zmieszczenie kolejnego faktu.
MAX_FACTS_BYTES = 2048

# Jednostki pomocnicze gminy — BIP /147/, stan na 3.08.2026.
SOLECTWA: tuple[str, ...] = (
    "Dębień", "Grabacz", "Grądy", "Gralewo Stacja", "Gronowo",
    "Hartowiec", "Jeglia", "Kopaniarze", "Koszelewki", "Koszelewy",
    "Naguszewo", "Nowa Wieś", "Prusy", "Rapaty", "Rumian",
    "Rybno", "Szczupliny", "Truszczyny", "Tuczki", "Żabiny",
)

# Jednostki organizacyjne gminy — BIP /2/, stan na 3.08.2026.
JEDNOSTKI: tuple[str, ...] = (
    "Zespół Szkół w Rybnie",
    "Szkoły Podstawowe: Rybno, Hartowiec, Koszelewy, Rumian, Żabiny",
    "Przedszkole w Rybnie", "Żłobek w Rybnie",
    "Gminny Ośrodek Pomocy Społecznej",
    "Samodzielny Publiczny Gminny Zakład Opieki Zdrowotnej",
    "Gminna Biblioteka Publiczna", "Ośrodek Sportu i Rekreacji",
)

_FACTS = f"""FAKTY PODSTAWOWE O GMINIE RYBNO (wiedza stała, zweryfikowana w BIP):
- Gmina wiejska Rybno, powiat działdowski, województwo warmińsko-mazurskie.
- Urząd Gminy Rybno, ul. Lubawska 15, 13-220 Rybno, tel. 23 696 60 55.
  BIP: bip.gminarybno.pl | ePUAP: /2803062/SkrytkaESP
- Wójt Gminy Rybno: Tomasz Węgrzynowski.
- Rada Gminy Rybno IX kadencji (2024-2029), 15 radnych.
  Przewodniczący: Piotr Kornatowski. Wiceprzewodniczący: Grzegorz Januszewski.
- Gmina ma {len(SOLECTWA)} sołectw: {", ".join(SOLECTWA)}.
- Jednostki organizacyjne gminy: {"; ".join(JEDNOSTKI)}.
- Sprawy powiatowe (prawo jazdy, rejestracja pojazdów, pozwolenia na budowę)
  załatwia Starostwo Powiatowe w Działdowie, nie Urząd Gminy."""

_PRECEDENCE = (
    "Powyższe fakty są prawdziwe i możesz się na nie powoływać bez zastrzeżeń. "
    "Jeśli materiał w bloku KONTEKST mówi co innego — pierwszeństwo ma KONTEKST, "
    "bo jest świeższy (np. zmiana na stanowisku). Nie dopisuj do tej listy faktów, "
    "których tu nie ma."
)


def gmina_facts() -> str:
    """Karta gminy jako treść wiadomości `system`."""
    return f"{_FACTS}\n\n{_PRECEDENCE}"
