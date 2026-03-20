CREATE TABLE IF NOT EXISTS telegram_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    chat_type VARCHAR(32) NOT NULL CHECK (chat_type IN ('private', 'group', 'supergroup', 'channel')),
    title VARCHAR(255) NULL,
    username VARCHAR(255) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_message_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (owner_user_id, chat_id)
);

CREATE INDEX IF NOT EXISTS telegram_chats_owner_user_id_idx ON telegram_chats (owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS telegram_chats_chat_type_idx ON telegram_chats (chat_type);

CREATE TABLE IF NOT EXISTS telegram_messages (
    id BIGSERIAL PRIMARY KEY,
    telegram_chat_id UUID NOT NULL REFERENCES telegram_chats(id) ON DELETE CASCADE,
    telegram_message_id BIGINT NOT NULL,
    telegram_user_id BIGINT NULL,
    sender_name VARCHAR(255) NULL,
    sender_username VARCHAR(255) NULL,
    text_content TEXT NOT NULL,
    message_type VARCHAR(32) NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'command', 'summary', 'analysis', 'system')),
    reply_to_message_id BIGINT NULL,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (telegram_chat_id, telegram_message_id)
);

CREATE INDEX IF NOT EXISTS telegram_messages_chat_created_at_idx ON telegram_messages (telegram_chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS telegram_messages_sender_idx ON telegram_messages (telegram_chat_id, telegram_user_id, created_at DESC);

DROP TRIGGER IF EXISTS telegram_chats_set_updated_at ON telegram_chats;
CREATE TRIGGER telegram_chats_set_updated_at BEFORE UPDATE ON telegram_chats
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS telegram_messages_set_updated_at ON telegram_messages;
CREATE TRIGGER telegram_messages_set_updated_at BEFORE UPDATE ON telegram_messages
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
