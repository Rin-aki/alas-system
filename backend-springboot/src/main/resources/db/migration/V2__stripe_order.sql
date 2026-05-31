CREATE TABLE IF NOT EXISTS stripe_order (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    plan_id    VARCHAR(50)  NOT NULL,
    days       INT          NOT NULL,
    amount     INT          NOT NULL,
    status     VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at DATETIME     NOT NULL,
    paid_at    DATETIME     NULL,
    INDEX idx_stripe_order_user_id (user_id)
);
