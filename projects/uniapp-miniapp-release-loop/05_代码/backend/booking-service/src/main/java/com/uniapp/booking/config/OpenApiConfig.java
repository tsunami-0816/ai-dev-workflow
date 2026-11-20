package com.uniapp.booking.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.StringSchema;
import io.swagger.v3.oas.models.parameters.Parameter;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springdoc.core.customizers.OperationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI 契约（T-704 / R-06）：声明 JWT 方案与本次新增的签名头，
 * 保证导出到 `06.5_契约/openapi.json` 后「未声明头 = 0」。
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI bookingOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("booking-service API")
                        .version("1.0.0")
                        .description("uniapp-miniapp-release-loop · 写真预约 demo 后端（6 个操作）"))
                .components(new Components()
                        .addSecuritySchemes("bearerAuth", new SecurityScheme()
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")));
    }

    /** 每个操作都登记 4 个云函数通道头（H5 直连可不带，故 required=false）。 */
    @Bean
    public OperationCustomizer channelHeaderCustomizer() {
        return (operation, handlerMethod) -> {
            addHeader(operation, "X-Client", "调用通道：cloud（云函数，需签名）/ http（H5 直连，免签名）");
            addHeader(operation, "X-Sign", "HMAC-SHA256 签名（X-Client=cloud 时必带）");
            addHeader(operation, "X-Timestamp", "签名时间戳（秒，±60s 时间窗）");
            addHeader(operation, "X-Nonce", "32 字符随机串，120s 内不可重复");
            return operation;
        };
    }

    private void addHeader(io.swagger.v3.oas.models.Operation operation, String name, String description) {
        // springdoc 2.6 对无参操作的 parameters 可能是 null（实测 NPE 根因）
        if (operation.getParameters() == null) {
            operation.setParameters(new java.util.ArrayList<>());
        }
        operation.getParameters().removeIf(p -> name.equals(p.getName()));
        operation.addParametersItem(new Parameter()
                .in("header")
                .name(name)
                .required(false)
                .description(description)
                .schema(new StringSchema()));
    }
}
