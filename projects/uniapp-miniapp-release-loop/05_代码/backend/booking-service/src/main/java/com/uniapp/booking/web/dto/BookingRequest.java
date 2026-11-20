package com.uniapp.booking.web.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 预约创建入参（T-402 / D-20）。
 * 字段级校验失败由 GlobalExceptionHandler 转 40001 + 字段名，前端据此做字段红字。
 */
public record BookingRequest(
        @NotNull(message = "套餐不能为空")
        Long packageId,

        @NotBlank(message = "预约日期不能为空")
        @Pattern(regexp = "\\d{4}-\\d{2}-\\d{2}", message = "日期格式需为 YYYY-MM-DD")
        String bookDate,

        @NotBlank(message = "时段不能为空")
        String slot,

        @NotBlank(message = "联系人手机号不能为空")
        @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
        String contact,

        @Size(max = 255, message = "备注最多 255 字")
        String remark) {
}
