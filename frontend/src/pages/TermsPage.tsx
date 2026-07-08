/**
 * Regulamin świadczenia usług drogą elektroniczną (art. 8 UŚUDE)
 *
 * ⚠️ WERSJA ROBOCZA — przed publikacją na produkcji wymaga weryfikacji
 * przez radcę prawnego / adwokata.
 */

import React from 'react';
import LegalLayout from '../../components/LegalLayout';
import { AppSection } from '../../types';

interface TermsPageProps {
  onNavigate: (section: AppSection) => void;
}

export const TERMS_VERSION = '2026-07-07';

const TermsPage: React.FC<TermsPageProps> = ({ onNavigate }) => (
  <LegalLayout title="Regulamin serwisu RybnoLive.pl" updated="7 lipca 2026">

    <h2>§ 1. Postanowienia ogólne</h2>
    <ol>
      <li>Niniejszy Regulamin określa zasady świadczenia usług drogą elektroniczną w serwisie internetowym <strong>RybnoLive.pl — Centrum Operacyjne Mieszkańca</strong> (dalej: „Serwis"), dostępnym pod adresem https://rybnolive.pl.</li>
      <li>Operatorem Serwisu jest <strong>Lumargo Łukasz Marchlewicz</strong>, NIP: 571-100-100, adres: ul. Wyzwolenia, 13-220 Rybno (dalej: „Operator"). Kontakt: <strong>biuro@lumargo.pl</strong>.</li>
      <li>Regulamin jest regulaminem, o którym mowa w art. 8 ustawy z dnia 18 lipca 2002 r. o świadczeniu usług drogą elektroniczną.</li>
      <li>Korzystanie z Serwisu oznacza akceptację Regulaminu. Rejestracja konta wymaga wyraźnej akceptacji Regulaminu oraz zapoznania się z Polityką prywatności.</li>
    </ol>

    <h2>§ 2. Definicje</h2>
    <ul>
      <li><strong>Użytkownik</strong> — osoba fizyczna korzystająca z Serwisu, w tym Konsument w rozumieniu art. 22¹ Kodeksu cywilnego.</li>
      <li><strong>Konto</strong> — zbiór zasobów i uprawnień przypisanych Użytkownikowi po rejestracji.</li>
      <li><strong>Plan płatny</strong> — odpłatny pakiet usług (Premium lub wyższy) opisany w cenniku dostępnym w Serwisie.</li>
      <li><strong>Asystent AI</strong> — funkcja Serwisu generująca odpowiedzi przy użyciu systemów sztucznej inteligencji.</li>
      <li><strong>Treści cyfrowe</strong> — usługi i treści dostarczane drogą elektroniczną w ramach Serwisu.</li>
    </ul>

    <h2>§ 3. Rodzaj i zakres usług</h2>
    <ol>
      <li>Serwis jest lokalnym portalem informacyjnym dla mieszkańców Gminy Rybno i okolic, oferującym w szczególności:
        <ul>
          <li>agregację i prezentację lokalnych wiadomości ze wskazaniem źródeł,</li>
          <li>informacje pogodowe, o jakości powietrza i utrudnieniach drogowych,</li>
          <li>harmonogram wywozu odpadów,</li>
          <li>Asystenta AI odpowiadającego na pytania o sprawy lokalne,</li>
          <li>moduł zgłoszeń mieszkańców,</li>
          <li>newsletter, powiadomienia push, dane statystyczne (GUS) oraz katalog lokalnych firm (CEIDG).</li>
        </ul>
      </li>
      <li>Część funkcji dostępna jest bezpłatnie, część w ramach Planów płatnych zgodnie z cennikiem.</li>
      <li>Po rejestracji Użytkownik otrzymuje bezpłatny, <strong>7-dniowy okres próbny planu Premium</strong>. Okres próbny nie wymaga podania danych płatniczych i nie przekształca się automatycznie w płatną subskrypcję — po jego zakończeniu Konto wraca do planu bezpłatnego.</li>
    </ol>

    <h2>§ 4. Wymagania techniczne</h2>
    <p>Do korzystania z Serwisu niezbędne są: urządzenie z dostępem do Internetu, aktualna przeglądarka internetowa z obsługą JavaScript i plików cookies oraz — dla wybranych funkcji (konto, newsletter) — aktywny adres e-mail. Powiadomienia push wymagają zgody wyrażonej w przeglądarce.</p>

    <h2>§ 5. Rejestracja i konto</h2>
    <ol>
      <li>Rejestracja wymaga podania adresu e-mail, imienia i nazwiska (lub pseudonimu), hasła oraz opcjonalnie miejscowości.</li>
      <li>Użytkownik zobowiązuje się do podawania danych prawdziwych i nienaruszających praw osób trzecich.</li>
      <li>Zakazane jest dostarczanie treści o charakterze bezprawnym (art. 8 ust. 3 pkt 2 lit. b UŚUDE).</li>
      <li>Użytkownik może w każdej chwili usunąć Konto — samodzielnie w ustawieniach profilu lub kontaktując się z Operatorem. Usunięcie Konta jest nieodwracalne.</li>
      <li>Operator może zawiesić lub usunąć Konto naruszające Regulamin, po uprzednim wezwaniu do zaniechania naruszeń, chyba że naruszenie jest rażące.</li>
    </ol>

    <h2>§ 6. Plany płatne i płatności</h2>
    <ol>
      <li>Aktualne ceny Planów płatnych oraz zakres funkcji określa cennik prezentowany w Serwisie przed zawarciem umowy.</li>
      <li>Płatności obsługuje <strong>PayPro S.A. (Przelewy24)</strong>. Operator nie przechowuje danych kart płatniczych.</li>
      <li>Opłata pobierana jest z góry za wybrany okres rozliczeniowy (miesięczny lub roczny). Plan płatny <strong>nie odnawia się automatycznie</strong> — przedłużenie wymaga ponownej płatności.</li>
      <li>Ceny są cenami brutto, wyrażonymi w złotych polskich (PLN).</li>
      <li>Bezpośrednio przed dokonaniem płatności Użytkownik jest informowany o łącznej cenie i potwierdza zamówienie przyciskiem oznaczonym jako wiążące się z obowiązkiem zapłaty.</li>
      <li>Na życzenie Użytkownika Operator wystawia fakturę na dane wskazane przez Użytkownika.</li>
    </ol>

    <h2>§ 7. Prawo odstąpienia od umowy (Konsumenci)</h2>
    <ol>
      <li>Konsument ma prawo odstąpić od umowy o dostarczanie Treści cyfrowych w terminie <strong>14 dni</strong> od jej zawarcia, bez podania przyczyny, składając oświadczenie (np. e-mailem na biuro@lumargo.pl).</li>
      <li>Jeżeli Konsument zażąda rozpoczęcia świadczenia usługi (aktywacji Planu płatnego) przed upływem terminu odstąpienia i przyjmie do wiadomości, że utraci w ten sposób prawo odstąpienia (art. 38 ust. 1 pkt 13 ustawy o prawach konsumenta), prawo odstąpienia nie przysługuje po pełnym wykonaniu usługi; w przypadku usług ciągłych Konsument, który odstąpi od umowy, otrzymuje zwrot proporcjonalny do niewykorzystanego okresu.</li>
      <li>Zwrot płatności następuje niezwłocznie, nie później niż w terminie 14 dni od otrzymania oświadczenia, tym samym kanałem płatności.</li>
    </ol>

    <h2>§ 8. Asystent AI — zastrzeżenia</h2>
    <ol>
      <li>Odpowiedzi Asystenta AI są <strong>generowane automatycznie przez systemy sztucznej inteligencji</strong>. Użytkownik jest o tym informowany w interfejsie czatu (art. 50 rozporządzenia UE 2024/1689 — AI Act).</li>
      <li>Odpowiedzi AI mogą zawierać błędy, nieścisłości lub nieaktualne informacje. <strong>Nie stanowią porady prawnej, medycznej, finansowej ani urzędowej</strong> i nie zastępują informacji uzyskanej we właściwym urzędzie lub u specjalisty.</li>
      <li>Automatycznie generowane podsumowania wiadomości są oznaczane jako treści wytworzone przez AI.</li>
      <li>Operator dokłada starań, by odpowiedzi opierały się na zweryfikowanych lokalnych źródłach, których lista (odnośniki) prezentowana jest przy odpowiedzi.</li>
    </ol>

    <h2>§ 9. Zgłoszenia mieszkańców</h2>
    <ol>
      <li>Moduł zgłoszeń służy do informowania o lokalnych problemach (awarie, uszkodzenia infrastruktury, zagrożenia).</li>
      <li>Zabronione jest zamieszczanie w zgłoszeniach (w tym na zdjęciach): wizerunku osób trzecich bez ich zgody, czytelnych tablic rejestracyjnych, danych osobowych osób trzecich oraz treści bezprawnych lub obraźliwych.</li>
      <li>Zgłoszenia mogą podlegać moderacji. Operator może odmówić publikacji lub usunąć zgłoszenie naruszające Regulamin.</li>
    </ol>

    <h2>§ 10. Treści, prawa autorskie i agregacja</h2>
    <ol>
      <li>Serwis agreguje informacje z publicznie dostępnych źródeł lokalnych (portale informacyjne, strony urzędowe, BIP, media społecznościowe), zawsze ze wskazaniem źródła i odnośnikiem do oryginału.</li>
      <li>Prawa do treści źródłowych przysługują ich autorom i wydawcom. Serwis prezentuje skróty informacji z odesłaniem do pełnej treści u źródła.</li>
      <li><strong>Procedura zgłaszania naruszeń (notice-and-takedown):</strong> podmiot, którego prawa zostały naruszone przez treść prezentowaną w Serwisie (w tym osoba, której dane osobowe lub wizerunek dotyczą), może zgłosić żądanie usunięcia na adres biuro@lumargo.pl. Operator rozpatruje zgłoszenia niezwłocznie, nie później niż w terminie 7 dni, i w uzasadnionych przypadkach usuwa lub anonimizuje treść.</li>
      <li>Układ Serwisu, oprogramowanie oraz treści własne Operatora podlegają ochronie prawnoautorskiej.</li>
    </ol>

    <h2>§ 11. Reklamacje</h2>
    <ol>
      <li>Reklamacje dotyczące działania Serwisu można składać e-mailem na adres biuro@lumargo.pl.</li>
      <li>Reklamacja powinna zawierać: adres e-mail Użytkownika, opis problemu oraz oczekiwany sposób rozstrzygnięcia.</li>
      <li>Operator rozpatruje reklamacje w terminie <strong>14 dni</strong> od otrzymania i odpowiada na adres e-mail zgłaszającego.</li>
    </ol>

    <h2>§ 12. Odpowiedzialność</h2>
    <ol>
      <li>Operator dokłada starań, aby informacje w Serwisie były aktualne i rzetelne, jednak — z uwagi na ich agregacyjny i automatyczny charakter — nie gwarantuje ich kompletności ani nieprzerwanej dostępności Serwisu.</li>
      <li>Informacje o zagrożeniach (pogoda, awarie, utrudnienia) mają charakter pomocniczy i nie zastępują oficjalnych komunikatów właściwych służb.</li>
      <li>Postanowienia Regulaminu nie wyłączają ani nie ograniczają praw Konsumenta wynikających z przepisów bezwzględnie obowiązujących.</li>
    </ol>

    <h2>§ 13. Dane osobowe</h2>
    <p>Zasady przetwarzania danych osobowych oraz prawa osób, których dane dotyczą, opisuje{' '}
      <button onClick={() => onNavigate('privacy')} className="text-blue-400 hover:underline">Polityka prywatności</button>.
      Zasady wykorzystania plików cookies opisuje{' '}
      <button onClick={() => onNavigate('cookies')} className="text-blue-400 hover:underline">Polityka cookies</button>.
    </p>

    <h2>§ 14. Postanowienia końcowe</h2>
    <ol>
      <li>Operator może zmienić Regulamin z ważnych przyczyn (zmiana przepisów, zakresu usług, względy bezpieczeństwa). O zmianach Użytkownicy zarejestrowani są informowani e-mailem lub komunikatem w Serwisie z co najmniej 14-dniowym wyprzedzeniem. Dalsze korzystanie z Serwisu po wejściu zmian w życie oznacza ich akceptację; Użytkownik może wypowiedzieć umowę usuwając Konto.</li>
      <li>Prawem właściwym jest prawo polskie. Spory z Konsumentami rozstrzygają sądy powszechne właściwe według przepisów ogólnych.</li>
      <li>Konsument może skorzystać z pozasądowych sposobów rozpatrywania reklamacji i dochodzenia roszczeń, m.in. z pomocy powiatowego (miejskiego) rzecznika konsumentów lub platformy ODR (https://ec.europa.eu/consumers/odr).</li>
      <li>Regulamin obowiązuje od dnia 7 lipca 2026 r.</li>
    </ol>

  </LegalLayout>
);

export default TermsPage;
