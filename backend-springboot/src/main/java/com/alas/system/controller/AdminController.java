package com.alas.system.controller;

import com.alas.system.security.CookieFactory;
import com.alas.system.security.JwtService;
import com.alas.system.service.AdminService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping
@Validated
public class AdminController {

    private final AdminService adminService;
    private final CookieFactory cookieFactory;
    private final JwtService jwtService;

    public AdminController(AdminService adminService, CookieFactory cookieFactory, JwtService jwtService) {
        this.adminService = adminService;
        this.cookieFactory = cookieFactory;
        this.jwtService = jwtService;
    }

    @PostMapping("/admin/login")
    public ResponseEntity<Map<String, Object>> login(@Valid @RequestBody AdminLoginRequest request) {
        String token = adminService.login(request.username(), request.password());
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookieFactory.adminCookie(token, jwtService.getAdminExpireMinutes()).toString())
                .body(Map.of("msg", "管理员登录成功", "token_type", "bearer"));
    }

    @PostMapping("/admin/logout")
    public ResponseEntity<Map<String, Object>> logout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookieFactory.clearAdminCookie().toString())
                .body(Map.of("msg", "管理员已登出"));
    }

    @GetMapping("/admin/check")
    public Map<String, Object> adminCheck(@CookieValue(value = "admin_token", required = false) String adminToken) {
        return adminService.check(adminToken);
    }

    @GetMapping("/announcement/latest")
    public Object latestAnnouncement() {
        return adminService.latestAnnouncement();
    }

    @GetMapping("/system/status")
    public Map<String, Object> systemStatus() {
        return adminService.systemStatus();
    }

    @PostMapping("/admin/announcement")
    public Map<String, Object> createAnnouncement(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @Valid @RequestBody AnnouncementRequest request
    ) {
        mustAdmin(adminToken);
        return adminService.createAnnouncement(request.title(), request.content());
    }

    @PostMapping("/admin/maintenance")
    public Map<String, Object> updateMaintenance(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @Valid @RequestBody MaintenanceRequest request
    ) {
        mustAdmin(adminToken);
        return adminService.updateMaintenance(request.isMaintenance(), request.maintenanceMessage());
    }

    @GetMapping("/admin/users")
    public List<Map<String, Object>> listUsers(
            @CookieValue(value = "admin_token", required = false) String adminToken
    ) {
        mustAdmin(adminToken);
        return adminService.listUsers();
    }

    @PostMapping("/admin/users/{id}/extend")
    public Map<String, Object> extendPurchase(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @PathVariable int id,
            @RequestBody ExtendPurchaseRequest request
    ) {
        mustAdmin(adminToken);
        return adminService.extendPurchase(id, request.months());
    }

    @PostMapping("/admin/users/{id}/purchase")
    public Map<String, Object> setPurchaseStatus(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @PathVariable int id,
            @RequestBody PurchaseRequest request
    ) {
        mustAdmin(adminToken);
        return adminService.setPurchaseStatus(id, request.hasPurchased(), request.expiresAt());
    }

    @PostMapping("/admin/users/{id}/active")
    public Map<String, Object> setUserActive(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @PathVariable int id,
            @RequestBody SetActiveRequest request
    ) {
        mustAdmin(adminToken);
        return adminService.setUserActive(id, request.active());
    }

    @GetMapping("/admin/announcements")
    public List<Map<String, Object>> listAnnouncements(
            @CookieValue(value = "admin_token", required = false) String adminToken
    ) {
        mustAdmin(adminToken);
        return adminService.listAnnouncements();
    }

    @DeleteMapping("/admin/announcement/{id}")
    public Map<String, Object> deleteAnnouncement(
            @CookieValue(value = "admin_token", required = false) String adminToken,
            @PathVariable int id
    ) {
        mustAdmin(adminToken);
        return adminService.deleteAnnouncement(id);
    }

    private void mustAdmin(String adminToken) {
        if (!adminService.validateAdminToken(adminToken)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "需要管理员权限");
        }
    }

    public record AdminLoginRequest(@NotBlank String username, @NotBlank String password) {
    }

    public record AnnouncementRequest(@NotBlank String title, @NotBlank String content) {
    }

    public record MaintenanceRequest(boolean isMaintenance, @NotBlank String maintenanceMessage) {
    }

    public record ExtendPurchaseRequest(int months) {
    }

    public record SetActiveRequest(boolean active) {
    }

    public record PurchaseRequest(boolean hasPurchased, String expiresAt) {
    }
}
