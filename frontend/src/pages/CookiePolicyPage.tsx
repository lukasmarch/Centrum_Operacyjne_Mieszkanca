/**
 * Polityka cookies (Prawo komunikacji elektronicznej)
 *
 * ⚠️ WERSJA ROBOCZA — przed publikacją na produkcji wymaga weryfikacji
 * przez radcę prawnego / adwokata.
 */

import React from 'react';
import LegalLayout from '../../components/LegalLayout';
import { AppSection } from '../../types';
import { resetCookieConsent } from '../../components/CookieConsent';

interface CookiePolicyPageProps {
  onNavigate: (section: AppSection) => void;
}

const CookiePolicyPage: React.FC<CookiePolicyPageProps> = ({ onNavigate }) => (
  <LegalLayout title="Polityka cookies" updated="7 lipca 2026">

    <h2>1. Czym są pliki cookies</h2>
    <p>Pliki cookies to niewielkie pliki tekstowe zapisywane na urządzeniu Użytkownika podczas korzystania z Serwisu. Wykorzystujemy również podobne technologie: <strong>localStorage</strong> (pamięć przeglądarki) oraz — po wyrażeniu odrębnej zgody w przeglądarce — powiadomienia push.</p>
    <p>Zgodnie z ustawą Prawo komunikacji elektronicznej przechowywanie informacji lub uzyskiwanie dostępu do informacji już przechowywanej na urządzeniu (cookies inne niż niezbędne) wymaga zgody Użytkownika.</p>

    <h2>2. Jakie cookies i technologie stosujemy</h2>
    <table>
      <thead>
        <tr><th>Nazwa</th><th>Rodzaj</th><th>Cel</th><th>Czas życia</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>access_token</td>
          <td>niezbędny (cookie)</td>
          <td>utrzymanie zalogowanej sesji Użytkownika</td>
          <td>8 godzin</td>
        </tr>
        <tr>
          <td>refresh_token</td>
          <td>niezbędny (cookie)</td>
          <td>odnowienie sesji bez ponownego logowania</td>
          <td>7 dni</td>
        </tr>
        <tr>
          <td>cookie_consent_v1</td>
          <td>niezbędny (localStorage)</td>
          <td>zapamiętanie decyzji Użytkownika dot. cookies</td>
          <td>12 miesięcy</td>
        </tr>
        <tr>
          <td>ustawienia interfejsu</td>
          <td>funkcjonalny (localStorage)</td>
          <td>preferencje wyglądu i układu (np. układ dashboardu)</td>
          <td>do usunięcia przez Użytkownika</td>
        </tr>
        <tr>
          <td>rl_sid</td>
          <td>niezbędny (sessionStorage)</td>
          <td>losowy identyfikator jednej wizyty; pozwala policzyć, ile podstron obejrzano w ramach jednego wejścia</td>
          <td>do zamknięcia karty przeglądarki</td>
        </tr>
        <tr>
          <td>rl_acq</td>
          <td>funkcjonalny (localStorage)</td>
          <td>adres, z którego Użytkownik trafił do Serwisu (znaczniki kampanii), aby ocenić skuteczność własnych publikacji</td>
          <td>do usunięcia przez Użytkownika</td>
        </tr>
      </tbody>
    </table>
    <p><strong>Serwis nie stosuje obecnie cookies analitycznych ani marketingowych</strong> i nie osadza zewnętrznych skryptów śledzących — statystyki odwiedzin prowadzimy wyłącznie we własnej infrastrukturze, bez profilowania i bez przekazywania danych podmiotom trzecim. Nie zapisujemy przy tym adresu IP ani pełnego identyfikatora przeglądarki (User-Agent); identyfikator wizyty <code>rl_sid</code> jest usuwany po 90 dniach, a cały zapis zdarzenia po 180 dniach. Jeżeli kiedykolwiek uruchomimy narzędzia zewnętrzne, nastąpi to wyłącznie po uzyskaniu zgody poprzez baner cookies, a niniejsza polityka zostanie zaktualizowana.</p>

    <h2>3. Cookies niezbędne — bez zgody</h2>
    <p>Cookies niezbędne do świadczenia usługi (sesja zalogowanego Użytkownika, zapamiętanie decyzji o zgodzie) nie wymagają zgody — ich stosowanie jest konieczne do wykonania usługi, której żąda Użytkownik.</p>

    <h2>4. Zarządzanie zgodą</h2>
    <ul>
      <li>Decyzję wyrażoną w banerze cookies można zmienić w każdej chwili —{' '}
        <button
          onClick={() => { resetCookieConsent(); window.location.reload(); }}
          className="text-blue-400 hover:underline"
        >
          kliknij tutaj, aby ponownie wyświetlić baner
        </button>.
      </li>
      <li>Cookies można też usuwać i blokować w ustawieniach przeglądarki (Chrome, Firefox, Safari, Edge — sekcja „Prywatność"). Zablokowanie cookies niezbędnych może uniemożliwić logowanie.</li>
    </ul>

    <h2>5. Powiązane dokumenty</h2>
    <p>Zasady przetwarzania danych osobowych opisuje{' '}
      <button onClick={() => onNavigate('privacy')} className="text-blue-400 hover:underline">Polityka prywatności</button>,
      a zasady świadczenia usług —{' '}
      <button onClick={() => onNavigate('terms')} className="text-blue-400 hover:underline">Regulamin</button>.
    </p>

  </LegalLayout>
);

export default CookiePolicyPage;
