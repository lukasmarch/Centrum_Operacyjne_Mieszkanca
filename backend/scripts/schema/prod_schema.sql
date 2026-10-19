-- Struktura bazy PRODUKCYJNEJ (pg_dump -s, bez danych) — plik GENEROWANY, nie edytuj ręcznie.
-- Odśwież: bash scripts/db_schema_refresh.sh   |   porównaj z produkcją: ... --check
-- Pilnuje go backend/scripts/test_schema_contract.py (CI). Opis: CLAUDE.md, „Wyrównanie baz”.
--
-- PostgreSQL database dump
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger;


--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger_data;


--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA topology;


--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: update_search_vector(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_search_vector() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', unaccent(NEW.chunk_text));
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_tool_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_tool_calls (
    id integer NOT NULL,
    agent_name character varying(50) NOT NULL,
    tool_name character varying(60) NOT NULL,
    state character varying(20) NOT NULL,
    error character varying(30),
    args jsonb,
    duration_ms integer DEFAULT 0 NOT NULL,
    question character varying(200),
    user_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: agent_tool_calls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_tool_calls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_tool_calls_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_tool_calls_id_seq OWNED BY public.agent_tool_calls.id;


--
-- Name: air_quality; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.air_quality (
    id integer NOT NULL,
    location character varying NOT NULL,
    pm25 double precision NOT NULL,
    pm10 double precision NOT NULL,
    caqi double precision NOT NULL,
    caqi_level character varying NOT NULL,
    temperature double precision,
    humidity double precision,
    pressure double precision,
    fetched_at timestamp without time zone NOT NULL,
    is_current boolean NOT NULL
);


--
-- Name: air_quality_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.air_quality_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: air_quality_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.air_quality_id_seq OWNED BY public.air_quality.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: anonymous_chat_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.anonymous_chat_usage (
    id integer NOT NULL,
    ip_address text NOT NULL,
    usage_date date NOT NULL,
    count integer DEFAULT 0
);


--
-- Name: anonymous_chat_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.anonymous_chat_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: anonymous_chat_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.anonymous_chat_usage_id_seq OWNED BY public.anonymous_chat_usage.id;


--
-- Name: api_cost_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_cost_log (
    id integer NOT NULL,
    service character varying(50) NOT NULL,
    model character varying(100) NOT NULL,
    tokens_input integer DEFAULT 0,
    tokens_output integer DEFAULT 0,
    estimated_cost_usd double precision DEFAULT 0,
    endpoint character varying(100),
    user_id integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: api_cost_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_cost_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_cost_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_cost_log_id_seq OWNED BY public.api_cost_log.id;


--
-- Name: articles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.articles (
    id integer NOT NULL,
    source_id integer NOT NULL,
    external_id character varying,
    title character varying NOT NULL,
    content character varying,
    summary character varying,
    url character varying NOT NULL,
    image_url character varying,
    author character varying,
    published_at timestamp without time zone,
    scraped_at timestamp without time zone NOT NULL,
    category character varying,
    tags character varying[],
    location_mentioned character varying[],
    processed boolean NOT NULL,
    embedded boolean DEFAULT false,
    display_title character varying(200),
    is_filler boolean DEFAULT false NOT NULL,
    is_promotional boolean DEFAULT false NOT NULL,
    event_at timestamp without time zone,
    event_until timestamp without time zone,
    alert_pushed_at timestamp without time zone,
    content_score smallint,
    locality smallint,
    event_checked_at timestamp without time zone,
    story_id integer,
    story_checked_at timestamp without time zone,
    withdrawn_at timestamp without time zone,
    term_corrected_at timestamp without time zone
);


--
-- Name: articles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.articles_id_seq OWNED BY public.articles.id;


--
-- Name: bip_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bip_documents (
    id integer NOT NULL,
    section_id character varying(20) NOT NULL,
    section_name character varying(200) NOT NULL,
    url character varying(1000) NOT NULL,
    title character varying(500) NOT NULL,
    content text,
    content_hash character varying(64) NOT NULL,
    pdf_count integer DEFAULT 0 NOT NULL,
    document_date timestamp without time zone,
    embedded boolean DEFAULT false NOT NULL,
    first_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    last_checked_at timestamp without time zone DEFAULT now() NOT NULL,
    content_changed_at timestamp without time zone
);


--
-- Name: bip_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bip_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bip_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bip_documents_id_seq OWNED BY public.bip_documents.id;


--
-- Name: bus_stop_times; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bus_stop_times (
    id integer NOT NULL,
    trip_id integer NOT NULL,
    stop_id character varying(50) NOT NULL,
    stop_sequence integer NOT NULL,
    arrival_time character varying(5) NOT NULL
);


--
-- Name: bus_stop_times_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bus_stop_times_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bus_stop_times_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bus_stop_times_id_seq OWNED BY public.bus_stop_times.id;


--
-- Name: bus_stops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bus_stops (
    id integer NOT NULL,
    stop_id character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    lat double precision NOT NULL,
    lng double precision NOT NULL,
    sequence integer NOT NULL
);


--
-- Name: bus_stops_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bus_stops_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bus_stops_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bus_stops_id_seq OWNED BY public.bus_stops.id;


--
-- Name: bus_trips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bus_trips (
    id integer NOT NULL,
    direction character varying(30) NOT NULL,
    departure_time character varying(5) NOT NULL,
    service_type character varying(2) NOT NULL
);


--
-- Name: bus_trips_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bus_trips_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bus_trips_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bus_trips_id_seq OWNED BY public.bus_trips.id;


--
-- Name: business_announcements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_announcements (
    id integer NOT NULL,
    business_id integer NOT NULL,
    type character varying(20) DEFAULT 'ogloszenie'::character varying NOT NULL,
    title character varying(120) NOT NULL,
    body character varying(500) NOT NULL,
    valid_until timestamp without time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: business_announcements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_announcements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_announcements_id_seq OWNED BY public.business_announcements.id;


--
-- Name: business_claim_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_claim_log (
    id integer NOT NULL,
    business_id integer NOT NULL,
    user_id integer NOT NULL,
    action character varying(20) NOT NULL,
    business_name character varying(300) NOT NULL,
    admin_email character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: business_claim_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_claim_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_claim_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_claim_log_id_seq OWNED BY public.business_claim_log.id;


--
-- Name: business_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_profiles (
    id integer NOT NULL,
    business_id integer NOT NULL,
    user_id integer NOT NULL,
    claim_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    claim_note character varying(500),
    description character varying(600),
    telefon character varying(50),
    email character varying(255),
    www character varying(500),
    godziny character varying(200),
    logo_url character varying(500),
    is_premium boolean DEFAULT false NOT NULL,
    premium_until timestamp without time zone,
    views_count integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    verified_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    views_last_report integer DEFAULT 0 NOT NULL,
    impressions_count integer DEFAULT 0 NOT NULL,
    impressions_last_report integer DEFAULT 0 NOT NULL
);


--
-- Name: business_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_profiles_id_seq OWNED BY public.business_profiles.id;


--
-- Name: ceidg_businesses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ceidg_businesses (
    id integer NOT NULL,
    ceidg_id character varying(50) NOT NULL,
    nazwa character varying(500) NOT NULL,
    nip character varying(20) NOT NULL,
    regon character varying(20),
    status character varying(60) NOT NULL,
    data_rozpoczecia timestamp without time zone,
    wlasciciel_imie character varying(100),
    wlasciciel_nazwisko character varying(100),
    ulica character varying(200),
    budynek character varying(20),
    lokal character varying(20),
    miasto character varying(100) NOT NULL,
    kod_pocztowy character varying(10) NOT NULL,
    gmina character varying(100) NOT NULL,
    powiat character varying(100) NOT NULL,
    wojewodztwo character varying(100),
    raw_data jsonb,
    ceidg_link character varying(500),
    fetched_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    pkd_main character varying,
    pkd_list jsonb,
    adres_korespondencyjny jsonb,
    spolki jsonb,
    obywatelstwa jsonb,
    email character varying,
    www character varying,
    telefon character varying,
    opted_out boolean DEFAULT false NOT NULL,
    previous_status character varying(60),
    status_changed_at timestamp without time zone,
    source character varying(20) DEFAULT 'ceidg'::character varying NOT NULL
);


--
-- Name: ceidg_businesses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ceidg_businesses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ceidg_businesses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ceidg_businesses_id_seq OWNED BY public.ceidg_businesses.id;


--
-- Name: ceidg_sync_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ceidg_sync_stats (
    id integer NOT NULL,
    gmina character varying(100) NOT NULL,
    powiat character varying(100) NOT NULL,
    total_count integer NOT NULL,
    active_count integer NOT NULL,
    by_miejscowosc jsonb,
    last_sync timestamp without time zone NOT NULL,
    sync_status character varying(20) NOT NULL
);


--
-- Name: ceidg_sync_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ceidg_sync_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ceidg_sync_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ceidg_sync_stats_id_seq OWNED BY public.ceidg_sync_stats.id;


--
-- Name: chat_message_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_message_feedback (
    id integer NOT NULL,
    message_id integer NOT NULL,
    rating integer NOT NULL,
    voter_key character varying(60) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: chat_message_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_message_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_message_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_message_feedback_id_seq OWNED BY public.chat_message_feedback.id;


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    sources jsonb DEFAULT '[]'::jsonb,
    agent_name character varying(50),
    tokens_used integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_messages_id_seq OWNED BY public.chat_messages.id;


--
-- Name: cinema_showtimes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cinema_showtimes (
    id integer NOT NULL,
    cinema_name character varying NOT NULL,
    date character varying NOT NULL,
    title character varying NOT NULL,
    genre character varying NOT NULL,
    showtimes character varying[],
    poster_url character varying NOT NULL,
    rating character varying NOT NULL,
    link character varying,
    fetched_at timestamp without time zone NOT NULL
);


--
-- Name: cinema_showtimes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cinema_showtimes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cinema_showtimes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cinema_showtimes_id_seq OWNED BY public.cinema_showtimes.id;


--
-- Name: clinic_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clinic_schedules (
    id integer NOT NULL,
    clinic_name character varying(100) NOT NULL,
    doctor_name character varying(200),
    doctor_role character varying(100),
    day_of_week integer,
    specific_date date,
    hours_from character varying(10) NOT NULL,
    hours_to character varying(10) NOT NULL,
    notes character varying(500),
    source_url character varying(500) NOT NULL,
    fetched_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: clinic_schedules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clinic_schedules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clinic_schedules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clinic_schedules_id_seq OWNED BY public.clinic_schedules.id;


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id integer NOT NULL,
    user_id integer,
    title character varying(200),
    agent_name character varying(50),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversations_id_seq OWNED BY public.conversations.id;


--
-- Name: council_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.council_sessions (
    id integer NOT NULL,
    external_id character varying(32) NOT NULL,
    title character varying(500) NOT NULL,
    session_number character varying(20),
    session_date timestamp without time zone,
    page_url character varying(1000) NOT NULL,
    youtube_id character varying(20),
    duration_s double precision DEFAULT 0 NOT NULL,
    transcript_chars integer DEFAULT 0 NOT NULL,
    transcript_json text,
    summary_json text,
    quotes_total integer DEFAULT 0 NOT NULL,
    quotes_verified integer DEFAULT 0 NOT NULL,
    quotes_dropped integer DEFAULT 0 NOT NULL,
    timestamps_fixed integer DEFAULT 0 NOT NULL,
    claims_total integer DEFAULT 0 NOT NULL,
    claims_flagged integer DEFAULT 0 NOT NULL,
    claims_flagged_text text,
    quotes_clean boolean DEFAULT false NOT NULL,
    status character varying(20) DEFAULT 'new'::character varying NOT NULL,
    review_token character varying(64),
    review_note character varying(1000),
    reviewed_at timestamp without time zone,
    reviewed_by integer,
    published_at timestamp without time zone,
    attempts integer DEFAULT 0 NOT NULL,
    last_error character varying(1000),
    cost_usd double precision DEFAULT 0 NOT NULL,
    embedded boolean DEFAULT false NOT NULL,
    first_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    processed_at timestamp without time zone
);


--
-- Name: council_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.council_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: council_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.council_sessions_id_seq OWNED BY public.council_sessions.id;


--
-- Name: csp_violations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.csp_violations (
    id integer NOT NULL,
    directive character varying(40) NOT NULL,
    blocked character varying(120) NOT NULL,
    page character varying(200) NOT NULL,
    disposition character varying(10) DEFAULT 'report'::character varying NOT NULL,
    hits integer DEFAULT 1 NOT NULL,
    first_seen timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text) NOT NULL,
    last_seen timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text) NOT NULL
);


--
-- Name: csp_violations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.csp_violations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: csp_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.csp_violations_id_seq OWNED BY public.csp_violations.id;


--
-- Name: daily_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.daily_summaries (
    id integer NOT NULL,
    date timestamp without time zone NOT NULL,
    headline character varying NOT NULL,
    content jsonb,
    generated_at timestamp without time zone NOT NULL
);


--
-- Name: daily_summaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.daily_summaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: daily_summaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.daily_summaries_id_seq OWNED BY public.daily_summaries.id;


--
-- Name: document_embeddings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_embeddings (
    id integer NOT NULL,
    source_type character varying(50) NOT NULL,
    source_id integer NOT NULL,
    chunk_index integer DEFAULT 0 NOT NULL,
    chunk_text text NOT NULL,
    embedding public.vector(1536),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now(),
    search_vector tsvector
);


--
-- Name: document_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_embeddings_id_seq OWNED BY public.document_embeddings.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    title character varying NOT NULL,
    description character varying,
    short_description character varying,
    event_date timestamp without time zone NOT NULL,
    event_time character varying,
    end_date timestamp without time zone,
    location character varying,
    address character varying,
    category character varying,
    source_article_id integer,
    external_url character varying,
    image_url character varying,
    organizer character varying,
    price_info character varying,
    contact_info character varying,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    is_featured boolean NOT NULL,
    views_count integer NOT NULL,
    embedded boolean DEFAULT false NOT NULL,
    locality smallint,
    canonical_id integer,
    withdrawn_at timestamp without time zone
);


--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: gmina_institutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gmina_institutions (
    id integer NOT NULL,
    slug character varying(60) NOT NULL,
    name character varying(250) NOT NULL,
    kind character varying(30) NOT NULL,
    address character varying(250),
    phone character varying(60),
    email character varying(200),
    website character varying(300),
    manager character varying(150),
    hours character varying(250),
    scope character varying(600),
    bip_url character varying(500),
    content_hash character varying(64),
    active boolean DEFAULT true NOT NULL,
    first_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    last_checked_at timestamp without time zone DEFAULT now() NOT NULL,
    content_changed_at timestamp without time zone
);


--
-- Name: gmina_institutions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gmina_institutions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gmina_institutions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gmina_institutions_id_seq OWNED BY public.gmina_institutions.id;


--
-- Name: gus_data_refresh_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gus_data_refresh_log (
    id integer NOT NULL,
    var_key character varying(100) NOT NULL,
    var_id character varying(20) NOT NULL,
    last_refresh timestamp without time zone DEFAULT now() NOT NULL,
    records_updated integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'success'::character varying NOT NULL,
    error_message character varying(500),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: gus_data_refresh_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gus_data_refresh_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gus_data_refresh_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gus_data_refresh_log_id_seq OWNED BY public.gus_data_refresh_log.id;


--
-- Name: gus_gmina_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gus_gmina_stats (
    id integer NOT NULL,
    unit_id character varying NOT NULL,
    unit_name character varying NOT NULL,
    var_id character varying NOT NULL,
    var_name character varying NOT NULL,
    year integer NOT NULL,
    value double precision,
    fetched_at timestamp without time zone NOT NULL,
    category character varying
);


--
-- Name: gus_gmina_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gus_gmina_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gus_gmina_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gus_gmina_stats_id_seq OWNED BY public.gus_gmina_stats.id;


--
-- Name: gus_insights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gus_insights (
    id integer NOT NULL,
    category character varying(50) NOT NULL,
    insight_type character varying(50) NOT NULL,
    content character varying(2000) NOT NULL,
    data_context jsonb DEFAULT '{}'::jsonb,
    generated_at timestamp without time zone DEFAULT now() NOT NULL,
    valid_until timestamp without time zone NOT NULL
);


--
-- Name: gus_insights_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gus_insights_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gus_insights_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gus_insights_id_seq OWNED BY public.gus_insights.id;


--
-- Name: gus_narratives; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gus_narratives (
    id integer NOT NULL,
    section_key character varying(50) NOT NULL,
    narrative text NOT NULL,
    key_insights jsonb DEFAULT '[]'::jsonb,
    generated_at timestamp without time zone DEFAULT now(),
    valid_until timestamp without time zone NOT NULL
);


--
-- Name: gus_narratives_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gus_narratives_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gus_narratives_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gus_narratives_id_seq OWNED BY public.gus_narratives.id;


--
-- Name: gus_national_averages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gus_national_averages (
    id integer NOT NULL,
    var_id character varying(20) NOT NULL,
    var_key character varying(100) NOT NULL,
    year integer NOT NULL,
    level character varying(20) NOT NULL,
    value double precision,
    fetched_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: gus_national_averages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gus_national_averages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gus_national_averages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gus_national_averages_id_seq OWNED BY public.gus_national_averages.id;


--
-- Name: job_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_runs (
    id integer NOT NULL,
    job_id character varying(60) NOT NULL,
    scheduled_for timestamp without time zone,
    started_at timestamp without time zone,
    finished_at timestamp without time zone,
    status character varying(20) NOT NULL,
    catch_up boolean DEFAULT false NOT NULL,
    error character varying(500)
);


--
-- Name: job_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.job_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.job_runs_id_seq OWNED BY public.job_runs.id;


--
-- Name: legal_acts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_acts (
    id integer NOT NULL,
    bip_id integer NOT NULL,
    act_number character varying(60),
    act_group character varying(120) NOT NULL,
    title text NOT NULL,
    adopted_at date,
    effective_from date,
    status character varying(60),
    url text NOT NULL,
    pdf_url text,
    content text,
    content_hash character varying(64),
    embedded boolean DEFAULT false NOT NULL,
    first_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    last_checked_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: legal_acts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.legal_acts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legal_acts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legal_acts_id_seq OWNED BY public.legal_acts.id;


--
-- Name: local_places; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.local_places (
    id integer NOT NULL,
    place_id character varying(200) NOT NULL,
    name character varying(300) NOT NULL,
    category character varying(50) NOT NULL,
    description character varying(2000),
    address character varying(500),
    maps_uri character varying(500),
    extra_data jsonb,
    active boolean DEFAULT true NOT NULL,
    fetched_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: local_places_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.local_places_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: local_places_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.local_places_id_seq OWNED BY public.local_places.id;


--
-- Name: newsletter_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.newsletter_logs (
    id integer NOT NULL,
    subscriber_id integer NOT NULL,
    newsletter_type character varying(20) NOT NULL,
    subject character varying(255) NOT NULL,
    sent_at timestamp without time zone NOT NULL,
    opened_at timestamp without time zone,
    clicked_at timestamp without time zone,
    status character varying(20) DEFAULT 'sent'::character varying NOT NULL,
    provider_message_id character varying(80)
);


--
-- Name: newsletter_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.newsletter_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: newsletter_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.newsletter_logs_id_seq OWNED BY public.newsletter_logs.id;


--
-- Name: newsletter_subscribers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.newsletter_subscribers (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    user_id integer,
    frequency character varying(20) DEFAULT 'weekly'::character varying NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    location character varying(100) DEFAULT 'Rybno'::character varying NOT NULL,
    confirmation_token character varying(100),
    confirmed_at timestamp without time zone,
    unsubscribe_token character varying(100) NOT NULL,
    unsubscribed_at timestamp without time zone,
    emails_sent integer DEFAULT 0 NOT NULL,
    emails_opened integer DEFAULT 0 NOT NULL,
    last_sent_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: newsletter_subscribers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.newsletter_subscribers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: newsletter_subscribers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.newsletter_subscribers_id_seq OWNED BY public.newsletter_subscribers.id;


--
-- Name: pharmacy_duties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pharmacy_duties (
    id integer NOT NULL,
    pharmacy_name character varying(200) NOT NULL,
    address character varying(300) NOT NULL,
    phone character varying(50),
    duty_type character varying(20) NOT NULL,
    day_of_week integer,
    specific_dates character varying[],
    hours_from character varying(10) NOT NULL,
    hours_to character varying(10) NOT NULL,
    valid_year integer NOT NULL,
    notes character varying(500),
    fetched_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pharmacy_duties_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pharmacy_duties_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pharmacy_duties_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pharmacy_duties_id_seq OWNED BY public.pharmacy_duties.id;


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    id integer NOT NULL,
    user_id integer,
    email character varying(255),
    endpoint character varying(1000) NOT NULL,
    p256dh character varying(200) NOT NULL,
    auth character varying(100) NOT NULL,
    categories jsonb DEFAULT '[]'::jsonb NOT NULL,
    user_agent character varying(500),
    active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    last_used_at timestamp without time zone,
    location character varying(100),
    acq_session_id character varying(36)
);


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.push_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: push_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.push_subscriptions_id_seq OWNED BY public.push_subscriptions.id;


--
-- Name: referrals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.referrals (
    id integer NOT NULL,
    referrer_id integer NOT NULL,
    referred_id integer NOT NULL,
    rewarded_at timestamp without time zone,
    reward_days integer DEFAULT 14 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: referrals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.referrals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: referrals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.referrals_id_seq OWNED BY public.referrals.id;


--
-- Name: report_upvotes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_upvotes (
    id integer NOT NULL,
    report_id integer NOT NULL,
    voter_key character varying(64) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: report_upvotes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.report_upvotes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: report_upvotes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.report_upvotes_id_seq OWNED BY public.report_upvotes.id;


--
-- Name: reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reports (
    id integer NOT NULL,
    user_id integer,
    author_name character varying(100),
    author_email character varying(255),
    author_phone character varying(50),
    title character varying(200) NOT NULL,
    description character varying NOT NULL,
    ai_summary character varying,
    category character varying(50) DEFAULT 'other'::character varying NOT NULL,
    ai_detected_objects jsonb,
    ai_condition_assessment character varying(500),
    ai_severity character varying(20),
    image_url character varying(500),
    generated_image_url character varying(500),
    latitude double precision,
    longitude double precision,
    address character varying(300),
    location_name character varying(100),
    status character varying(20) DEFAULT 'new'::character varying NOT NULL,
    is_spam boolean DEFAULT false NOT NULL,
    upvotes integer DEFAULT 0 NOT NULL,
    views_count integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    resolved_at timestamp without time zone
);


--
-- Name: reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reports_id_seq OWNED BY public.reports.id;


--
-- Name: role_invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_invitations (
    id integer NOT NULL,
    token character varying(64) NOT NULL,
    role character varying(30) NOT NULL,
    scope character varying(100) DEFAULT ''::character varying NOT NULL,
    invitee_label character varying(100),
    created_by character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    used_by_user_id integer,
    revoked_at timestamp without time zone
);


--
-- Name: role_invitations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.role_invitations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: role_invitations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.role_invitations_id_seq OWNED BY public.role_invitations.id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    name character varying(100) NOT NULL,
    applied_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text) NOT NULL,
    baseline boolean DEFAULT false NOT NULL
);


--
-- Name: site_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.site_events (
    id bigint NOT NULL,
    occurred_at timestamp without time zone DEFAULT now() NOT NULL,
    session_id character varying(36),
    user_id integer,
    event character varying(40) NOT NULL,
    section character varying(40),
    path character varying(200),
    referrer_host character varying(120),
    utm_source character varying(60),
    utm_medium character varying(60),
    utm_campaign character varying(100),
    utm_content character varying(100),
    device character varying(10),
    meta jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: site_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.site_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: site_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.site_events_id_seq OWNED BY public.site_events.id;


--
-- Name: solectwo_post_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solectwo_post_requests (
    id integer NOT NULL,
    post_id integer NOT NULL,
    user_id integer,
    kind character varying(20) NOT NULL,
    message text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    handled_by character varying(255),
    handled_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text) NOT NULL
);


--
-- Name: solectwo_post_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solectwo_post_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solectwo_post_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solectwo_post_requests_id_seq OWNED BY public.solectwo_post_requests.id;


--
-- Name: solectwo_post_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solectwo_post_versions (
    id integer NOT NULL,
    post_id integer NOT NULL,
    version integer NOT NULL,
    kind character varying(20) NOT NULL,
    title character varying(200),
    summary text,
    transcript text,
    event_at timestamp without time zone,
    event_until timestamp without time zone,
    reason character varying(500),
    changed_by character varying(255),
    created_at timestamp without time zone DEFAULT (now() AT TIME ZONE 'utc'::text) NOT NULL
);


--
-- Name: solectwo_post_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solectwo_post_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solectwo_post_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solectwo_post_versions_id_seq OWNED BY public.solectwo_post_versions.id;


--
-- Name: solectwo_posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solectwo_posts (
    id integer NOT NULL,
    user_id integer,
    role_id integer,
    solectwo character varying(100) NOT NULL,
    signed_as character varying(150) NOT NULL,
    status character varying(20) DEFAULT 'processing'::character varying NOT NULL,
    note text,
    image_files jsonb DEFAULT '[]'::jsonb NOT NULL,
    title character varying(200),
    summary text,
    transcript text,
    doc_type character varying(100),
    event_at timestamp without time zone,
    event_until timestamp without time zone,
    personal_data jsonb,
    illegible jsonb,
    ai_error text,
    article_id integer,
    moderated_by character varying(255),
    moderated_at timestamp without time zone,
    reject_reason character varying(500),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    published_at timestamp without time zone,
    images_deleted_at timestamp without time zone,
    version integer DEFAULT 0 NOT NULL,
    corrected_at timestamp without time zone,
    withdrawn_at timestamp without time zone,
    withdraw_reason character varying(500)
);


--
-- Name: solectwo_posts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solectwo_posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solectwo_posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solectwo_posts_id_seq OWNED BY public.solectwo_posts.id;


--
-- Name: sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sources (
    id integer NOT NULL,
    name character varying NOT NULL,
    type character varying NOT NULL,
    url character varying,
    scraping_config jsonb,
    last_scraped timestamp without time zone,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_success_at timestamp without time zone,
    last_error character varying(300),
    last_error_at timestamp without time zone
);


--
-- Name: sources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sources_id_seq OWNED BY public.sources.id;


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tier character varying(20) NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    stripe_subscription_id character varying(100),
    stripe_customer_id character varying(100),
    started_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone,
    cancelled_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    p24_order_id character varying(100),
    p24_session_id character varying(100),
    reminder_stage character varying(20),
    reminder_sent_at timestamp without time zone
);


--
-- Name: subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.subscriptions_id_seq OWNED BY public.subscriptions.id;


--
-- Name: traffic_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.traffic_cache (
    id integer NOT NULL,
    data jsonb,
    fetched_at timestamp without time zone NOT NULL,
    is_current boolean NOT NULL,
    ttl_seconds integer NOT NULL
);


--
-- Name: traffic_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.traffic_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: traffic_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.traffic_cache_id_seq OWNED BY public.traffic_cache.id;


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying(30) NOT NULL,
    scope character varying(100) DEFAULT ''::character varying NOT NULL,
    status character varying(20) DEFAULT 'verified'::character varying NOT NULL,
    method character varying(20) DEFAULT 'manual'::character varying NOT NULL,
    verified_by character varying(255),
    verified_at timestamp without time zone,
    revoked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: user_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_roles_id_seq OWNED BY public.user_roles.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(100) NOT NULL,
    location character varying(100) DEFAULT 'Rybno'::character varying NOT NULL,
    tier character varying(20) DEFAULT 'free'::character varying NOT NULL,
    preferences jsonb,
    email_verified boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_login timestamp without time zone,
    trial_ends_at timestamp without time zone,
    referral_code character varying(20),
    referred_by integer,
    consent_terms_at timestamp without time zone,
    consent_marketing boolean DEFAULT false NOT NULL,
    consent_privacy_version character varying(20),
    is_admin boolean DEFAULT false NOT NULL,
    trial_reminder_stage character varying(20),
    trial_reminder_sent_at timestamp without time zone,
    acq_session_id character varying(36),
    acq_utm_campaign character varying(100),
    acq_landing character varying(200),
    acq_first_seen timestamp without time zone
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: waste_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.waste_schedule (
    id integer NOT NULL,
    town character varying NOT NULL,
    waste_type character varying NOT NULL,
    collection_date date NOT NULL,
    year integer DEFAULT 0 NOT NULL
);


--
-- Name: waste_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.waste_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: waste_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.waste_schedule_id_seq OWNED BY public.waste_schedule.id;


--
-- Name: weather; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather (
    id integer NOT NULL,
    location character varying NOT NULL,
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    temperature double precision NOT NULL,
    feels_like double precision NOT NULL,
    temp_min double precision NOT NULL,
    temp_max double precision NOT NULL,
    description character varying NOT NULL,
    icon character varying NOT NULL,
    main character varying NOT NULL,
    humidity integer NOT NULL,
    pressure integer NOT NULL,
    wind_speed double precision NOT NULL,
    wind_deg integer,
    clouds integer NOT NULL,
    visibility integer,
    rain_1h double precision,
    rain_3h double precision,
    sunrise timestamp without time zone,
    sunset timestamp without time zone,
    forecast jsonb,
    fetched_at timestamp without time zone NOT NULL,
    is_current boolean NOT NULL
);


--
-- Name: weather_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weather_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_id_seq OWNED BY public.weather.id;


--
-- Name: agent_tool_calls id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tool_calls ALTER COLUMN id SET DEFAULT nextval('public.agent_tool_calls_id_seq'::regclass);


--
-- Name: air_quality id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality ALTER COLUMN id SET DEFAULT nextval('public.air_quality_id_seq'::regclass);


--
-- Name: anonymous_chat_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anonymous_chat_usage ALTER COLUMN id SET DEFAULT nextval('public.anonymous_chat_usage_id_seq'::regclass);


--
-- Name: api_cost_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_cost_log ALTER COLUMN id SET DEFAULT nextval('public.api_cost_log_id_seq'::regclass);


--
-- Name: articles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.articles ALTER COLUMN id SET DEFAULT nextval('public.articles_id_seq'::regclass);


--
-- Name: bip_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bip_documents ALTER COLUMN id SET DEFAULT nextval('public.bip_documents_id_seq'::regclass);


--
-- Name: bus_stop_times id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stop_times ALTER COLUMN id SET DEFAULT nextval('public.bus_stop_times_id_seq'::regclass);


--
-- Name: bus_stops id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stops ALTER COLUMN id SET DEFAULT nextval('public.bus_stops_id_seq'::regclass);


--
-- Name: bus_trips id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_trips ALTER COLUMN id SET DEFAULT nextval('public.bus_trips_id_seq'::regclass);


--
-- Name: business_announcements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_announcements ALTER COLUMN id SET DEFAULT nextval('public.business_announcements_id_seq'::regclass);


--
-- Name: business_claim_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_claim_log ALTER COLUMN id SET DEFAULT nextval('public.business_claim_log_id_seq'::regclass);


--
-- Name: business_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_profiles ALTER COLUMN id SET DEFAULT nextval('public.business_profiles_id_seq'::regclass);


--
-- Name: ceidg_businesses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ceidg_businesses ALTER COLUMN id SET DEFAULT nextval('public.ceidg_businesses_id_seq'::regclass);


--
-- Name: ceidg_sync_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ceidg_sync_stats ALTER COLUMN id SET DEFAULT nextval('public.ceidg_sync_stats_id_seq'::regclass);


--
-- Name: chat_message_feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_feedback ALTER COLUMN id SET DEFAULT nextval('public.chat_message_feedback_id_seq'::regclass);


--
-- Name: chat_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages ALTER COLUMN id SET DEFAULT nextval('public.chat_messages_id_seq'::regclass);


--
-- Name: cinema_showtimes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cinema_showtimes ALTER COLUMN id SET DEFAULT nextval('public.cinema_showtimes_id_seq'::regclass);


--
-- Name: clinic_schedules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinic_schedules ALTER COLUMN id SET DEFAULT nextval('public.clinic_schedules_id_seq'::regclass);


--
-- Name: conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations ALTER COLUMN id SET DEFAULT nextval('public.conversations_id_seq'::regclass);


--
-- Name: council_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.council_sessions ALTER COLUMN id SET DEFAULT nextval('public.council_sessions_id_seq'::regclass);


--
-- Name: csp_violations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.csp_violations ALTER COLUMN id SET DEFAULT nextval('public.csp_violations_id_seq'::regclass);


--
-- Name: daily_summaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_summaries ALTER COLUMN id SET DEFAULT nextval('public.daily_summaries_id_seq'::regclass);


--
-- Name: document_embeddings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_embeddings ALTER COLUMN id SET DEFAULT nextval('public.document_embeddings_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: gmina_institutions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gmina_institutions ALTER COLUMN id SET DEFAULT nextval('public.gmina_institutions_id_seq'::regclass);


--
-- Name: gus_data_refresh_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_data_refresh_log ALTER COLUMN id SET DEFAULT nextval('public.gus_data_refresh_log_id_seq'::regclass);


--
-- Name: gus_gmina_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_gmina_stats ALTER COLUMN id SET DEFAULT nextval('public.gus_gmina_stats_id_seq'::regclass);


--
-- Name: gus_insights id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_insights ALTER COLUMN id SET DEFAULT nextval('public.gus_insights_id_seq'::regclass);


--
-- Name: gus_narratives id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_narratives ALTER COLUMN id SET DEFAULT nextval('public.gus_narratives_id_seq'::regclass);


--
-- Name: gus_national_averages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_national_averages ALTER COLUMN id SET DEFAULT nextval('public.gus_national_averages_id_seq'::regclass);


--
-- Name: job_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_runs ALTER COLUMN id SET DEFAULT nextval('public.job_runs_id_seq'::regclass);


--
-- Name: legal_acts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acts ALTER COLUMN id SET DEFAULT nextval('public.legal_acts_id_seq'::regclass);


--
-- Name: local_places id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.local_places ALTER COLUMN id SET DEFAULT nextval('public.local_places_id_seq'::regclass);


--
-- Name: newsletter_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_logs ALTER COLUMN id SET DEFAULT nextval('public.newsletter_logs_id_seq'::regclass);


--
-- Name: newsletter_subscribers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_subscribers ALTER COLUMN id SET DEFAULT nextval('public.newsletter_subscribers_id_seq'::regclass);


--
-- Name: pharmacy_duties id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_duties ALTER COLUMN id SET DEFAULT nextval('public.pharmacy_duties_id_seq'::regclass);


--
-- Name: push_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.push_subscriptions_id_seq'::regclass);


--
-- Name: referrals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referrals ALTER COLUMN id SET DEFAULT nextval('public.referrals_id_seq'::regclass);


--
-- Name: report_upvotes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_upvotes ALTER COLUMN id SET DEFAULT nextval('public.report_upvotes_id_seq'::regclass);


--
-- Name: reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports ALTER COLUMN id SET DEFAULT nextval('public.reports_id_seq'::regclass);


--
-- Name: role_invitations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_invitations ALTER COLUMN id SET DEFAULT nextval('public.role_invitations_id_seq'::regclass);


--
-- Name: site_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site_events ALTER COLUMN id SET DEFAULT nextval('public.site_events_id_seq'::regclass);


--
-- Name: solectwo_post_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_requests ALTER COLUMN id SET DEFAULT nextval('public.solectwo_post_requests_id_seq'::regclass);


--
-- Name: solectwo_post_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_versions ALTER COLUMN id SET DEFAULT nextval('public.solectwo_post_versions_id_seq'::regclass);


--
-- Name: solectwo_posts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_posts ALTER COLUMN id SET DEFAULT nextval('public.solectwo_posts_id_seq'::regclass);


--
-- Name: sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources ALTER COLUMN id SET DEFAULT nextval('public.sources_id_seq'::regclass);


--
-- Name: subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions ALTER COLUMN id SET DEFAULT nextval('public.subscriptions_id_seq'::regclass);


--
-- Name: traffic_cache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.traffic_cache ALTER COLUMN id SET DEFAULT nextval('public.traffic_cache_id_seq'::regclass);


--
-- Name: user_roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles ALTER COLUMN id SET DEFAULT nextval('public.user_roles_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: waste_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_schedule ALTER COLUMN id SET DEFAULT nextval('public.waste_schedule_id_seq'::regclass);


--
-- Name: weather id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather ALTER COLUMN id SET DEFAULT nextval('public.weather_id_seq'::regclass);


--
-- Name: agent_tool_calls agent_tool_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_tool_calls
    ADD CONSTRAINT agent_tool_calls_pkey PRIMARY KEY (id);


--
-- Name: air_quality air_quality_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.air_quality
    ADD CONSTRAINT air_quality_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: anonymous_chat_usage anonymous_chat_usage_ip_address_usage_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anonymous_chat_usage
    ADD CONSTRAINT anonymous_chat_usage_ip_address_usage_date_key UNIQUE (ip_address, usage_date);


--
-- Name: anonymous_chat_usage anonymous_chat_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.anonymous_chat_usage
    ADD CONSTRAINT anonymous_chat_usage_pkey PRIMARY KEY (id);


--
-- Name: api_cost_log api_cost_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_cost_log
    ADD CONSTRAINT api_cost_log_pkey PRIMARY KEY (id);


--
-- Name: articles articles_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_external_id_key UNIQUE (external_id);


--
-- Name: articles articles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_pkey PRIMARY KEY (id);


--
-- Name: bip_documents bip_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bip_documents
    ADD CONSTRAINT bip_documents_pkey PRIMARY KEY (id);


--
-- Name: bip_documents bip_documents_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bip_documents
    ADD CONSTRAINT bip_documents_url_key UNIQUE (url);


--
-- Name: bus_stop_times bus_stop_times_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stop_times
    ADD CONSTRAINT bus_stop_times_pkey PRIMARY KEY (id);


--
-- Name: bus_stops bus_stops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stops
    ADD CONSTRAINT bus_stops_pkey PRIMARY KEY (id);


--
-- Name: bus_stops bus_stops_stop_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stops
    ADD CONSTRAINT bus_stops_stop_id_key UNIQUE (stop_id);


--
-- Name: bus_trips bus_trips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_trips
    ADD CONSTRAINT bus_trips_pkey PRIMARY KEY (id);


--
-- Name: business_announcements business_announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_announcements
    ADD CONSTRAINT business_announcements_pkey PRIMARY KEY (id);


--
-- Name: business_claim_log business_claim_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_claim_log
    ADD CONSTRAINT business_claim_log_pkey PRIMARY KEY (id);


--
-- Name: business_profiles business_profiles_business_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_profiles
    ADD CONSTRAINT business_profiles_business_id_key UNIQUE (business_id);


--
-- Name: business_profiles business_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_profiles
    ADD CONSTRAINT business_profiles_pkey PRIMARY KEY (id);


--
-- Name: ceidg_businesses ceidg_businesses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ceidg_businesses
    ADD CONSTRAINT ceidg_businesses_pkey PRIMARY KEY (id);


--
-- Name: ceidg_sync_stats ceidg_sync_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ceidg_sync_stats
    ADD CONSTRAINT ceidg_sync_stats_pkey PRIMARY KEY (id);


--
-- Name: chat_message_feedback chat_message_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_feedback
    ADD CONSTRAINT chat_message_feedback_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: cinema_showtimes cinema_showtimes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cinema_showtimes
    ADD CONSTRAINT cinema_showtimes_pkey PRIMARY KEY (id);


--
-- Name: clinic_schedules clinic_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clinic_schedules
    ADD CONSTRAINT clinic_schedules_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: council_sessions council_sessions_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.council_sessions
    ADD CONSTRAINT council_sessions_external_id_key UNIQUE (external_id);


--
-- Name: council_sessions council_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.council_sessions
    ADD CONSTRAINT council_sessions_pkey PRIMARY KEY (id);


--
-- Name: council_sessions council_sessions_review_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.council_sessions
    ADD CONSTRAINT council_sessions_review_token_key UNIQUE (review_token);


--
-- Name: csp_violations csp_violations_directive_blocked_page_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.csp_violations
    ADD CONSTRAINT csp_violations_directive_blocked_page_key UNIQUE (directive, blocked, page);


--
-- Name: csp_violations csp_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.csp_violations
    ADD CONSTRAINT csp_violations_pkey PRIMARY KEY (id);


--
-- Name: daily_summaries daily_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_summaries
    ADD CONSTRAINT daily_summaries_pkey PRIMARY KEY (id);


--
-- Name: document_embeddings document_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_embeddings
    ADD CONSTRAINT document_embeddings_pkey PRIMARY KEY (id);


--
-- Name: document_embeddings document_embeddings_source_type_source_id_chunk_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_embeddings
    ADD CONSTRAINT document_embeddings_source_type_source_id_chunk_index_key UNIQUE (source_type, source_id, chunk_index);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: gmina_institutions gmina_institutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gmina_institutions
    ADD CONSTRAINT gmina_institutions_pkey PRIMARY KEY (id);


--
-- Name: gmina_institutions gmina_institutions_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gmina_institutions
    ADD CONSTRAINT gmina_institutions_slug_key UNIQUE (slug);


--
-- Name: gus_data_refresh_log gus_data_refresh_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_data_refresh_log
    ADD CONSTRAINT gus_data_refresh_log_pkey PRIMARY KEY (id);


--
-- Name: gus_gmina_stats gus_gmina_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_gmina_stats
    ADD CONSTRAINT gus_gmina_stats_pkey PRIMARY KEY (id);


--
-- Name: gus_insights gus_insights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_insights
    ADD CONSTRAINT gus_insights_pkey PRIMARY KEY (id);


--
-- Name: gus_narratives gus_narratives_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_narratives
    ADD CONSTRAINT gus_narratives_pkey PRIMARY KEY (id);


--
-- Name: gus_narratives gus_narratives_section_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_narratives
    ADD CONSTRAINT gus_narratives_section_key_key UNIQUE (section_key);


--
-- Name: gus_national_averages gus_national_averages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gus_national_averages
    ADD CONSTRAINT gus_national_averages_pkey PRIMARY KEY (id);


--
-- Name: job_runs job_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT job_runs_pkey PRIMARY KEY (id);


--
-- Name: legal_acts legal_acts_bip_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acts
    ADD CONSTRAINT legal_acts_bip_id_key UNIQUE (bip_id);


--
-- Name: legal_acts legal_acts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_acts
    ADD CONSTRAINT legal_acts_pkey PRIMARY KEY (id);


--
-- Name: local_places local_places_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.local_places
    ADD CONSTRAINT local_places_pkey PRIMARY KEY (id);


--
-- Name: local_places local_places_place_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.local_places
    ADD CONSTRAINT local_places_place_id_key UNIQUE (place_id);


--
-- Name: newsletter_logs newsletter_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_logs
    ADD CONSTRAINT newsletter_logs_pkey PRIMARY KEY (id);


--
-- Name: newsletter_subscribers newsletter_subscribers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_subscribers
    ADD CONSTRAINT newsletter_subscribers_pkey PRIMARY KEY (id);


--
-- Name: pharmacy_duties pharmacy_duties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pharmacy_duties
    ADD CONSTRAINT pharmacy_duties_pkey PRIMARY KEY (id);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: referrals referrals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_pkey PRIMARY KEY (id);


--
-- Name: referrals referrals_referred_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referred_id_key UNIQUE (referred_id);


--
-- Name: report_upvotes report_upvotes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_upvotes
    ADD CONSTRAINT report_upvotes_pkey PRIMARY KEY (id);


--
-- Name: reports reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_pkey PRIMARY KEY (id);


--
-- Name: role_invitations role_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_invitations
    ADD CONSTRAINT role_invitations_pkey PRIMARY KEY (id);


--
-- Name: role_invitations role_invitations_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_invitations
    ADD CONSTRAINT role_invitations_token_key UNIQUE (token);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (name);


--
-- Name: site_events site_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site_events
    ADD CONSTRAINT site_events_pkey PRIMARY KEY (id);


--
-- Name: solectwo_post_requests solectwo_post_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_requests
    ADD CONSTRAINT solectwo_post_requests_pkey PRIMARY KEY (id);


--
-- Name: solectwo_post_versions solectwo_post_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_versions
    ADD CONSTRAINT solectwo_post_versions_pkey PRIMARY KEY (id);


--
-- Name: solectwo_post_versions solectwo_post_versions_post_id_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_versions
    ADD CONSTRAINT solectwo_post_versions_post_id_version_key UNIQUE (post_id, version);


--
-- Name: solectwo_posts solectwo_posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_posts
    ADD CONSTRAINT solectwo_posts_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: traffic_cache traffic_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.traffic_cache
    ADD CONSTRAINT traffic_cache_pkey PRIMARY KEY (id);


--
-- Name: chat_message_feedback uq_feedback_message_voter; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_feedback
    ADD CONSTRAINT uq_feedback_message_voter UNIQUE (message_id, voter_key);


--
-- Name: report_upvotes uq_report_upvotes_report_voter; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_upvotes
    ADD CONSTRAINT uq_report_upvotes_report_voter UNIQUE (report_id, voter_key);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_referral_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_referral_code_key UNIQUE (referral_code);


--
-- Name: waste_schedule waste_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waste_schedule
    ADD CONSTRAINT waste_schedule_pkey PRIMARY KEY (id);


--
-- Name: weather weather_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather
    ADD CONSTRAINT weather_pkey PRIMARY KEY (id);


--
-- Name: idx_anon_ip_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_anon_ip_date ON public.anonymous_chat_usage USING btree (ip_address, usage_date);


--
-- Name: idx_articles_event_unchecked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_articles_event_unchecked ON public.articles USING btree (event_at) WHERE ((event_checked_at IS NULL) AND (event_at IS NOT NULL));


--
-- Name: idx_articles_story_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_articles_story_id ON public.articles USING btree (story_id) WHERE (story_id IS NOT NULL);


--
-- Name: idx_bprofiles_premium; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bprofiles_premium ON public.business_profiles USING btree (is_premium);


--
-- Name: idx_bprofiles_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bprofiles_user ON public.business_profiles USING btree (user_id);


--
-- Name: idx_bus_stop_times_trip_seq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bus_stop_times_trip_seq ON public.bus_stop_times USING btree (trip_id, stop_sequence);


--
-- Name: idx_bus_trips_direction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bus_trips_direction ON public.bus_trips USING btree (direction);


--
-- Name: idx_ceidg_gmina_powiat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ceidg_gmina_powiat ON public.ceidg_businesses USING btree (gmina, powiat);


--
-- Name: idx_ceidg_miasto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ceidg_miasto ON public.ceidg_businesses USING btree (miasto);


--
-- Name: idx_ceidg_nip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ceidg_nip ON public.ceidg_businesses USING btree (nip);


--
-- Name: idx_ceidg_opted_out; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ceidg_opted_out ON public.ceidg_businesses USING btree (opted_out);


--
-- Name: idx_ceidg_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ceidg_source ON public.ceidg_businesses USING btree (source);


--
-- Name: idx_chat_messages_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chat_messages_conversation ON public.chat_messages USING btree (conversation_id, created_at);


--
-- Name: idx_cinema_date_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cinema_date_title ON public.cinema_showtimes USING btree (cinema_name, date, title);


--
-- Name: idx_clinic_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clinic_day ON public.clinic_schedules USING btree (clinic_name, day_of_week);


--
-- Name: idx_clinic_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clinic_name ON public.clinic_schedules USING btree (clinic_name);


--
-- Name: idx_conversations_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_user ON public.conversations USING btree (user_id, updated_at DESC);


--
-- Name: idx_cost_log_service_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cost_log_service_date ON public.api_cost_log USING btree (service, created_at DESC);


--
-- Name: idx_csp_violations_last_seen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_csp_violations_last_seen ON public.csp_violations USING btree (last_seen);


--
-- Name: idx_embeddings_fts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_embeddings_fts ON public.document_embeddings USING gin (search_vector);


--
-- Name: idx_embeddings_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_embeddings_source_id ON public.document_embeddings USING btree (source_type, source_id);


--
-- Name: idx_embeddings_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_embeddings_source_type ON public.document_embeddings USING btree (source_type);


--
-- Name: idx_embeddings_vector_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_embeddings_vector_hnsw ON public.document_embeddings USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_event_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_canonical ON public.events USING btree (canonical_id);


--
-- Name: idx_event_day_place; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_day_place ON public.events USING btree (date(event_date), location);


--
-- Name: idx_event_one_per_article; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_event_one_per_article ON public.events USING btree (source_article_id) WHERE ((source_article_id IS NOT NULL) AND (canonical_id IS NULL));


--
-- Name: idx_feedback_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_message ON public.chat_message_feedback USING btree (message_id);


--
-- Name: idx_gus_avg_var_year_level; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_gus_avg_var_year_level ON public.gus_national_averages USING btree (var_id, year, level);


--
-- Name: idx_gus_gmina_unit_var_year; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_gus_gmina_unit_var_year ON public.gus_gmina_stats USING btree (unit_id, var_id, year);


--
-- Name: idx_gus_insight_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gus_insight_category ON public.gus_insights USING btree (category);


--
-- Name: idx_gus_refresh_var_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_gus_refresh_var_key ON public.gus_data_refresh_log USING btree (var_key);


--
-- Name: idx_job_runs_job_scheduled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_job_runs_job_scheduled ON public.job_runs USING btree (job_id, scheduled_for DESC);


--
-- Name: idx_job_runs_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_job_runs_started ON public.job_runs USING btree (started_at DESC);


--
-- Name: idx_legal_acts_adopted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_acts_adopted ON public.legal_acts USING btree (adopted_at DESC);


--
-- Name: idx_legal_acts_embedded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_acts_embedded ON public.legal_acts USING btree (embedded);


--
-- Name: idx_legal_acts_group_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_acts_group_date ON public.legal_acts USING btree (act_group, adopted_at DESC);


--
-- Name: idx_local_places_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_local_places_category ON public.local_places USING btree (category);


--
-- Name: idx_local_places_fetched; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_local_places_fetched ON public.local_places USING btree (fetched_at);


--
-- Name: idx_newsletter_logs_provider_msg; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_newsletter_logs_provider_msg ON public.newsletter_logs USING btree (provider_message_id);


--
-- Name: idx_pharmacy_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pharmacy_name ON public.pharmacy_duties USING btree (pharmacy_name);


--
-- Name: idx_pharmacy_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pharmacy_year ON public.pharmacy_duties USING btree (pharmacy_name, valid_year);


--
-- Name: idx_push_subscriptions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_subscriptions_active ON public.push_subscriptions USING btree (active);


--
-- Name: idx_push_subscriptions_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_subscriptions_endpoint ON public.push_subscriptions USING btree (endpoint);


--
-- Name: idx_push_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_subscriptions_user_id ON public.push_subscriptions USING btree (user_id);


--
-- Name: idx_referral_referrer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_referral_referrer ON public.referrals USING btree (referrer_id);


--
-- Name: idx_site_events_campaign; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_site_events_campaign ON public.site_events USING btree (utm_campaign);


--
-- Name: idx_site_events_event_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_site_events_event_occurred ON public.site_events USING btree (event, occurred_at);


--
-- Name: idx_site_events_occurred; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_site_events_occurred ON public.site_events USING btree (occurred_at);


--
-- Name: idx_site_events_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_site_events_session ON public.site_events USING btree (session_id);


--
-- Name: idx_solectwo_post_requests_open; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solectwo_post_requests_open ON public.solectwo_post_requests USING btree (post_id) WHERE ((status)::text = 'open'::text);


--
-- Name: idx_solectwo_posts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solectwo_posts_status ON public.solectwo_posts USING btree (status);


--
-- Name: idx_solectwo_posts_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solectwo_posts_user ON public.solectwo_posts USING btree (user_id);


--
-- Name: idx_subscriptions_p24_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_subscriptions_p24_session ON public.subscriptions USING btree (p24_session_id) WHERE (p24_session_id IS NOT NULL);


--
-- Name: idx_tool_calls_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_calls_created ON public.agent_tool_calls USING btree (created_at);


--
-- Name: idx_tool_calls_tool_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tool_calls_tool_state ON public.agent_tool_calls USING btree (tool_name, state);


--
-- Name: idx_user_roles_live; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_user_roles_live ON public.user_roles USING btree (user_id, role, scope) WHERE ((status)::text <> 'revoked'::text);


--
-- Name: idx_user_roles_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_roles_user ON public.user_roles USING btree (user_id);


--
-- Name: idx_waste_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_waste_date ON public.waste_schedule USING btree (collection_date);


--
-- Name: idx_waste_town; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_waste_town ON public.waste_schedule USING btree (town);


--
-- Name: idx_waste_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_waste_year ON public.waste_schedule USING btree (year);


--
-- Name: ix_air_quality_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_air_quality_fetched_at ON public.air_quality USING btree (fetched_at);


--
-- Name: ix_air_quality_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_air_quality_location ON public.air_quality USING btree (location);


--
-- Name: ix_articles_alert_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_articles_alert_pending ON public.articles USING btree (scraped_at) WHERE (alert_pushed_at IS NULL);


--
-- Name: ix_articles_event_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_articles_event_at ON public.articles USING btree (event_at);


--
-- Name: ix_articles_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_articles_source_id ON public.articles USING btree (source_id);


--
-- Name: ix_articles_url; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_articles_url ON public.articles USING btree (url);


--
-- Name: ix_bip_documents_content_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bip_documents_content_hash ON public.bip_documents USING btree (content_hash);


--
-- Name: ix_bip_documents_embedded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bip_documents_embedded ON public.bip_documents USING btree (embedded);


--
-- Name: ix_bip_documents_section_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bip_documents_section_id ON public.bip_documents USING btree (section_id);


--
-- Name: ix_business_announcements_active_valid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_announcements_active_valid ON public.business_announcements USING btree (is_active, valid_until);


--
-- Name: ix_business_announcements_business_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_announcements_business_id ON public.business_announcements USING btree (business_id);


--
-- Name: ix_business_claim_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_claim_log_action ON public.business_claim_log USING btree (action);


--
-- Name: ix_business_claim_log_business_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_claim_log_business_id ON public.business_claim_log USING btree (business_id);


--
-- Name: ix_business_claim_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_claim_log_created_at ON public.business_claim_log USING btree (created_at);


--
-- Name: ix_business_claim_log_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_business_claim_log_user_id ON public.business_claim_log USING btree (user_id);


--
-- Name: ix_ceidg_businesses_ceidg_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_ceidg_businesses_ceidg_id ON public.ceidg_businesses USING btree (ceidg_id);


--
-- Name: ix_ceidg_businesses_miasto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ceidg_businesses_miasto ON public.ceidg_businesses USING btree (miasto);


--
-- Name: ix_ceidg_businesses_nip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ceidg_businesses_nip ON public.ceidg_businesses USING btree (nip);


--
-- Name: ix_ceidg_businesses_pkd_main; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ceidg_businesses_pkd_main ON public.ceidg_businesses USING btree (pkd_main);


--
-- Name: ix_ceidg_status_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ceidg_status_changed_at ON public.ceidg_businesses USING btree (status_changed_at);


--
-- Name: ix_ceidg_sync_stats_gmina; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_ceidg_sync_stats_gmina ON public.ceidg_sync_stats USING btree (gmina);


--
-- Name: ix_cinema_showtimes_cinema_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cinema_showtimes_cinema_name ON public.cinema_showtimes USING btree (cinema_name);


--
-- Name: ix_cinema_showtimes_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cinema_showtimes_date ON public.cinema_showtimes USING btree (date);


--
-- Name: ix_cinema_showtimes_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cinema_showtimes_fetched_at ON public.cinema_showtimes USING btree (fetched_at);


--
-- Name: ix_council_sessions_embedded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_council_sessions_embedded ON public.council_sessions USING btree (embedded);


--
-- Name: ix_council_sessions_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_council_sessions_external_id ON public.council_sessions USING btree (external_id);


--
-- Name: ix_council_sessions_review_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_council_sessions_review_token ON public.council_sessions USING btree (review_token);


--
-- Name: ix_council_sessions_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_council_sessions_session_date ON public.council_sessions USING btree (session_date);


--
-- Name: ix_council_sessions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_council_sessions_status ON public.council_sessions USING btree (status);


--
-- Name: ix_daily_summaries_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_daily_summaries_date ON public.daily_summaries USING btree (date);


--
-- Name: ix_gmina_institutions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gmina_institutions_active ON public.gmina_institutions USING btree (active);


--
-- Name: ix_gmina_institutions_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gmina_institutions_kind ON public.gmina_institutions USING btree (kind);


--
-- Name: ix_gus_data_refresh_log_var_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_gus_data_refresh_log_var_key ON public.gus_data_refresh_log USING btree (var_key);


--
-- Name: ix_gus_gmina_stats_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_gmina_stats_category ON public.gus_gmina_stats USING btree (category);


--
-- Name: ix_gus_gmina_stats_unit_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_gmina_stats_unit_id ON public.gus_gmina_stats USING btree (unit_id);


--
-- Name: ix_gus_gmina_stats_var_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_gmina_stats_var_id ON public.gus_gmina_stats USING btree (var_id);


--
-- Name: ix_gus_gmina_stats_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_gmina_stats_year ON public.gus_gmina_stats USING btree (year);


--
-- Name: ix_gus_insights_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_insights_category ON public.gus_insights USING btree (category);


--
-- Name: ix_gus_national_averages_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_national_averages_level ON public.gus_national_averages USING btree (level);


--
-- Name: ix_gus_national_averages_var_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_national_averages_var_id ON public.gus_national_averages USING btree (var_id);


--
-- Name: ix_gus_national_averages_var_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_national_averages_var_key ON public.gus_national_averages USING btree (var_key);


--
-- Name: ix_gus_national_averages_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gus_national_averages_year ON public.gus_national_averages USING btree (year);


--
-- Name: ix_newsletter_logs_subscriber_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_newsletter_logs_subscriber_id ON public.newsletter_logs USING btree (subscriber_id);


--
-- Name: ix_newsletter_subscribers_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_newsletter_subscribers_email ON public.newsletter_subscribers USING btree (email);


--
-- Name: ix_push_subscriptions_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_push_subscriptions_location ON public.push_subscriptions USING btree (location);


--
-- Name: ix_reports_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_category ON public.reports USING btree (category);


--
-- Name: ix_reports_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_created_at ON public.reports USING btree (created_at);


--
-- Name: ix_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_status ON public.reports USING btree (status);


--
-- Name: ix_reports_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reports_user_id ON public.reports USING btree (user_id);


--
-- Name: ix_sources_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sources_name ON public.sources USING btree (name);


--
-- Name: ix_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_user_id ON public.subscriptions USING btree (user_id);


--
-- Name: ix_traffic_cache_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_traffic_cache_fetched_at ON public.traffic_cache USING btree (fetched_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_weather_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_fetched_at ON public.weather USING btree (fetched_at);


--
-- Name: ix_weather_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_location ON public.weather USING btree (location);


--
-- Name: document_embeddings tsvector_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE OF chunk_text ON public.document_embeddings FOR EACH ROW EXECUTE FUNCTION public.update_search_vector();


--
-- Name: articles articles_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: articles articles_story_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_story_id_fkey FOREIGN KEY (story_id) REFERENCES public.articles(id) ON DELETE SET NULL;


--
-- Name: bus_stop_times bus_stop_times_trip_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bus_stop_times
    ADD CONSTRAINT bus_stop_times_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.bus_trips(id);


--
-- Name: business_announcements business_announcements_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_announcements
    ADD CONSTRAINT business_announcements_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.ceidg_businesses(id);


--
-- Name: business_profiles business_profiles_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_profiles
    ADD CONSTRAINT business_profiles_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.ceidg_businesses(id) ON DELETE CASCADE;


--
-- Name: business_profiles business_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_profiles
    ADD CONSTRAINT business_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chat_message_feedback chat_message_feedback_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_message_feedback
    ADD CONSTRAINT chat_message_feedback_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;


--
-- Name: chat_messages chat_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: council_sessions council_sessions_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.council_sessions
    ADD CONSTRAINT council_sessions_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: events events_canonical_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_canonical_id_fkey FOREIGN KEY (canonical_id) REFERENCES public.events(id) ON DELETE SET NULL;


--
-- Name: events events_source_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_source_article_id_fkey FOREIGN KEY (source_article_id) REFERENCES public.articles(id);


--
-- Name: newsletter_logs newsletter_logs_subscriber_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_logs
    ADD CONSTRAINT newsletter_logs_subscriber_id_fkey FOREIGN KEY (subscriber_id) REFERENCES public.newsletter_subscribers(id);


--
-- Name: newsletter_subscribers newsletter_subscribers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.newsletter_subscribers
    ADD CONSTRAINT newsletter_subscribers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: push_subscriptions push_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: referrals referrals_referred_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referred_id_fkey FOREIGN KEY (referred_id) REFERENCES public.users(id);


--
-- Name: referrals referrals_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public.users(id);


--
-- Name: report_upvotes report_upvotes_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_upvotes
    ADD CONSTRAINT report_upvotes_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.reports(id) ON DELETE CASCADE;


--
-- Name: reports reports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reports
    ADD CONSTRAINT reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: role_invitations role_invitations_used_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_invitations
    ADD CONSTRAINT role_invitations_used_by_user_id_fkey FOREIGN KEY (used_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: solectwo_post_requests solectwo_post_requests_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_requests
    ADD CONSTRAINT solectwo_post_requests_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.solectwo_posts(id) ON DELETE CASCADE;


--
-- Name: solectwo_post_requests solectwo_post_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_requests
    ADD CONSTRAINT solectwo_post_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: solectwo_post_versions solectwo_post_versions_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_post_versions
    ADD CONSTRAINT solectwo_post_versions_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.solectwo_posts(id) ON DELETE CASCADE;


--
-- Name: solectwo_posts solectwo_posts_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_posts
    ADD CONSTRAINT solectwo_posts_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.articles(id) ON DELETE SET NULL;


--
-- Name: solectwo_posts solectwo_posts_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_posts
    ADD CONSTRAINT solectwo_posts_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.user_roles(id) ON DELETE SET NULL;


--
-- Name: solectwo_posts solectwo_posts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solectwo_posts
    ADD CONSTRAINT solectwo_posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: subscriptions subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_referred_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_referred_by_fkey FOREIGN KEY (referred_by) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--


