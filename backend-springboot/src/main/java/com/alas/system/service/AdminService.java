package com.alas.system.service;

import com.alas.system.domain.Announcement;
import com.alas.system.domain.SystemStatus;
import com.alas.system.domain.User;
import com.alas.system.repository.AnnouncementRepository;
import com.alas.system.repository.SystemStatusRepository;
import com.alas.system.repository.UserRepository;
import com.alas.system.security.JwtService;
import io.jsonwebtoken.Claims;
import jakarta.transaction.Transactional;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AdminService {

    private final String adminUsername;
    private final String adminPassword;
    private final JwtService jwtService;
    private final AnnouncementRepository announcementRepository;
    private final SystemStatusRepository systemStatusRepository;
    private final UserRepository userRepository;

    public AdminService(
            @Value("${app.admin.username}") String adminUsername,
            @Value("${app.admin.password}") String adminPassword,
            JwtService jwtService,
            AnnouncementRepository announcementRepository,
            SystemStatusRepository systemStatusRepository,
            UserRepository userRepository
    ) {
        this.adminUsername = adminUsername;
        this.adminPassword = adminPassword;
        this.jwtService = jwtService;
        this.announcementRepository = announcementRepository;
        this.systemStatusRepository = systemStatusRepository;
        this.userRepository = userRepository;
    }

    public String login(String username, String password) {
        if (!adminUsername.equals(username) || !adminPassword.equals(password)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "用户名或密码错误");
        }
        return jwtService.createAdminToken("admin");
    }

    public Map<String, Object> check(String token) {
        if (token == null || token.isBlank()) {
            return Map.of("is_admin", false);
        }
        Optional<Claims> claims = jwtService.parseAdminToken(token);
        if (claims.isEmpty() || !"admin".equals(claims.get().get("role", String.class))) {
            return Map.of("is_admin", false);
        }
        return Map.of(
                "is_admin", true,
                "expires_at", claims.get().getExpiration().toInstant().getEpochSecond()
        );
    }

    public boolean validateAdminToken(String token) {
        Optional<Claims> claims = jwtService.parseAdminToken(token);
        return claims.isPresent() && "admin".equals(claims.get().get("role", String.class));
    }

    public Map<String, Object> latestAnnouncement() {
        Optional<Announcement> current = announcementRepository.findFirstByIsActiveTrueOrderByCreatedAtDesc();
        if (current.isEmpty()) {
            return null;
        }
        Announcement a = current.get();
        return Map.of(
                "id", a.getId(),
                "title", a.getTitle(),
                "content", a.getContent(),
                "created_at", a.getCreatedAt().toString()
        );
    }

    @Transactional
    public Map<String, Object> createAnnouncement(String title, String content) {
        announcementRepository.findAll().forEach(a -> {
            if (Boolean.TRUE.equals(a.getIsActive())) {
                a.setIsActive(false);
                announcementRepository.save(a);
            }
        });

        Announcement announcement = new Announcement();
        announcement.setTitle(title);
        announcement.setContent(content);
        announcement.setCreatedAt(LocalDateTime.now());
        announcement.setIsActive(true);
        Announcement saved = announcementRepository.save(announcement);

        return Map.of(
                "success", true,
                "message", "公告发布成功",
                "announcement_id", saved.getId()
        );
    }

    @Transactional
    public Map<String, Object> updateMaintenance(boolean isMaintenance, String maintenanceMessage) {
        SystemStatus status = systemStatusRepository.findById(1).orElseGet(() -> {
            SystemStatus s = new SystemStatus();
            s.setId(1);
            return s;
        });
        status.setIsMaintenance(isMaintenance);
        status.setMaintenanceMessage(maintenanceMessage);
        systemStatusRepository.save(status);

        return Map.of(
                "success", true,
                "message", "维护状态更新成功",
                "is_maintenance", isMaintenance
        );
    }

    public List<Map<String, Object>> listUsers() {
        return userRepository.findAll().stream()
                .sorted(Comparator.comparing(User::getId))
                .map(u -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("id", u.getId());
                    m.put("email", u.getEmail());
                    m.put("is_active", Boolean.TRUE.equals(u.getIsActive()));
                    m.put("has_purchased", Boolean.TRUE.equals(u.getHasPurchased()));
                    m.put("purchase_expires", u.getPurchaseExpires() == null ? null : u.getPurchaseExpires().toString());
                    return m;
                })
                .collect(Collectors.toList());
    }

    @Transactional
    public Map<String, Object> extendPurchase(int userId, int months) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));

        LocalDateTime now = LocalDateTime.now();
        LocalDateTime base = (user.getPurchaseExpires() != null && user.getPurchaseExpires().isAfter(now))
                ? user.getPurchaseExpires() : now;

        user.setPurchaseExpires(base.plusMonths(months));
        user.setHasPurchased(true);
        userRepository.save(user);

        return Map.of(
                "success", true,
                "message", "到期时间已更新",
                "purchase_expires", user.getPurchaseExpires().toString()
        );
    }

    @Transactional
    public Map<String, Object> setPurchaseStatus(int userId, boolean hasPurchased, String expiresAt) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));

        user.setHasPurchased(hasPurchased);
        if (expiresAt != null && !expiresAt.isBlank()) {
            user.setPurchaseExpires(LocalDateTime.parse(expiresAt));
        }
        userRepository.save(user);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", true);
        result.put("has_purchased", user.getHasPurchased());
        result.put("purchase_expires", user.getPurchaseExpires() == null ? null : user.getPurchaseExpires().toString());
        return result;
    }

    @Transactional
    public Map<String, Object> setUserActive(int userId, boolean active) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在"));

        user.setIsActive(active);
        userRepository.save(user);

        return Map.of(
                "success", true,
                "message", active ? "用户已激活" : "用户已禁用",
                "is_active", active
        );
    }

    public List<Map<String, Object>> listAnnouncements() {
        return announcementRepository.findAll().stream()
                .sorted(Comparator.comparing(Announcement::getCreatedAt).reversed())
                .map(a -> {
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("id", a.getId());
                    m.put("title", a.getTitle());
                    m.put("created_at", a.getCreatedAt().toString());
                    m.put("is_active", Boolean.TRUE.equals(a.getIsActive()));
                    return m;
                })
                .collect(Collectors.toList());
    }

    @Transactional
    public Map<String, Object> deleteAnnouncement(int id) {
        if (!announcementRepository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "公告不存在");
        }
        announcementRepository.deleteById(id);
        return Map.of("success", true, "message", "公告已删除");
    }

    @Transactional
    public Map<String, Object> systemStatus() {
        SystemStatus status = systemStatusRepository.findById(1).orElseGet(() -> {
            SystemStatus s = new SystemStatus();
            s.setId(1);
            s.setIsMaintenance(false);
            s.setMaintenanceMessage("系统维护中，请稍后再试");
            return systemStatusRepository.save(s);
        });

        return Map.of(
                "is_maintenance", Boolean.TRUE.equals(status.getIsMaintenance()),
                "maintenance_message", status.getMaintenanceMessage() == null ? "系统维护中，请稍后再试" : status.getMaintenanceMessage()
        );
    }
}
