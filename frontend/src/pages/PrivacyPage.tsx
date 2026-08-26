/**
 * Polityka prywatności (RODO art. 13 i 14)
 *
 * ⚠️ WERSJA ROBOCZA — przed publikacją na produkcji wymaga weryfikacji
 * przez radcę prawnego / adwokata.
 */

import React from 'react';
import LegalLayout from '../../components/LegalLayout';
import { AppSection } from '../../types';

interface PrivacyPageProps {
  onNavigate: (section: AppSection) => void;
}

export const PRIVACY_VERSION = '2026-08-26';

const PrivacyPage: React.FC<PrivacyPageProps> = ({ onNavigate }) => (
  <LegalLayout title="Polityka prywatności" updated="26 sierpnia 2026">

    <h2>1. Administrator danych</h2>
    <p>Administratorem danych osobowych jest <strong>Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz</strong>, NIP: 571-156-78-15, adres: Żabiny 96, 13-220 Rybno (dalej: „Administrator"). Kontakt we wszystkich sprawach dotyczących danych osobowych: <strong>biuro@lumargo.pl</strong>, tel. <strong>+48 501 081 723</strong>.</p>

    <h2>2. Jakie dane przetwarzamy, po co i na jakiej podstawie</h2>
    <table>
      <thead>
        <tr><th>Kategoria danych</th><th>Cel</th><th>Podstawa prawna (RODO)</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>Dane konta: e-mail, imię i nazwisko, miejscowość, hasło (zaszyfrowane)</td>
          <td>założenie i obsługa konta, świadczenie usług Serwisu</td>
          <td>art. 6 ust. 1 lit. b — wykonanie umowy</td>
        </tr>
        <tr>
          <td>Dane płatności: identyfikatory transakcji Przelewy24, wybrany plan, okres</td>
          <td>obsługa płatności za plany płatne, rozliczenia i obowiązki podatkowe</td>
          <td>art. 6 ust. 1 lit. b i c</td>
        </tr>
        <tr>
          <td>Treść rozmów z Asystentem AI</td>
          <td>udzielenie odpowiedzi, historia rozmów, poprawa jakości usługi</td>
          <td>art. 6 ust. 1 lit. b; lit. f — doskonalenie usługi</td>
        </tr>
        <tr>
          <td>Zgłoszenia mieszkańców: treść, lokalizacja GPS, zdjęcie, opcjonalne dane kontaktowe</td>
          <td>publikacja i obsługa zgłoszenia lokalnego problemu</td>
          <td>art. 6 ust. 1 lit. a — zgoda przy wysyłce zgłoszenia</td>
        </tr>
        <tr>
          <td>E-mail (newsletter), subskrypcje push</td>
          <td>wysyłka newslettera i powiadomień</td>
          <td>art. 6 ust. 1 lit. a — zgoda (można ją cofnąć w każdej chwili)</td>
        </tr>
        <tr>
          <td>Dane techniczne: adres IP, typ przeglądarki, logi serwera</td>
          <td>bezpieczeństwo, przeciwdziałanie nadużyciom, limity anonimowego użycia AI</td>
          <td>art. 6 ust. 1 lit. f — prawnie uzasadniony interes</td>
        </tr>
      </tbody>
    </table>
    <p>Podanie danych konta jest dobrowolne, ale niezbędne do rejestracji. Zgody (newsletter, marketing, push) są zawsze opcjonalne.</p>

    <h2>3. Dane pozyskiwane z innych źródeł (art. 14 RODO)</h2>
    <p>Serwis agreguje publicznie dostępne informacje lokalne. W ich treści mogą pojawiać się dane osobowe osób trzecich:</p>
    <ul>
      <li><strong>Publiczne wpisy z serwisu Facebook</strong> (profile informacyjne o charakterze publicznym — lokalne media, instytucje): kategorie danych — imiona i nazwiska, wizerunek, treści wpisów. Cel: informowanie społeczności lokalnej (art. 6 ust. 1 lit. f). Prezentujemy skróty z odesłaniem do oryginału.</li>
      <li><strong>CEIDG</strong> (Centralna Ewidencja i Informacja o Działalności Gospodarczej): dane przedsiębiorców — nazwa firmy, imię i nazwisko, adres wykonywania działalności (ulica i numer budynku, miejscowość, kod pocztowy), NIP, REGON, kody PKD i branża, status wpisu oraz data rozpoczęcia działalności. Cel: prowadzenie katalogu lokalnych firm (art. 6 ust. 1 lit. f). Źródło: rejestr publiczny CEIDG. Nie pobieramy ani nie przechowujemy danych kontaktowych z rejestru (adresu e-mail, telefonu, strony www) — telefon, e-mail i adres strony pojawiają się w katalogu wyłącznie wtedy, gdy firma poda je samodzielnie, przejmując swoją wizytówkę.</li>
      <li><strong>Lokalne portale informacyjne, strony urzędowe i BIP</strong>: dane zawarte w publikowanych tam materiałach prasowych i urzędowych.</li>
      <li><strong>Nagrania obrad Rady Gminy Rybno</strong> (galeria nagrań na gminarybno.pl): kategorie danych — imiona i nazwiska radnych, Wójta, sołtysów i urzędników, treść ich wypowiedzi na jawnych obradach. Cel: informowanie mieszkańców o działalności organu władzy publicznej (art. 6 ust. 1 lit. f). Podstawa jawności: art. 11b ust. 1 oraz art. 20 ust. 1b ustawy o samorządzie gminnym — obrady rady gminy są jawne, a gmina ma obowiązek je transmitować, utrwalać i udostępniać nagranie publicznie. Nagranie przepisujemy automatycznie (transkrypcja mowy na tekst — <strong>bez rozpoznawania głosu i bez identyfikacji mówcy po barwie głosu</strong>, nie przetwarzamy danych biometrycznych), a na podstawie zapisu powstaje skrót obrad. <strong>Transkrypt nie jest publikowany</strong> — służy wyłącznie sprawdzeniu, czy cytat w skrócie naprawdę padł. Publikujemy sam skrót, i to dopiero po sprawdzeniu i zatwierdzeniu przez człowieka. Wypowiedzi osób niepełniących funkcji publicznych (mieszkańców, gości) referujemy <strong>bez podawania nazwiska</strong>, a spraw prywatnych nie opisujemy w ogóle.</li>
    </ul>
    <p><strong>Skąd wiesz, że tu jesteś:</strong> art. 14 ust. 5 lit. b RODO zwalnia nas z zawiadamiania każdej osoby z osobna, gdy dane pochodzą ze źródła publicznego, a poinformowanie wszystkich wymagałoby niewspółmiernie dużego wysiłku — w zamian nakazuje podać te informacje publicznie. Ten akapit jest właśnie takim powiadomieniem.</p>
    <p><strong>Prawo sprzeciwu:</strong> każda osoba, której dane pojawiają się w agregowanych treściach, może wnieść sprzeciw lub zażądać usunięcia danych, pisząc na biuro@lumargo.pl. Żądania rozpatrujemy niezwłocznie, nie później niż w 7 dni.</p>

    <h2>4. Odbiorcy danych (podmioty przetwarzające)</h2>
    <p>Dane powierzamy wyłącznie w zakresie niezbędnym do działania Serwisu:</p>
    <ul>
      <li><strong>Hetzner Online GmbH</strong> (Niemcy, UE) — hosting serwera i bazy danych,</li>
      <li><strong>OpenAI</strong> oraz <strong>Google (Gemini)</strong> — przetwarzanie zapytań do Asystenta AI, automatyczna kategoryzacja treści oraz transkrypcja i streszczanie nagrań obrad Rady Gminy (ścieżka dźwiękowa nagrania i powstały z niej tekst),</li>
      <li><strong>PayPro S.A. (Przelewy24)</strong> — obsługa płatności (odrębny administrator danych transakcyjnych),</li>
      <li><strong>Resend</strong> — wysyłka wiadomości e-mail,</li>
      <li>dostawcy danych pogodowych i jakości powietrza (Airly i in.) — bez przekazywania danych osobowych.</li>
    </ul>

    <h2>5. Przekazywanie danych poza EOG</h2>
    <p>W związku z korzystaniem z usług OpenAI i Google dane (treść zapytań do AI) mogą być przetwarzane na serwerach poza Europejskim Obszarem Gospodarczym, w szczególności w USA. Przekazanie odbywa się na podstawie <strong>standardowych klauzul umownych (SCC)</strong> zatwierdzonych przez Komisję Europejską oraz — w przypadku podmiotów certyfikowanych — decyzji o adekwatności EU-U.S. Data Privacy Framework.</p>

    <h2>6. Okresy przechowywania</h2>
    <table>
      <thead>
        <tr><th>Dane</th><th>Okres</th></tr>
      </thead>
      <tbody>
        <tr><td>Dane konta</td><td>do usunięcia konta przez Użytkownika lub Administratora</td></tr>
        <tr><td>Historia rozmów z AI (zalogowani)</td><td>do usunięcia konta lub na żądanie</td></tr>
        <tr><td>Rozmowy anonimowe i dane o limitach (IP)</td><td>do 90 dni</td></tr>
        <tr><td>Zgłoszenia mieszkańców</td><td>do 12 miesięcy od rozwiązania sprawy (dane autora — anonimizowane)</td></tr>
        <tr><td>Dane rozliczeniowe</td><td>5 lat od końca roku podatkowego (obowiązek ustawowy)</td></tr>
        <tr><td>Transkrypt nagrania obrad Rady Gminy (niepublikowany)</td><td>przez okres publikowania skrótu danej sesji — transkrypt jest jedynym materiałem pozwalającym sprawdzić, czy zacytowane zdanie naprawdę padło; usuwany razem ze skrótem</td></tr>
        <tr><td>Skrót obrad Rady Gminy (publikowany)</td><td>bezterminowo — pełni funkcję archiwum działalności organu władzy publicznej; usuwany na uzasadniony sprzeciw</td></tr>
        <tr><td>Logi techniczne</td><td>do 90 dni</td></tr>
      </tbody>
    </table>

    <h2>7. Prawa osób, których dane dotyczą</h2>
    <p>Każdej osobie przysługuje prawo: dostępu do danych (art. 15), sprostowania (art. 16), usunięcia (art. 17), ograniczenia przetwarzania (art. 18), przenoszenia danych (art. 20), sprzeciwu wobec przetwarzania opartego na prawnie uzasadnionym interesie (art. 21) oraz cofnięcia zgody w dowolnym momencie (bez wpływu na zgodność z prawem przetwarzania przed cofnięciem).</p>
    <p>Żądania można kierować na <strong>biuro@lumargo.pl</strong>. Odpowiadamy w terminie do 30 dni.</p>
    <p>Każdemu przysługuje również prawo wniesienia skargi do <strong>Prezesa Urzędu Ochrony Danych Osobowych</strong> (ul. Stawki 2, 00-193 Warszawa, uodo.gov.pl).</p>

    <h2>8. Zautomatyzowane przetwarzanie i AI</h2>
    <ul>
      <li>Treści w Serwisie są automatycznie kategoryzowane i podsumowywane przez systemy AI; podsumowania oznaczamy jako wygenerowane przez AI.</li>
      <li>Asystent AI generuje odpowiedzi automatycznie — informacja o tym jest widoczna w interfejsie czatu (art. 50 AI Act).</li>
      <li>Nie podejmujemy wobec Użytkowników decyzji opartych wyłącznie na zautomatyzowanym przetwarzaniu, które wywoływałyby skutki prawne (art. 22 RODO).</li>
    </ul>

    <h2>9. Bezpieczeństwo</h2>
    <p>Stosujemy środki techniczne i organizacyjne odpowiednie do ryzyka: szyfrowanie transmisji (TLS), szyfrowanie haseł (bcrypt), kontrolę dostępu, kopie zapasowe oraz zasadę minimalizacji danych.</p>

    <h2>10. Pliki cookies</h2>
    <p>Zasady wykorzystania plików cookies i podobnych technologii opisuje{' '}
      <button onClick={() => onNavigate('cookies')} className="text-blue-400 hover:underline">Polityka cookies</button>.
    </p>

    <h2>11. Zmiany polityki</h2>
    <p>O istotnych zmianach Polityki prywatności informujemy komunikatem w Serwisie, a zarejestrowanych Użytkowników — e-mailem. Aktualna wersja jest zawsze dostępna pod adresem rybnolive.pl.</p>

  </LegalLayout>
);

export default PrivacyPage;
