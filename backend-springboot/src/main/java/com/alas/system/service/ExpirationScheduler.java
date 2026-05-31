package com.alas.system.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ExpirationScheduler {

    private static final Logger log = LoggerFactory.getLogger(ExpirationScheduler.class);
    private final UserService userService;

    public ExpirationScheduler(UserService userService) {
        this.userService = userService;
    }

    @Scheduled(fixedDelay = 60 * 60 * 1000)
    public void checkExpirationHourly() {
        int changed = userService.disableExpiredPurchases();
        if (changed > 0) {
            log.info("Disabled {} expired purchases", changed);
        }
    }

    // 每天凌晨 2 点检查并发送到期提醒邮件
    @Scheduled(cron = "0 0 2 * * *", zone = "Asia/Shanghai")
    public void sendExpiryNotificationsDaily() {
        int sent = userService.sendExpiryNotifications();
        if (sent > 0) {
            log.info("Sent {} expiry notification emails", sent);
        }
    }
}
