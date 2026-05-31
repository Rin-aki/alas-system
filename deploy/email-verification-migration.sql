-- 邮箱验证与到期提醒功能数据库迁移
-- 执行前请备份数据库

ALTER TABLE `user`
    ADD COLUMN `email_verified`            TINYINT(1)   DEFAULT 0    COMMENT '邮箱是否已验证',
    ADD COLUMN `verification_token`        VARCHAR(255) DEFAULT NULL  COMMENT '邮箱验证 token',
    ADD COLUMN `verification_token_expires` DATETIME    DEFAULT NULL  COMMENT '验证 token 过期时间',
    ADD COLUMN `expiry_notification_sent`  TINYINT(1)   DEFAULT 0    COMMENT '到期提醒邮件是否已发送';

-- 将已有用户标记为邮箱已验证（存量用户跳过验证流程）
UPDATE `user` SET `email_verified` = 1 WHERE `is_active` = 1;

-- 为 verification_token 列添加索引，加速 token 查找
CREATE INDEX idx_user_verification_token ON `user` (`verification_token`);
