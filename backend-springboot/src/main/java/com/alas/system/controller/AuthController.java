package com.alas.system.controller;

import com.alas.system.domain.User;
import com.alas.system.security.CookieFactory;
import com.alas.system.security.JwtService;
import com.alas.system.service.ReconnectService;
import com.alas.system.service.UserService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping
@Validated
public class AuthController {

    private final UserService userService;
    private final JwtService jwtService;
    private final CookieFactory cookieFactory;
    private final ReconnectService reconnectService;

    public AuthController(UserService userService, JwtService jwtService, CookieFactory cookieFactory, ReconnectService reconnectService) {
        this.userService = userService;
        this.jwtService = jwtService;
        this.cookieFactory = cookieFactory;
        this.reconnectService = reconnectService;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@Valid @RequestBody RegisterRequest request) {
        return userService.register(request.email(), request.password());
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        UserService.LoginResult result = userService.login(request.email(), request.password());
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookieFactory.authCookie(result.token(), jwtService.getUserExpireMinutes()).toString())
                .body(result.body());
    }

    @PostMapping("/purchase")
    public Map<String, Object> purchase(
            @CookieValue(value = "access_token", required = false) String token,
            @Valid @RequestBody PurchaseRequest request
    ) {
        User user = mustUser(token);
        int days = request.days() == null ? 30 : request.days();
        return userService.purchase(user, days);
    }

    @GetMapping("/purchase/status")
    public Map<String, Object> purchaseStatus(@CookieValue(value = "access_token", required = false) String token) {
        return userService.purchaseStatus(mustUser(token));
    }

    @GetMapping("/auth/check")
    public Map<String, Object> authCheck(@CookieValue(value = "access_token", required = false) String token) {
        return userService.authCheck(token);
    }

    @PostMapping("/logout")
    public ResponseEntity<Map<String, Object>> logout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookieFactory.clearAuthCookie().toString())
                .body(Map.of("msg", "已登出"));
    }

    @GetMapping("/user/info")
    public Map<String, Object> userInfo(@CookieValue(value = "access_token", required = false) String token) {
        return userService.userInfo(mustUser(token));
    }

    @PostMapping("/reconnect")
    public Map<String, Object> reconnect(@CookieValue(value = "access_token", required = false) String token) {
        return reconnectService.reconnect(mustUser(token));
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "healthy",
                "timestamp", Instant.now().toString()
        );
    }

    private User mustUser(String token) {
        return userService.fromAccessToken(token)
                .orElseThrow(() -> new ResponseStatusException(org.springframework.http.HttpStatus.UNAUTHORIZED, "Could not validate credentials"));
    }

    public record RegisterRequest(@Email String email, @NotBlank String password) {
    }

    public record LoginRequest(@Email String email, @NotBlank String password) {
    }

    public record PurchaseRequest(Integer days) {
    }
}
