package com.uniapp.booking.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * booking.* 配置（架构 §6 / §11）。
 * 密钥只能来自环境变量；application.yml 里的默认值仅本地开发占位。
 */
@ConfigurationProperties(prefix = "booking")
public class BookingProperties {

    private Jwt jwt = new Jwt();
    private Hmac hmac = new Hmac();
    private Idem idem = new Idem();
    private Cache cache = new Cache();
    private Cors cors = new Cors();
    /** 可预约窗口：今天 ~ 今天 + N 天（默认 30，超范围返回 40002）。 */
    private int windowDays = 30;

    public int getWindowDays() {
        return windowDays;
    }

    public void setWindowDays(int windowDays) {
        this.windowDays = windowDays;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public void setJwt(Jwt jwt) {
        this.jwt = jwt;
    }

    public Hmac getHmac() {
        return hmac;
    }

    public void setHmac(Hmac hmac) {
        this.hmac = hmac;
    }

    public Idem getIdem() {
        return idem;
    }

    public void setIdem(Idem idem) {
        this.idem = idem;
    }

    public Cache getCache() {
        return cache;
    }

    public void setCache(Cache cache) {
        this.cache = cache;
    }

    public Cors getCors() {
        return cors;
    }

    public void setCors(Cors cors) {
        this.cors = cors;
    }

    /** JWT 参数（HS256，默认 2h，C02）。 */
    public static class Jwt {
        private String secret;
        private int ttlHours = 2;

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public int getTtlHours() {
            return ttlHours;
        }

        public void setTtlHours(int ttlHours) {
            this.ttlHours = ttlHours;
        }
    }

    /** HMAC 签名参数（±60s 时间窗 + nonce 去重，R-08）。 */
    public static class Hmac {
        private String secret;
        private int windowSeconds = 60;

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public int getWindowSeconds() {
            return windowSeconds;
        }

        public void setWindowSeconds(int windowSeconds) {
            this.windowSeconds = windowSeconds;
        }
    }

    /** 幂等键 TTL（C05 600s）。 */
    public static class Idem {
        private int ttlSeconds = 600;

        public int getTtlSeconds() {
            return ttlSeconds;
        }

        public void setTtlSeconds(int ttlSeconds) {
            this.ttlSeconds = ttlSeconds;
        }
    }

    /** 套餐缓存 TTL（C04 300s）。 */
    public static class Cache {
        private int packageTtlSeconds = 300;

        public int getPackageTtlSeconds() {
            return packageTtlSeconds;
        }

        public void setPackageTtlSeconds(int packageTtlSeconds) {
            this.packageTtlSeconds = packageTtlSeconds;
        }
    }

    /** dev CORS 白名单（P2-02）。 */
    public static class Cors {
        private String allowedOrigins = "http://127.0.0.1:5186";

        public String getAllowedOrigins() {
            return allowedOrigins;
        }

        public void setAllowedOrigins(String allowedOrigins) {
            this.allowedOrigins = allowedOrigins;
        }
    }
}
