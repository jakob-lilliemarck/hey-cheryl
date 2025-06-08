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
    id uuid NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    concept text NOT NULL,
    meaning text NOT NULL,
    deleted boolean NOT NULL
);


--
-- Name: latest_concepts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.latest_concepts AS
 SELECT id,
    "timestamp",
    concept,
    meaning,
    deleted
   FROM ( SELECT DISTINCT ON (concepts.id) concepts.id,
            concepts."timestamp",
            concepts.concept,
            concepts.meaning,
            concepts.deleted
           FROM public.concepts
          ORDER BY concepts.id, concepts."timestamp" DESC) unnamed_subquery
  WHERE (deleted = false);


--
-- Name: replies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.replies (
    id uuid NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    message_id uuid NOT NULL,
    status text NOT NULL,
    message text
);


--
-- Name: latest_replies; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.latest_replies AS
 SELECT DISTINCT ON (id) id,
    "timestamp",
    message_id,
    status,
    message
   FROM public.replies
  ORDER BY id, "timestamp" DESC;


--
-- Name: system_prompts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_prompts (
    key text NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    prompt text NOT NULL,
    approved boolean DEFAULT false NOT NULL
);


--
-- Name: latest_system_prompts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.latest_system_prompts AS
 SELECT DISTINCT ON (key) key,
    "timestamp",
    prompt
   FROM public.system_prompts
  ORDER BY key, "timestamp" DESC;


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    event text NOT NULL
);


--
-- Name: latest_user_sessions; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.latest_user_sessions AS
 SELECT DISTINCT ON (id) id,
    user_id,
    "timestamp",
    event
   FROM public.user_sessions
  ORDER BY id, "timestamp" DESC;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    message text NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    name text NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);


--
-- Name: concepts concepts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts
    ADD CONSTRAINT concepts_pkey PRIMARY KEY (id, "timestamp");


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: replies replies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.replies
    ADD CONSTRAINT replies_pkey PRIMARY KEY (id, "timestamp");


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: system_prompts system_prompts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_prompts
    ADD CONSTRAINT system_prompts_pkey PRIMARY KEY (key, "timestamp");


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id, "timestamp");


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_system_prompts_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_prompts_key ON public.system_prompts USING btree (key);


--
-- Name: idx_user_sessions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_id ON public.user_sessions USING btree (id);


--
-- Name: idx_user_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_user_id ON public.user_sessions USING btree (user_id);


--
-- Name: messages messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: replies replies_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.replies
    ADD CONSTRAINT replies_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id);


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20250525155138'),
    ('20250608101345');
