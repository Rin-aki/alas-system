package com.alas.system.service;

import com.alas.system.domain.User;
import com.alas.system.repository.UserRepository;
import com.alas.system.security.JwtService;
import com.alas.system.security.PasswordService;
import io.jsonwebtoken.Claims;
import jakarta.transaction.Transactional;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.server.ResponseStatusException;

@Service
public class UserService {

    private final UserRepository userRepository;
    private final PasswordService passwordService;
    private final JwtService jwtService;
    private final EmailService emailService;
    private final int defaultServerIp;

    public UserService(
            UserRepository userRepository,
            PasswordService passwordService,
            JwtService jwtService,
            EmailService emailService,
            @org.springframework.beans.factory.annotation.Value("${app.network.default-server-ip}") int defaultServerIp
    ) {
        this.userRepository = userRepository;
        this.passwordService = passwordService;
        this.jwtService = jwtService;
        this.emailService = emailService;
        this.defaultServerIp = defaultServerIp;
    }

    @Transactional
    public Map<String, Object> register(String email, String password) {
        if (userRepository.findByEmail(email).isPresent()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "该邮箱已被注册");
        }

        int[] ips = allocateIps();
        User user = new User();
        user.setEmail(email);
        user.setPasswordHash(passwordService.hashPassword(password));
        user.setHasPurchased(false);
        user.setAlasIp(ips[0]);
        user.setBlhxIp(ips[1]);
        user.setWsIp(ips[2]);
        user.setServerIp(defaultServerIp);

        if (emailService.isEnabled()) {
            String token = UUID.randomUUID().toString();
            user.setIsActive(false);
            user.setEmailVerified(false);
            user.setVerificationToken(token);
            user.setVerificationTokenExpires(LocalDateTime.now().plusHours(24));
            userRepository.save(user);
            sendVerificationEmailAfterCommit(email, token);
        } else {
            user.setIsActive(true);
            user.setEmailVerified(true);
            userRepository.save(user);
        }

