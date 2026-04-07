package com.alas.system.config;

import java.util.Arrays;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig {

    @Value("${app.cors.allowed-origin-patterns:https://alasm.gjiang.xyz:58000,https://api.gjiang.xyz:58000,http://localhost:*,https://localhost:*,http://127.0.0.1:*,https://127.0.0.1:*,http://10.10.10.*:*,https://10.10.10.*:*}")
    private String allowedOriginPatterns;

    @Bean
    public WebMvcConfigurer corsConfigurer() {
        List<String> originPatterns = Arrays.stream(allowedOriginPatterns.split(","))
                .map(String::trim)
                .filter(pattern -> !pattern.isEmpty())
                .toList();

        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                registry.addMapping("/**")
                        .allowedOriginPatterns(originPatterns.toArray(String[]::new))
                        .allowCredentials(true)
                        .allowedMethods("*")
                        .allowedHeaders("*")
                        .maxAge(1800);
            }
        };
    }
}
