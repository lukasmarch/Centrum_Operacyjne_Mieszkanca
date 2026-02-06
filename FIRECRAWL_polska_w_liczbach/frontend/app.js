// Globals
let APP_DATA = null;
let CURRENT_TAB = 'overview';
const API_URL = './data.json'; // Local file for now

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    try {
        await loadData();
        setupNavigation();
        setupAI();
        renderTab(CURRENT_TAB);
    } catch (error) {
        console.error("Initialization failed:", error);
        document.getElementById('content-area').innerHTML = `
            <div class="glass-panel card" style="text-align:center; color: #f87171;">
                <h2>Błąd ładowania danych</h2>
                <p>${error.message}</p>
            </div>
        `;
    }
}

async function loadData() {
    const response = await fetch(API_URL);
    if (!response.ok) throw new Error("Failed to fetch data.json");
    const json = await response.json();
    APP_DATA = json.structured_data || json; // Handle nested structure if present

    // Update footer
    document.getElementById('last-update-date').textContent = new Date().toLocaleDateString('pl-PL');
}

function setupNavigation() {
    const tabs = document.querySelectorAll('.nav-links li');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class
            tabs.forEach(t => t.classList.remove('active'));
            // Add active class
            tab.classList.add('active');

            const tabName = tab.getAttribute('data-tab');
            CURRENT_TAB = tabName;
            renderTab(tabName);

            // Update Headers
            const titles = {
                'overview': ['Przegląd Gminy', 'Kluczowe wskaźniki rozwoju'],
                'demographics': ['Demografia', 'Struktura ludności i trendy'],
                'finance': ['Finanse', 'Budżet, dochody i wydatki'],
                'infrastructure': ['Mienie i Infrastruktura', 'Mieszkalnictwo i media'],
                'labor': ['Rynek Pracy', 'Zatrudnienie, bezrobocie i zarobki']
            };
            const [title, sub] = titles[tabName] || ['Panel', 'Statystyki'];
            document.getElementById('page-title').textContent = title;
            document.getElementById('page-subtitle').textContent = sub;
        });
    });
}

function renderTab(tabName) {
    const container = document.getElementById('content-area');
    container.innerHTML = ''; // Clear content

    const grid = document.createElement('div');
    grid.className = 'dashboard-grid';

    if (tabName === 'overview') renderOverview(grid);
    if (tabName === 'demographics') renderDemographics(grid);
    if (tabName === 'finance') renderFinance(grid);
    if (tabName === 'infrastructure') renderInfrastructure(grid);
    if (tabName === 'labor') renderLabor(grid);

    container.appendChild(grid);
}

// --- Render Functions ---

function renderOverview(grid) {
    // Basic Info Cards
    const basic = APP_DATA.basic_info;
    const demo = APP_DATA.demographics;
    const fin = APP_DATA.finance;

    createCard(grid, 'Populacja', demo.population_total.toLocaleString(), 'fa-users', 'Mieszkańców');
    createCard(grid, 'Powierzchnia', `${basic.area_km2} km²`, 'fa-map', 'Obszar');
    createCard(grid, 'Budżet (Wydatki)', `${fin.budget_expenditure_mln} mln zł`, 'fa-coins', '2024');
    createCard(grid, 'Bezrobocie', `${APP_DATA.labor_market.unemployment_rate}%`, 'fa-briefcase', 'Stopa bezrobocia');

    // Budget History Chart
    createChartCard(grid, 'Historia Budżetu (mln zł)', 'usageChart');
    setTimeout(() => {
        if (fin.budget_history && fin.budget_history.length > 0) {
            const labels = fin.budget_history.map(h => h.year);
            const inc = fin.budget_history.map(h => h.income);
            const exp = fin.budget_history.map(h => h.expenditure);

            initChart('usageChart', 'line', labels, [
                { label: 'Dochody', data: inc, borderColor: '#4ade80', backgroundColor: 'rgba(74, 222, 128, 0.2)' },
                { label: 'Wydatki', data: exp, borderColor: '#f87171', backgroundColor: 'rgba(248, 113, 113, 0.2)' }
            ]);
        }
    }, 100);
}

function renderDemographics(grid) {
    const d = APP_DATA.demographics;
    createCard(grid, 'Kobiety', d.women_count, 'fa-venus', `${d.women_percentage}%`);
    createCard(grid, 'Mężczyźni', d.men_count, 'fa-mars', `${d.men_percentage}%`);
    createCard(grid, 'Średni Wiek', d.average_age, 'fa-hourglass-half', 'Lat');
    createCard(grid, 'Przyrost Nat.', d.natural_growth, 'fa-baby', '2023');

    // Population Pyramid Stub (since we don't have full buckets, just simple age groups if avail)
    // We have percentages: pre_working, working, post_working
    createChartCard(grid, 'Ekonomiczne Grupy Wieku', 'ageChart');
    setTimeout(() => {
        initChart('ageChart', 'doughnut', ['Przedprodukcyjny', 'Produkcyjny', 'Poprodukcyjny'], [{
            data: [d.pre_working_age_percentage, d.working_age_percentage, d.post_working_age_percentage],
            backgroundColor: ['#38bdf8', '#4ade80', '#f472b6']
        }]);
    }, 100);
}

