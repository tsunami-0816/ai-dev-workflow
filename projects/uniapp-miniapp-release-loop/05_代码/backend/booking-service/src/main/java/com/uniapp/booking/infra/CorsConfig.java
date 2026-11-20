package com.uniapp.booking.infra;

import com.uniapp.booking.config.BookingProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * dev CORS（P2-02）：只放开 booking.cors.allowed-origins 里的 H5 地址。
 * 生产环境不启用该配置（建议由网关统一处理）。
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    private final BookingProperties props;

    public CorsConfig(BookingProperties props) {
        this.props = props;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        String[] origins = props.getCors().getAllowedOrigins().split(",");
        registry.addMapping("/api/**")
                .allowedOrigins(origins)
                .allowedMethods("GET", "POST", "OPTIONS")
                .allowedHeaders("Authorization", "Content-Type", "X-Sign", "X-Timestamp",
                        "X-Nonce", "X-Client", "X-Idempotency-Key")
                .maxAge(3600);
    }
}