        Map<String, Object> allocatedIps = new LinkedHashMap<>();
        allocatedIps.put("alas", "10.10.10." + ips[0]);
        allocatedIps.put("blhx", "10.10.10." + ips[1]);
        allocatedIps.put("ws", "10.10.10." + ips[2]);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("msg", emailService.isEnabled() ? "注册成功，请查收验证邮件激活账户" : "注册成功");
        response.put("user_id", user.getId());
        response.put("allocated_ips", allocatedIps);
        response.put("email_verification_required", emailService.isEnabled());
        return response;
    }

    @Transactional
    public Map<String, Object> verifyEmail(String token) {
        User user = userRepository.findByVerificationToken(token)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "验证链接无效或已失效"));

        if (user.getVerificationTokenExpires() == null || LocalDateTime.now().isAfter(user.getVerificationTokenExpires())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "验证链接已过期，请重新发送验证邮件");
        }

        user.setIsActive(true);
        user.setEmailVerified(true);
        user.setVerificationToken(null);
        user.setVerificationTokenExpires(null);
        userRepository.save(user);

        return Map.of("msg", "邮箱验证成功，账户已激活，请登录");
    }

    @Transactional
    public Map<String, Object> resendVerification(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "邮箱不存在"));

        if (Boolean.TRUE.equals(user.getIsActive())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "账户已激活，请直接登录");
        }

        String token = UUID.randomUUID().toString();
        user.setVerificationToken(token);
        user.setVerificationTokenExpires(LocalDateTime.now().plusHours(24));
        userRepository.save(user);

        sendVerificationEmailAfterCommit(email, token);
        return Map.of("msg", "验证邮件已重新发送，请查收");
    }

    public LoginResult login(String email, String password) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "邮箱或密码错误"));

        if (!passwordService.verifyPassword(password, user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "邮箱或密码错误");
        }

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "账户未激活，请查收邮件进行激活");
        }

        boolean purchaseExpired = checkAndDisableExpired(user);
        String token = jwtService.createUserToken(user.getId().toString());

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("msg", "登录成功");
        body.put("token_type", "bearer");
        body.put("user_id", user.getId());
        body.put("alas_ip", user.getAlasIp() == null ? null : "10.10.10." + user.getAlasIp());
        body.put("blhx_ip", user.getBlhxIp() == null ? null : "10.10.10." + user.getBlhxIp());
        body.put("ws_ip", user.getWsIp() == null ? null : "10.10.10." + user.getWsIp());
        body.put("alas_port", 22267);
        body.put("ws_port", 8000);
        body.put("email", user.getEmail());
        body.put("has_purchased", Boolean.TRUE.equals(user.getHasPurchased()));
        body.put("purchase_expires", user.getPurchaseExpires() == null ? null : user.getPurchaseExpires().toString());
        body.put("purchase_expired", purchaseExpired);

        return new LoginResult(token, body);
    }

    @Transactional
    public Map<String, Object> purchase(User currentUser, int days) {
        currentUser.setHasPurchased(true);
        currentUser.setExpiryNotificationSent(false);
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime expires = currentUser.getPurchaseExpires();
        if (expires != null && expires.isAfter(now)) {
            currentUser.setPurchaseExpires(expires.plusDays(days));
        } else {
            currentUser.setPurchaseExpires(now.plusDays(days));
        }
        userRepository.save(currentUser);

        long remaining = Duration.between(now, currentUser.getPurchaseExpires()).toDays();
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("msg", "购买成功");
        response.put("has_purchased", true);
        response.put("purchase_expires", currentUser.getPurchaseExpires().toString());
        response.put("days_remaining", Math.max(remaining, 0));
        return response;
    }

    @Transactional
    public Map<String, Object> purchaseStatus(User currentUser) {
        boolean purchaseExpired = checkAndDisableExpired(currentUser);
        long daysRemaining = 0;
        if (Boolean.TRUE.equals(currentUser.getHasPurchased()) && currentUser.getPurchaseExpires() != null) {
            daysRemaining = Duration.between(LocalDateTime.now(), currentUser.getPurchaseExpires()).toDays();
            if (daysRemaining < 0) {
                daysRemaining = 0;
            }
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("has_purchased", Boolean.TRUE.equals(currentUser.getHasPurchased()));
        response.put("purchase_expires", currentUser.getPurchaseExpires() == null ? null : currentUser.getPurchaseExpires().toString());
        response.put("days_remaining", daysRemaining);
        response.put("purchase_expired", purchaseExpired);
        return response;
    }

    public Map<String, Object> userInfo(User user) {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("user_id", user.getId());
        response.put("email", user.getEmail());
        response.put("is_active", Boolean.TRUE.equals(user.getIsActive()));
        response.put("alas_ip", user.getAlasIp() == null ? null : "10.10.10." + user.getAlasIp());
        response.put("blhx_ip", user.getBlhxIp() == null ? null : "10.10.10." + user.getBlhxIp());
        response.put("ws_ip", user.getWsIp() == null ? null : "10.10.10." + user.getWsIp());
        response.put("alas_port", 22267);
        response.put("ws_port", 8000);
        response.put("has_purchased", Boolean.TRUE.equals(user.getHasPurchased()));
        response.put("purchase_expires", user.getPurchaseExpires() == null ? null : user.getPurchaseExpires().toString());
        return response;
    }

    public Optional<User> fromAccessToken(String token) {
        Optional<Claims> claims = jwtService.parseUserToken(token);
        if (claims.isEmpty()) {
            return Optional.empty();
        }
        String subject = claims.get().getSubject();
        if (subject == null) {
            return Optional.empty();
        }
        try {
            return userRepository.findById(Integer.parseInt(subject));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }

    @Transactional
    public int disableExpiredPurchases() {
        int changed = 0;
        LocalDateTime now = LocalDateTime.now();
        for (User user : userRepository.findAll()) {
            if (Boolean.TRUE.equals(user.getHasPurchased()) && user.getPurchaseExpires() != null && user.getPurchaseExpires().isBefore(now)) {
                user.setHasPurchased(false);
                userRepository.save(user);
                changed++;
            }
        }
        return changed;
    }

    @Transactional
    public int sendExpiryNotifications() {
        if (!emailService.isEnabled()) {
            return 0;
        }
        int sent = 0;
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime threshold = now.plusDays(3);
        for (User user : userRepository.findAll()) {
            if (Boolean.TRUE.equals(user.getHasPurchased())
                    && user.getPurchaseExpires() != null
                    && user.getPurchaseExpires().isAfter(now)
                    && user.getPurchaseExpires().isBefore(threshold)
                    && !Boolean.TRUE.equals(user.getExpiryNotificationSent())) {
                long daysRemaining = Duration.between(now, user.getPurchaseExpires()).toDays();
                emailService.sendExpiryNotification(user.getEmail(), daysRemaining, user.getPurchaseExpires());
                user.setExpiryNotificationSent(true);
                userRepository.save(user);
                sent++;
            }
        }
        return sent;
    }

    public Map<String, Object> authCheck(String token) {
        if (token == null || token.isBlank()) {
            return Map.of("is_authenticated", false);
        }
        Optional<Claims> claims = jwtService.parseUserToken(token);
        if (claims.isEmpty() || claims.get().getSubject() == null) {
            return Map.of("is_authenticated", false);
        }
        return Map.of(
                "is_authenticated", true,
                "user_id", claims.get().getSubject(),
                "expires_at", claims.get().getExpiration().toInstant().getEpochSecond()
        );
    }

    private boolean checkAndDisableExpired(User user) {
        if (Boolean.TRUE.equals(user.getHasPurchased())
                && user.getPurchaseExpires() != null
                && user.getPurchaseExpires().isBefore(LocalDateTime.now())) {
            user.setHasPurchased(false);
            userRepository.save(user);
            return true;
        }
        return false;
    }

    private int[] allocateIps() {
        Set<Integer> used = new HashSet<>();
        for (User user : userRepository.findAll()) {
            if (user.getAlasIp() != null) {
                used.add(user.getAlasIp());
            }
            if (user.getBlhxIp() != null) {
                used.add(user.getBlhxIp());
            }
            if (user.getWsIp() != null) {
                used.add(user.getWsIp());
            }
        }

        int[] result = new int[3];
        int index = 0;
        for (int ip = 30; ip < 119; ip++) {
            if (!used.contains(ip)) {
                result[index++] = ip;
                if (index == 3) {
                    return result;
                }
            }
        }
        throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "可用IP不足，无法分配");
    }

    private void sendVerificationEmailAfterCommit(String email, String token) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            emailService.sendVerificationEmail(email, token);
            return;
        }

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                emailService.sendVerificationEmail(email, token);
            }
        });
    }

    public record LoginResult(String token, Map<String, Object> body) {
    }
}
