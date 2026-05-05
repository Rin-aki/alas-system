package com.alas.system.websocket;

import com.alas.system.domain.User;
import com.alas.system.repository.UserRepository;
import com.alas.system.security.JwtService;
import io.jsonwebtoken.Claims;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
public class FixWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(FixWebSocketHandler.class);

    private final JwtService jwtService;
    private final UserRepository userRepository;
    private final String sshHostPrefix;
    private final String sshUser;
    private final String sshPassword;
    private final int defaultServerIp;

    public FixWebSocketHandler(
            JwtService jwtService,
            UserRepository userRepository,
            @Value("${app.network.ssh-host-prefix}") String sshHostPrefix,
            @Value("${app.network.ssh-user}") String sshUser,
            @Value("${app.network.ssh-password}") String sshPassword,
            @Value("${app.network.default-server-ip}") int defaultServerIp
    ) {
        this.jwtService = jwtService;
        this.userRepository = userRepository;
        this.sshHostPrefix = sshHostPrefix;
        this.sshUser = sshUser;
        this.sshPassword = sshPassword;
        this.defaultServerIp = defaultServerIp;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        String token = extractToken(session);
        if (token == null) {
            sendAndClose(session, "❌ 认证失败：缺少访问令牌");
            return;
        }

        Optional<Claims> claims = jwtService.parseUserToken(token);
        if (claims.isEmpty() || claims.get().getSubject() == null) {
            sendAndClose(session, "❌ 认证失败：无效的访问令牌");
            return;
        }

        int userId;
        try {
            userId = Integer.parseInt(claims.get().getSubject());
        } catch (NumberFormatException e) {
            sendAndClose(session, "❌ 认证失败：无效的用户标识");
            return;
        }

        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isEmpty()) {
            sendAndClose(session, "❌ 认证失败：用户不存在");
            return;
        }

        User user = userOpt.get();
        if (user.getServerIp() == null) {
            user.setServerIp(defaultServerIp);
        }

        new Thread(() -> runFix(session, user)).start();
    }

    private void runFix(WebSocketSession session, User user) {
        String host = sshHostPrefix + user.getServerIp();
        int userId = user.getId();
        String email = user.getEmail();

        List<String> containers = List.of(
                "blhx_" + userId,
                "alas_" + userId
        );

        try {
            send(session, "✅ 用户认证成功: " + email);
            send(session, "🔧 开始修复服务（服务器：" + host + "）...");
            send(session, "📋 准备重启以下容器:");
            for (String c : containers) {
                send(session, "  ➤ " + c);
            }

            int success = 0;
            int fail = 0;

            for (String containerName : containers) {
                send(session, "\n🔄 正在重启容器: " + containerName);

                ProcessBuilder pb = new ProcessBuilder(
                        "sshpass", "-p", sshPassword,
                        "ssh", "-o", "StrictHostKeyChecking=no",
                        sshUser + "@" + host,
                        "docker restart " + containerName
                );
                pb.redirectOutput(ProcessBuilder.Redirect.DISCARD);

                try {
                    Process proc = pb.start();
                    boolean done = proc.waitFor(30, TimeUnit.SECONDS);
                    if (!done) {
                        proc.destroyForcibly();
                        send(session, "  ⚠️ " + containerName + " 重启超时");
                        fail++;
                    } else if (proc.exitValue() == 0) {
                        send(session, "  ✅ " + containerName + " 重启成功");
                        success++;
                    } else {
                        byte[] errBytes = proc.getErrorStream().readAllBytes();
                        String err = new String(errBytes, StandardCharsets.UTF_8).trim();
                        send(session, "  ❌ " + containerName + " 重启失败: " + truncate(err, 100));
                        fail++;
                    }
                } catch (Exception e) {
                    send(session, "  ❌ " + containerName + " 重启出错: " + truncate(e.getMessage(), 100));
                    fail++;
                }
            }

            send(session, "\n🎉 服务修复完成！");
            send(session, "📝 修复总结:");
            send(session, "  ➤ 用户: " + email + " (ID: " + userId + ")");
            send(session, "  ➤ 服务器: " + host);
            send(session, "  ➤ 成功重启: " + success + " 个容器");
            if (fail > 0) {
                send(session, "  ➤ 失败: " + fail + " 个容器");
            }
            send(session, "✨ 即将返回控制台...");
            log.info("修复完成 - 用户: {} (ID: {}), 服务器: {}, 成功: {}, 失败: {}", email, userId, host, success, fail);
        } catch (Exception e) {
            log.error("修复服务时发生错误", e);
            trySend(session, "\n❌ 修复过程中发生错误: " + truncate(e.getMessage(), 100));
        } finally {
            try {
                session.close(CloseStatus.NORMAL);
            } catch (IOException ignored) {
            }
        }
    }

    private String extractToken(WebSocketSession session) {
        String cookieHeader = session.getHandshakeHeaders().getFirst("Cookie");
        if (cookieHeader == null) return null;
        for (String part : cookieHeader.split(";")) {
            String[] kv = part.trim().split("=", 2);
            if (kv.length == 2 && "access_token".equals(kv[0].trim())) {
                return kv[1].trim();
            }
        }
        return null;
    }

    private void send(WebSocketSession session, String text) throws IOException {
        if (session.isOpen()) {
            session.sendMessage(new TextMessage(text));
        }
    }

    private void trySend(WebSocketSession session, String text) {
        try {
            send(session, text);
        } catch (IOException ignored) {
        }
    }

    private void sendAndClose(WebSocketSession session, String text) {
        trySend(session, text);
        try {
            session.close(CloseStatus.POLICY_VIOLATION);
        } catch (IOException ignored) {
        }
    }

    private String truncate(String s, int maxLen) {
        if (s == null) return "未知错误";
        return s.length() > maxLen ? s.substring(0, maxLen) : s;
    }
}
