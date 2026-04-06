package com.alas.system.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.Map;
import java.util.Optional;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JwtService {

    private final String userSecret;
    private final String adminSecret;
    private final int userExpireMinutes;
    private final int adminExpireMinutes;

    public JwtService(
            @Value("${app.jwt.user-secret}") String userSecret,
            @Value("${app.jwt.admin-secret}") String adminSecret,
            @Value("${app.jwt.user-expire-minutes}") int userExpireMinutes,
            @Value("${app.jwt.admin-expire-minutes}") int adminExpireMinutes
    ) {
        this.userSecret = userSecret;
        this.adminSecret = adminSecret;
        this.userExpireMinutes = userExpireMinutes;
        this.adminExpireMinutes = adminExpireMinutes;
    }

    public String createUserToken(String userId) {
        Instant now = Instant.now();
        Instant exp = now.plusSeconds((long) userExpireMinutes * 60);
        return Jwts.builder()
                .subject(userId)
                .issuedAt(Date.from(now))
                .expiration(Date.from(exp))
                .signWith(secretKey(userSecret))
                .compact();
    }

    public String createAdminToken(String adminName) {
        Instant now = Instant.now();
        Instant exp = now.plusSeconds((long) adminExpireMinutes * 60);
        return Jwts.builder()
                .subject(adminName)
                .claims(Map.of("role", "admin"))
                .issuedAt(Date.from(now))
                .expiration(Date.from(exp))
                .signWith(secretKey(adminSecret))
                .compact();
    }

    public Optional<Claims> parseUserToken(String token) {
        return parse(token, userSecret);
    }

    public Optional<Claims> parseAdminToken(String token) {
        return parse(token, adminSecret);
    }

    private Optional<Claims> parse(String token, String secret) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(secretKey(secret))
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return Optional.of(claims);
        } catch (Exception ignored) {
            return Optional.empty();
        }
    }

    private SecretKey secretKey(String secret) {
        try {
            byte[] bytes = Decoders.BASE64.decode(secret);
            if (bytes.length >= 32) {
                return Keys.hmacShaKeyFor(bytes);
            }
        } catch (Exception ignored) {
        }
        byte[] raw = secret.getBytes(StandardCharsets.UTF_8);
        byte[] key = new byte[32];
        for (int i = 0; i < key.length; i++) {
            key[i] = raw[i % raw.length];
        }
        return Keys.hmacShaKeyFor(key);
    }

    public int getUserExpireMinutes() {
        return userExpireMinutes;
    }

    public int getAdminExpireMinutes() {
        return adminExpireMinutes;
    }
}
