package com.alas.system.security;

import java.security.SecureRandom;
import java.security.spec.KeySpec;
import java.util.Base64;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import org.springframework.stereotype.Service;

@Service
public class PasswordService {

    private static final int ROUNDS = 29000;
    private static final int SALT_BYTES = 16;
    private static final int HASH_BYTES = 32;
    private static final SecureRandom RANDOM = new SecureRandom();

    public String hashPassword(String plainPassword) {
        byte[] salt = new byte[SALT_BYTES];
        RANDOM.nextBytes(salt);
        byte[] digest = pbkdf2(plainPassword, salt, ROUNDS, HASH_BYTES);
        return "$pbkdf2-sha256$" + ROUNDS + "$" + toPasslibBase64(salt) + "$" + toPasslibBase64(digest);
    }

    public boolean verifyPassword(String plainPassword, String storedHash) {
        if (storedHash == null || storedHash.isBlank()) {
            return false;
        }

        if (storedHash.startsWith("$pbkdf2-sha256$")) {
            String[] parts = storedHash.split("\\$");
            if (parts.length < 5) {
                return false;
            }
            int rounds = Integer.parseInt(parts[2]);
            byte[] salt = fromPasslibBase64(parts[3]);
            byte[] expected = fromPasslibBase64(parts[4]);
            byte[] actual = pbkdf2(plainPassword, salt, rounds, expected.length);
            return constantTimeEquals(expected, actual);
        }

        return false;
    }

    private byte[] pbkdf2(String password, byte[] salt, int rounds, int hashBytes) {
        try {
            KeySpec spec = new PBEKeySpec(password.toCharArray(), salt, rounds, hashBytes * 8);
            SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
            return factory.generateSecret(spec).getEncoded();
        } catch (Exception e) {
            throw new IllegalStateException("Password hash operation failed", e);
        }
    }

    private boolean constantTimeEquals(byte[] a, byte[] b) {
        if (a.length != b.length) {
            return false;
        }
        int result = 0;
        for (int i = 0; i < a.length; i++) {
            result |= a[i] ^ b[i];
        }
        return result == 0;
    }

    private String toPasslibBase64(byte[] data) {
        return Base64.getEncoder().withoutPadding().encodeToString(data).replace('+', '.');
    }

    private byte[] fromPasslibBase64(String value) {
        String normalized = value.replace('.', '+');
        int mod = normalized.length() % 4;
        if (mod != 0) {
            normalized = normalized + "=".repeat(4 - mod);
        }
        return Base64.getDecoder().decode(normalized);
    }
}
