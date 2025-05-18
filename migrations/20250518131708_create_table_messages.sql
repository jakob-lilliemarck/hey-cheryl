-- migrate:up
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL,
    is_cheryl BOOLEAN NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    message TEXT NOT NULL
);

CREATE INDEX idx_messages_conversation_id_timestamp ON messages (conversation_id, timestamp);

-- migrate:down
DROP INDEX idx_messages_conversation_id_timestamp;

DROP TABLE messages;
