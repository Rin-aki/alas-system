package com.alas.system.controller;

import com.alas.system.domain.User;
import com.alas.system.service.PaymentService;
import com.alas.system.service.UserService;
import jakarta.validation.constraints.NotBlank;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/payment")
@Validated
public class PaymentController {

    private final PaymentService paymentService;
    private final UserService userService;

    public PaymentController(PaymentService paymentService, UserService userService) {
        this.paymentService = paymentService;
        this.userService = userService;
    }

    @GetMapping("/plans")
    public List<Map<String, Object>> listPlans() {
        return paymentService.listPlans();
    }

    @PostMapping("/create-session")
    public Map<String, Object> createSession(
            @CookieValue(value = "access_token", required = false) String token,
            @RequestBody CreateSessionRequest request
    ) {
        User user = mustUser(token);
        return paymentService.createCheckoutSession(user, request.planId());
    }

    @GetMapping("/verify")
    public Map<String, Object> verifySession(
            @CookieValue(value = "access_token", required = false) String token,
            @RequestParam("session_id") String sessionId
    ) {
        User user = mustUser(token);
        return paymentService.verifySession(user, sessionId);
    }

    // Stripe sends raw body — must NOT be parsed by Spring's JSON deserializer.
    // Mapping consumes text/plain as well to handle Stripe's content-type variations.
    @PostMapping(value = "/webhook", consumes = {"application/json", "text/plain"})
    public ResponseEntity<Map<String, Object>> webhook(
            @RequestBody String payload,
            @RequestHeader(value = "Stripe-Signature", required = false) String sigHeader
    ) {
        if (sigHeader == null || sigHeader.isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", "Missing Stripe-Signature"));
        }
        paymentService.handleWebhook(payload, sigHeader);
        return ResponseEntity.ok(Map.of("received", true));
    }

    private User mustUser(String token) {
        return userService.fromAccessToken(token)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Could not validate credentials"));
    }

    public record CreateSessionRequest(@NotBlank String planId) {}
}
