package com.alas.system.service;

import com.alas.system.domain.User;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class ReconnectService {

    private final String sshHostPrefix;
    private final String sshUser;
    private final String sshPassword;
    private final int defaultServerIp;

    public ReconnectService(
            @Value("${app.network.ssh-host-prefix}") String sshHostPrefix,
            @Value("${app.network.ssh-user}") String sshUser,
            @Value("${app.network.ssh-password}") String sshPassword,
            @Value("${app.network.default-server-ip}") int defaultServerIp
    ) {
        this.sshHostPrefix = sshHostPrefix;
        this.sshUser = sshUser;
        this.sshPassword = sshPassword;
        this.defaultServerIp = defaultServerIp;
    }

    public Map<String, Object> reconnect(User user) {
        String containerName = "ws-scrcpy_" + user.getId();
        int serverIp = user.getServerIp() != null ? user.getServerIp() : defaultServerIp;
        String host = sshHostPrefix + serverIp;
        String cmd = "docker restart " + containerName;

        ProcessBuilder pb = new ProcessBuilder(
                "sshpass", "-p", sshPassword,
                "ssh", "-o", "StrictHostKeyChecking=no",
                sshUser + "@" + host,
                cmd
        );

        try {
            Process process = pb.start();
            boolean finished = process.waitFor(Duration.ofSeconds(30).toSeconds(), TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                return Map.of(
                        "success", false,
                        "message", "容器 " + containerName + " 重启超时",
                        "error", "操作超时（30秒）",
                        "user_email", user.getEmail(),
                        "user_id", user.getId(),
                        "container", containerName,
                        "server", host
                );
            }

            String stderr = readStream(process.getErrorStream());
            if (process.exitValue() == 0) {
                return Map.of(
                        "success", true,
                        "message", "容器 " + containerName + " 重启成功",
                        "user_email", user.getEmail(),
                        "user_id", user.getId(),
                        "container", containerName,
                        "server", host
                );
            }
            return Map.of(
                    "success", false,
                    "message", "容器 " + containerName + " 重启失败",
                    "error", stderr.length() > 200 ? stderr.substring(0, 200) : stderr,
                    "user_email", user.getEmail(),
                    "user_id", user.getId(),
                    "container", containerName,
                    "server", host
            );
        } catch (Exception e) {
            String error = e.getMessage() == null ? "未知错误" : e.getMessage();
            return Map.of(
                    "success", false,
                    "message", "容器 " + containerName + " 重启出错",
                    "error", error.length() > 200 ? error.substring(0, 200) : error,
                    "user_email", user.getEmail(),
                    "user_id", user.getId(),
                    "container", containerName,
                    "server", host
            );
        }
    }

    private String readStream(java.io.InputStream inputStream) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }
}