function renderFinance(grid) {
    const f = APP_DATA.finance;
    createCard(grid, 'Dochody Ogółem', `${f.budget_income_mln} mln`, 'fa-arrow-up', 'PLN');
    createCard(grid, 'Wydatki Ogółem', `${f.budget_expenditure_mln} mln`, 'fa-arrow-down', 'PLN');
    createCard(grid, 'Dochód na osobę', `${f.income_per_capita} zł`, 'fa-wallet', 'Per Capita');
    createCard(grid, 'Inwestycje', `${f.investment_pct}%`, 'fa-hammer', 'Wydatków');

    createChartCard(grid, 'Struktura Wydatków (%)', 'expChart');
    setTimeout(() => {
        const labels = ['Oświata', 'Transport', 'Administracja'];
        const data = [f.education_expenditure_pct, f.transport_expenditure_pct, f.admin_expenditure_pct];
        initChart('expChart', 'bar', labels, [{
            label: 'Udział %',
            data: data,
            backgroundColor: ['#fbbf24', '#f87171', '#a78bfa']
        }]);
    }, 100);

    // Main Budget History Chart (Income vs Expenditure)
    if (f.budget_history && f.budget_history.length > 0) {
        createChartCard(grid, 'Budżet Historyczny (PLN)', 'historyChart');
        setTimeout(() => {
            const h = f.budget_history.filter(x => x.income > 0 || x.expenditure > 0);
            const years = h.map(x => x.year);
            const inc = h.map(x => x.income);
            const exp = h.map(x => x.expenditure);

            initChart('historyChart', 'bar', years, [
                { label: 'Dochody', data: inc, backgroundColor: '#22c55e' }, // Green
                { label: 'Wydatki', data: exp, backgroundColor: '#ef4444' }  // Red
            ]);
        }, 150);
    }

    // Detailed History Chart (Top 5 Departments)
    if (f.budget_expenditure_details && f.budget_expenditure_details.length > 0) {
        createChartCard(grid, 'Top 5 Działów - Trend Wydatków (PLN)', 'topDeptChart');
        setTimeout(() => {
            const depts = f.budget_expenditure_details;
            const years = ['2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024'];

            // Helper: get value for year
            const getVal = (dept, year) => {
                // Try string match or int match
                const h = dept.history.find(x => String(x.year).split('.')[0] === String(year));
                return h ? h.value : 0;
            };

            // Sort by 2024 value descending
            const sorted = [...depts].sort((a, b) => getVal(b, 2024) - getVal(a, 2024));
            const top5 = sorted.slice(0, 5);

            const datasets = top5.map((d, i) => ({
                label: d.name.replace(/<br>.*$/, ''), // Clean name from br/code
                data: years.map(y => getVal(d, y)),
                borderColor: `hsl(${i * 45 + 180}, 80%, 60%)`, // Dynamic colors
                backgroundColor: 'transparent',
                borderWidth: 2
            }));

            initChart('topDeptChart', 'line', years, datasets);
        }, 200);
    }

    // Detailed Income History Chart (Top 5 Sources)
    if (f.budget_income_details && f.budget_income_details.length > 0) {
        createChartCard(grid, 'Top 5 Źródeł Dochodu (PLN)', 'topIncomeChart');
        setTimeout(() => {
            const depts = f.budget_income_details;
            const years = ['2018', '2019', '2020', '2021', '2022', '2023']; // 2017/24 might be sparse

            const getVal = (dept, year) => {
                const h = dept.history.find(x => String(x.year).split('.')[0] === String(year));
                return h ? h.value : 0;
            };

            // Sort by 2023 value descending
            const sorted = [...depts].sort((a, b) => getVal(b, 2023) - getVal(a, 2023));
            const top5 = sorted.slice(0, 5);

            const datasets = top5.map((d, i) => ({
                label: d.name.replace(/<br>.*$/, ''),
                data: years.map(y => getVal(d, y)),
                borderColor: `hsl(${i * 45}, 80%, 60%)`,
                backgroundColor: 'transparent',
                borderWidth: 2
            }));

            initChart('topIncomeChart', 'line', years, datasets);
        }, 250);
    }
}

function renderInfrastructure(grid) {
    const r = APP_DATA.real_estate;
    createCard(grid, 'Mieszkania', r.total_apartments, 'fa-home', 'Ogółem');
    createCard(grid, 'Pow. Użytkowa', `${r.avg_area_m2} m²`, 'fa-ruler-combined', 'Średnia');
    createCard(grid, 'Wodociągi', `${r.water_supply_pct}%`, 'fa-faucet', 'Dostęp');
    createCard(grid, 'Kanalizacja', `${r.bathroom_pct}%`, 'fa-toilet', 'Łazienka'); // bathroom_pct as proxy if needed
}

