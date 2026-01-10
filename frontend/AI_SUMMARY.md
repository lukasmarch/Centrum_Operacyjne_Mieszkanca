# AI Project Context: Centrum Operacyjne Mieszkańca (Frontend)

## Project Overview
**Name:** Działdowo Live - Centrum Operacyjne Mieszkańca
**Type:** Local Community Dashboard / Operations Center
**Purpose:** A centralized platform for residents to access local news, weather, events, statistics (GUS), and traffic information. Includes a premium subscription model.

## Technology Stack
- **Framework:** React 19 (Functional Components, Hooks)
- **Build Tool:** Vite
- **Styling:** Tailwind CSS (Utility-first)
- **Language:** TypeScript
- **Routing:** Internal state-based routing (`activeSection` state in `App.tsx`)
- **Icons/Fonts:** Google Fonts (Inter), standard emojis used as icons.

## File Structure
- **`App.tsx`**: Main application logic, layout (Sidebar + Main Content), top header, and section rendering switch.
- **`index.html`**: Entry HTML file (Head, Tailwind script, Fonts).
- **`types.ts`**: TypeScript definitions for domain entities.
- **`components/`**: Directory for sub-components (e.g., `Sidebar`, `Dashboard`).

## Key Features & Components

### 1. Navigation & Layout
- **Sidebar**: Left-hand navigation menu.
- **Top Header**: Search bar, notifications, and user profile snippet.
- **Footer**: Server status, API status, and legal links.

### 2. Sections (implemented in `App.tsx`)
- **Dashboard**: The default view (likely a summary of all widgets).
- **News (Wiadomości)**: Displays local news (Standard & Premium). *Currently a placeholder.*
- **Stats (GUS)**: Statistics dashboard. *Currently a placeholder.*
- **Premium**: A generic "Select Plan" page with 3 tiers (Free, Premium, Business). *Fully implemented UI.*
- **Other sections** (Events, Weather, Traffic): Handled via `default` construction or specific components.

### 3. Data Models (`types.ts`)
- **`Article`**: News items (title, summary, source, category).
- **`WeatherData`**: Weather conditions + Lake parameters (temp, level).
- **`TrafficStatus`**: Road conditions and delays.
- **`Event`**: Local events calendar.
- **`GUSStat`**: Economic/Demographic statistics.

## Technical Notes for AI Agents
- **Styling**: Use standard Tailwind CSS classes. No custom CSS files are used except for minimal global styles (glassmorphism) in `index.html`.
- **State Management**: Simple local state (`useState`) in `App.tsx` controls the active view.
- **Icons**: Currently using emojis or placeholder spans. Recommend integrating `lucide-react` or `heroicons` for a more professional look if requested.
- **Data**: Data fetching logic is not yet visible in the main files; components likely use mock data or props.

## Running the Project
- `npm install`
- `npm run dev` (Runs on port 3001 by default configuration)
