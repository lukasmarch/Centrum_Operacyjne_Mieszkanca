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

export const PRIVACY_VERSION = '2026-07-07';

const PrivacyPage: React.FC<PrivacyPageProps> = ({ onNavigate }) => (
  <LegalLayout title="Polityka prywatności" updated="7 lipca 2026">

    <h2>1. Administrator danych</h2>
    <p>Administratorem danych osobowych jest <strong>Lumargo Łukasz Marchlewicz</strong>, NIP: 571-156-78-15, adres: ul. Wyzwolenia, 13-220 Rybno (dalej: „Administrator"). Kontakt we wszystkich sprawach dotyczących danych osobowych: <strong>biuro@lumargo.pl</strong>.</p>

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
      <li><strong>CEIDG</strong> (Centralna Ewidencja i Informacja o Działalności Gospodarczej): dane przedsiębiorców — nazwa firmy, imię i nazwisko, adres wykonywania działalności, NIP, branża. Cel: prowadzenie katalogu lokalnych firm (art. 6 ust. 1 lit. f). Źródło: rejestr publiczny CEIDG.</li>
      <li><strong>Lokalne portale informacyjne, strony urzędowe i BIP</strong>: dane zawarte w publikowanych tam materiałach prasowych i urzędowych.</li>
    </ul>
    <p><strong>Prawo sprzeciwu:</strong> każda osoba, której dane pojawiają się w agregowanych treściach, może wnieść sprzeciw lub zażądać usunięcia danych, pisząc na biuro@lumargo.pl. Żądania rozpatrujemy niezwłocznie, nie później niż w 7 dni.</p>

    <h2>4. Odbiorcy danych (podmioty przetwarzające)</h2>
    <p>Dane powierzamy wyłącznie w zakresie niezbędnym do działania Serwisu:</p>
    <ul>
      <li><strong>Hetzner Online GmbH</strong> (Niemcy, UE) — hosting serwera i bazy danych,</li>
      <li><strong>OpenAI</strong> oraz <strong>Google (Gemini)</strong> — przetwarzanie zapytań do Asystenta AI i automatyczna kategoryzacja treści,</li>
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
