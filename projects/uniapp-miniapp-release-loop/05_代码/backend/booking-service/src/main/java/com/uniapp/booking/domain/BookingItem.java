package com.uniapp.booking.domain;

/**
 * 「我的预约」列表项（T-501）。手机号脱敏后返回，避免列表接口成为 PII 出口。
 */
public record BookingItem(long id, long packageId, String packageTitle, String bookDate,
                          String slot, String contactMasked, int status, String statusText,
                          String createdAt) {
}
