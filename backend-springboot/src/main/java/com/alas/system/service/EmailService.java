package com.alas.system.service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

@Service
public class EmailService {

    private static final Logger log = LoggerFactory.getLogger(EmailService.class);
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    @Autowired(required = false)
    private JavaMailSender mailSender;

    @Value("${app.email.enabled:false}")
    private boolean enabled;

    @Value("${app.email.from:noreply@alas.system}")
    private String from;

    @Value("${app.email.frontend-base-url:http://localhost:4173}")
    private String frontendBaseUrl;

    public boolean isEnabled() {
        return enabled && mailSender != null;
    }

    public void sendVerificationEmail(String to, String token) {
        if (!isEnabled()) {
            log.warn("邮件功能未启用，跳过发送验证邮件至 {}", to);
            return;
        }
        String link = frontendBaseUrl + "/verify-email?token=" + token;
        String html = buildVerificationHtml(link);
        send(to, "【ALAS系统】请验证您的邮箱", html);
    }

    public void sendExpiryNotification(String to, long daysRemaining, LocalDateTime expiresAt) {
        if (!isEnabled()) {
            log.warn("邮件功能未启用，跳过发送到期提醒至 {}", to);
            return;
        }
        String html = buildExpiryHtml(daysRemaining, expiresAt);
        send(to, "【ALAS系统】您的订阅即将到期", html);
    }

    private void send(String to, String subject, String html) {
        try {
            var message = mailSender.createMimeMessage();
            var helper = new MimeMessageHelper(message, false, "UTF-8");
            helper.setFrom(from);
            helper.setTo(to);
            helper.setSubject(subject);
            helper.setText(html, true);
            mailSender.send(message);
            log.info("邮件已发送至 {}: {}", to, subject);
        } catch (Exception e) {
            log.error("发送邮件至 {} 失败: {}", to, e.getMessage(), e);
        }
    }

    private String buildVerificationHtml(String link) {
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f6fb;padding:40px 0;margin:0">
                  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:40px 36px;box-shadow:0 2px 12px rgba(0,0,0,.08)">
                    <h2 style="color:#2d5be3;margin:0 0 8px">ALAS 系统</h2>
                    <p style="color:#666;margin:0 0 28px;font-size:14px">AzurLane AutoScript 管理平台</p>
                    <h3 style="color:#1a1a1a;margin:0 0 16px">验证您的邮箱地址</h3>
                    <p style="color:#444;line-height:1.7">感谢您注册 ALAS 系统！请点击下方按钮完成邮箱验证，激活您的账户。</p>
                    <p style="color:#444;line-height:1.7">此链接 <strong>24 小时</strong>内有效，过期后需重新发送验证邮件。</p>
                    <div style="text-align:center;margin:32px 0">
                      <a href="%s" style="display:inline-block;padding:14px 40px;background:linear-gradient(90deg,#409eff,#36d1dc);color:#fff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:bold">
                        验证邮箱
                      </a>
                    </div>
                    <p style="color:#999;font-size:12px;line-height:1.6">如果按钮无法点击，请复制以下链接到浏览器：<br>
                    <span style="color:#409eff;word-break:break-all">%s</span></p>
                    <hr style="border:none;border-top:1px solid #eee;margin:28px 0">
                    <p style="color:#bbb;font-size:12px;margin:0">如果您没有注册 ALAS 系统，请忽略此邮件。</p>
                  </div>
                </body>
                </html>
                """.formatted(link, link);
    }

    private String buildExpiryHtml(long daysRemaining, LocalDateTime expiresAt) {
        String expiryStr = expiresAt.format(DATE_FMT);
        String urgency = daysRemaining <= 1 ? "color:#e53e3e;font-weight:bold" : "color:#e07a00;font-weight:bold";
        return """
                <!DOCTYPE html>
                <html>
                <body style="font-family:Arial,sans-serif;background:#f4f6fb;padding:40px 0;margin:0">
                  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:40px 36px;box-shadow:0 2px 12px rgba(0,0,0,.08)">
                    <h2 style="color:#2d5be3;margin:0 0 8px">ALAS 系统</h2>
                    <p style="color:#666;margin:0 0 28px;font-size:14px">AzurLane AutoScript 管理平台</p>
                    <h3 style="color:#1a1a1a;margin:0 0 16px">📢 订阅即将到期提醒</h3>
                    <p style="color:#444;line-height:1.7">您好，您在 ALAS 系统的订阅服务即将到期，请及时续费以避免服务中断。</p>
                    <div style="background:#fff8f0;border:1px solid #fcd0a0;border-radius:8px;padding:20px 24px;margin:24px 0">
                      <p style="margin:0 0 8px;color:#666;font-size:14px">到期时间</p>
                      <p style="margin:0 0 12px;font-size:18px;color:#1a1a1a;font-weight:bold">%s</p>
                      <p style="margin:0;font-size:14px">剩余时间：<span style="%s">%d 天</span></p>
                    </div>
                    <p style="color:#444;line-height:1.7">如需续费，请登录 ALAS 系统控制台操作，或联系管理员。</p>
                    <hr style="border:none;border-top:1px solid #eee;margin:28px 0">
                    <p style="color:#bbb;font-size:12px;margin:0">此为系统自动发送的提醒邮件，请勿回复。</p>
                  </div>
                </body>
                </html>
                """.formatted(expiryStr, urgency, daysRemaining);
    }
}
