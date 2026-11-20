package com.uniapp.booking.web.dto;

/**
 * 预约创建出参（R-02）：重复提交也返回 HTTP 200 + code=0，用 duplicated 区分首单/同单。
 *
 * @param bookingId  预约单号（首单与重复提交相同）
 * @param status     状态：0 待确认 / 1 已确认 / 2 已取消
 * @param duplicated true 表示命中幂等键，返回的是同一笔预约
 */
public record BookingCreateResponse(long bookingId, int status, boolean duplicated) {
}
