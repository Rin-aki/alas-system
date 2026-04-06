package com.alas.system.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseCookie.ResponseCookieBuilder;
import org.springframework.stereotype.Component;

@Component
public class CookieFactory {

    private final String cookieDomain;
    private final boolean secure;

    public CookieFactory(
            @Value("${app.cookie.domain:}") String cookieDomain,
            @Value("${app.cookie.secure:true}") boolean secure
    ) {
        this.cookieDomain = cookieDomain;
        this.secure = secure;
    }

    public ResponseCookie authCookie(String token, int minutes) {
        return base("access_token", token, minutes);
    }

    public ResponseCookie adminCookie(String token, int minutes) {
        return base("admin_token", token, minutes);
    }

    public ResponseCookie clearAuthCookie() {
        return base("access_token", "", 0);
    }

    public ResponseCookie clearAdminCookie() {
        return base("admin_token", "", 0);
    }

    private ResponseCookie base(String name, String value, int minutes) {
        ResponseCookieBuilder builder = ResponseCookie.from(name, value)
                .httpOnly(true)
                .secure(secure)
                .path("/")
                .sameSite(secure ? "None" : "Lax")
                .maxAge(minutes * 60L);

        if (cookieDomain != null && !cookieDomain.isBlank()) {
            builder.domain(cookieDomain.trim());
        }

        return builder.build();
    }
}
