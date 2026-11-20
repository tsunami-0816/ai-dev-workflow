package com.uniapp.booking.domain;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * booking 表行快照（T-402 / T-501）。只在 domain 层内部流转，不直接序列化给前端。
 *
 * @param id           主键
 * @param userId       下单用户
 * @param packageId    套餐 id
 * @param packageTitle 套餐名（列表 join 得到，幂等查单时可为 null）
 * @param bookDate     预约日期
 * @param slot         时段（上午/下午/晚间）
 * @param contact      联系人手机号（幂等键组成部分，列表出参前脱敏）
 * @param remark       备注
 * @param status       0 待确认 / 1 已确认 / 2 已取消
 * @param createdAt    创建时间
 */
public record BookingRow(long id, long userId, long packageId, String packageTitle,
                         LocalDate bookDate, String slot, String contact, String remark,
                         int status, LocalDateTime createdAt) {
}
