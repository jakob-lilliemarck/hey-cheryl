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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: concepts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.concepts (
    id integer NOT NULL,
    concept text NOT NULL,
    meaning text NOT NULL
);


--
-- Name: concepts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.concepts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: concepts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.concepts_id_seq OWNED BY public.concepts.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id integer NOT NULL,
    conversation_id uuid NOT NULL,
    is_cheryl boolean NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    message text NOT NULL
);


--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: sid_conversation_ids; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sid_conversation_ids (
    sid uuid NOT NULL,
    conversation_id uuid NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);


--
-- Name: concepts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts ALTER COLUMN id SET DEFAULT nextval('public.concepts_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: concepts concepts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts
    ADD CONSTRAINT concepts_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sid_conversation_ids sid_conversation_ids_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sid_conversation_ids
    ADD CONSTRAINT sid_conversation_ids_pkey PRIMARY KEY (sid);


--
-- Name: idx_messages_conversation_id_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_conversation_id_timestamp ON public.messages USING btree (conversation_id, "timestamp");


--
-- Name: idx_sid_conversation_ids_sid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sid_conversation_ids_sid ON public.sid_conversation_ids USING btree (sid);


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20250518131704'),
    ('20250518131708'),
    ('20250518181644');
