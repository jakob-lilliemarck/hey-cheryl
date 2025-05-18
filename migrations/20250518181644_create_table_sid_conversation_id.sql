-- migrate:up
CREATE TABLE sid_conversation_ids (
    sid UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_sid_conversation_ids_sid ON sid_conversation_ids (sid);

-- migrate:down
DROP INDEX idx_sid_conversation_ids_sid;

DROP TABLE sid_conversation_ids;
