package com.uniapp.booking.domain;

import java.util.List;

/**
 * 「我的预约」分页出参（T-501）。
 *
 * @param list  当前页数据
 * @param total 该用户全部预约数
 * @param page  当前页码
 * @param size  每页条数
 */
public record BookingPage(List<BookingItem> list, long total, int page, int size) {
}