function renderLabor(grid) {
    const l = APP_DATA.labor_market;
    createCard(grid, 'Bezrobocie', `${l.unemployment_rate}%`, 'fa-chart-line', 'Stopa');
    createCard(grid, 'Pracujący', l.employed_total, 'fa-users-cog', 'Ogółem');
    createCard(grid, 'Zarobki', `${l.salary_gross_pln} zł`, 'fa-money-bill-wave', 'Brutto');
    createCard(grid, 'Vs Polska', `${l.salary_vs_poland_pct}%`, 'fa-balance-scale', 'Średniej Krajowej');

    createChartCard(grid, 'Zatrudnienie wg Sektorów', 'sectorChart');
    setTimeout(() => {
        initChart('sectorChart', 'pie', ['Rolnictwo', 'Przemysł', 'Usługi', 'Finanse'], [{
            data: [l.sector_agriculture_pct, l.sector_industry_pct, l.sector_services_pct, l.sector_finance_pct],
            backgroundColor: ['#4ade80', '#60a5fa', '#f472b6', '#fbbf24']
        }]);
    }, 100);
}

// --- Helpers ---

function createCard(grid, title, value, iconClass, trendText) {
    const card = document.createElement('div');
    card.className = 'card glass-panel';
    card.innerHTML = `
        <div class="card-header">
            <span class="card-title">${title}</span>
            <i class="card-icon fa-solid ${iconClass}"></i>
        </div>
        <div class="card-value">${value || '-'}</div>
        <div class="card-trend trend-neutral">
            <i class="fa-solid fa-minus"></i>
            <span>${trendText}</span>
        </div>
    `;
    grid.appendChild(card);
}

function createChartCard(grid, title, canvasId) {
    const card = document.createElement('div');
    card.className = 'card glass-panel chart-card';
    card.innerHTML = `
        <div class="card-header">
            <span class="card-title">${title}</span>
        </div>
        <div class="chart-container" style="position: relative; height: 300px; width:100%">
            <canvas id="${canvasId}"></canvas>
        </div>
    `;
    grid.appendChild(card);
}

function initChart(canvasId, type, labels, datasets) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: datasets.map(d => ({
                ...d,
                borderWidth: 2,
                tension: 0.4
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#94a3b8' } }
            },
            scales: type !== 'doughnut' && type !== 'pie' ? {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            } : {}
        }
    });
}

function setupAI() {
    const btn = document.getElementById('ask-ai-btn');
    const modal = document.getElementById('ai-modal');
    const close = document.querySelector('.close-modal');
    const responseText = document.getElementById('ai-response-text');

    btn.onclick = async () => {
        modal.style.display = 'flex';
        responseText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generowanie analizy...';

        // Mock Response for now (or call real API if configured)
        setTimeout(() => {
            const context1 = `Analiza dla: ${CURRENT_TAB.toUpperCase()}. `;
            const text = generateMockInsight(CURRENT_TAB);
            responseText.innerHTML = `<strong>${context1}</strong><br><br>${text}`;
        }, 1500);
    };

    close.onclick = () => modal.style.display = 'none';
    window.onclick = (e) => {
        if (e.target == modal) modal.style.display = 'none';
    };
}

function generateMockInsight(tab) {
    const insights = {
        overview: "Gmina wykazuje stabilny wzrost budżetowy przy jednoczesnym wyzwaniu demograficznym (ujemny przyrost naturalny). Wydatki inwestycyjne są na umiarkowanym poziomie. Infrastruktura wodno-kanalizacyjna jest bardzo dobrze rozwinięta.",
        demographics: "Zauważalna przewaga liczby mężczyzn nad kobietami w strukturze ogólnej, co jest nietypowe dla średniej krajowej. Społeczeństwo starzeje się, na co wskazuje rosnący udział grupy poprodukcyjnej.",
        finance: "Budżet gminy stabilnie rośnie roku do roku. Największym obciążeniem są wydatki oświatowe i administracyjne. W 2024 roku zaplanowano rekordowe wydatki (62 mln zł), co może świadczyć o nowych inwestycjach.",
        infrastructure: "Bardzo wysoki wskaźnik dostępności wodociągów (97%) i kanalizacji (>90%) stawia gminę w czołówce regionu. Nowe budownictwo mieszkaniowe rozwija się powoli.",
        labor: "Bezrobocie na poziomie 12.4% jest wyższe od średniej krajowej, ale typowe dla regionu warmińsko-mazurskiego. Dominacja rolnictwa w strukturze zatrudnienia jest wyraźna."
    };
    return insights[tab] || "Brak danych do analizy dla tej sekcji.";
}
