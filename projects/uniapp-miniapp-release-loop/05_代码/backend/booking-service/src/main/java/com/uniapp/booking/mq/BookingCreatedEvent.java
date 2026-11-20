package com.uniapp.booking.mq;

/**
 * 预约创建事件（booking.created）。消费者按 `uk_booking_event(booking_id,event)` 幂等落库。
 *
 * @param event      事件名，固定 booking.created
 * @param bookingId  预约单号
 * @param userId     下单用户 id
 * @param packageId  套餐 id
 * @param bookDate   预约日期（YYYY-MM-DD）
 * @param slot       时段
 * @param contact    脱敏手机号（MQ 载荷不落明文 PII）
 * @param createdAt  下单时间
 */
public record BookingCreatedEvent(String event, long bookingId, long userId, long packageId,
                                  String bookDate, String slot, String contact, String createdAt) {
}
